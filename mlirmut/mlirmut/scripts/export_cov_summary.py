import os
from argparse import ArgumentParser
import subprocess
import asyncio

from tqdm import tqdm


async def worker(queue, target_binary, profdata_dir, json_dir, overwrite, timeout=30):
    while True:
        # Get a "work item" out of the queue.
        file_path = await queue.get()
        file_name = os.path.basename(file_path)

        profdata_path = os.path.join(profdata_dir, file_name)
        json_path = os.path.join(json_dir, f"{file_name}.json")

        if not overwrite and os.path.exists(json_path):
            queue.task_done()
            continue

        # Export to json
        with open(json_path, "w") as f:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/llvm-cov",
                "export",
                "-summary-only",
                "-instr-profile",
                profdata_path,
                target_binary,
                stdout=f,
            )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except TimeoutError:
            proc.terminate()

        queue.task_done()


async def monitor_queue(queue):
    try:
        num_items = queue.qsize()
        pbar = tqdm(total=num_items)
        while True:
            diff = num_items - queue.qsize()
            num_items -= diff
            pbar.update(diff)
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pbar.close()


async def main(args):
    # Create a queue that we will use to store our "workload".
    queue = asyncio.Queue()

    # Enqueue all files in the directory
    if args.max_items >= 0:
        # assume filenames are numbered
        file_names = os.listdir(args.input_dir)
        file_numbers = [os.path.splitext(f)[0] for f in file_names]
        file_numbers.sort()
        for file_number in file_numbers[:args.max_items]:
            file_path = os.path.join(args.input_dir, f"{file_number}.profdata")
            queue.put_nowait(file_path)
    else:
        for entry in os.scandir(args.input_dir):
            if os.path.isfile(entry.path) and entry.name.endswith(".profdata"):
                queue.put_nowait(entry.path)

    # Create a task to monitor the queue size.
    tasks = []
    monitor_task = asyncio.create_task(monitor_queue(queue=queue))
    tasks.append(monitor_task)

    # Create worker tasks to process the queue concurrently.
    for _ in range(args.max_threads):
        task = asyncio.create_task(
            worker(
                queue=queue,
                target_binary=args.target_binary,
                profdata_dir=args.input_dir,
                json_dir=args.json_dir,
                overwrite=args.overwrite,
                timeout=args.timeout,
            )
        )
        tasks.append(task)

    # Wait until the queue is fully processed.
    await queue.join()

    # Cancel our worker tasks.
    for task in tasks:
        task.cancel()

    # Wait until all worker tasks are cancelled.
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument("json_dir")
    parser.add_argument(
        "--target-binary",
    )
    parser.add_argument("--max-threads", default=os.cpu_count(), type=int)
    parser.add_argument("--max-items", default=-1, type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--timeout", default=30, type=int)
    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        os.makedirs(args.input_dir)

    if not os.path.exists(args.json_dir):
        os.makedirs(args.json_dir)

    asyncio.run(main(args))
