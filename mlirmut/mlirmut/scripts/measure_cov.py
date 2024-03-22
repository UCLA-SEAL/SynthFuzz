import os
from argparse import ArgumentParser
import subprocess
import asyncio

from tqdm import tqdm


async def worker(
    queue, command_prefix_template, profraw_dir, profdata_dir, overwrite, timeout=30
):
    while True:
        # Get a "work item" out of the queue.
        file_path = await queue.get()
        file_name = os.path.basename(file_path)

        full_command = [
            arg.replace("%inputpath", file_path).replace(
                "%inputname", os.path.basename(file_path)
            )
            for arg in command_prefix_template
        ]

        profraw_path = os.path.join(profraw_dir, f"{file_name}.profraw")
        profdata_path = os.path.join(profdata_dir, f"{file_name}.profdata")
        if not overwrite and os.path.exists(profdata_path):
            queue.task_done()
            continue

        # Generate profraw
        proc = await asyncio.create_subprocess_exec(
            *full_command,
            env={"LLVM_PROFILE_FILE": profraw_path} | os.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except TimeoutError:
            proc.terminate()

        if not os.path.isfile(profraw_path):
            print(f"{profraw_path} does not exist.")
            queue.task_done()
            continue

        # Convert to profdata
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/llvm-profdata",
            "merge",
            "-sparse",
            profraw_path,
            "-o",
            profdata_path,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except TimeoutError:
            proc.terminate()

        # Clean up
        os.remove(profraw_path)

        if not os.path.isfile(profdata_path):
            print(f"{profdata_path} does not exist.")
            queue.task_done()
            continue

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
        for file_number in file_numbers[: args.max_items]:
            file_path = os.path.join(args.input_dir, f"{file_number}.mlir")
            queue.put_nowait(file_path)
    else:
        for entry in os.scandir(args.input_dir):
            if os.path.isfile(entry.path) and entry.name.endswith(".mlir"):
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
                command_prefix_template=args.command_prefix.split(" "),
                profraw_dir=args.temp_dir,
                profdata_dir=args.profdata_dir,
                overwrite=args.overwrite,
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
    parser.add_argument("profdata_dir")
    parser.add_argument("--temp-dir", default="/tmp/measure-cov-temp")
    parser.add_argument(
        "--command-prefix",
    )
    parser.add_argument("--max-threads", default=os.cpu_count(), type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-items", type=int, default=-1)
    args = parser.parse_args()

    if not os.path.exists(args.profdata_dir):
        os.makedirs(args.profdata_dir)

    if not os.path.exists(args.temp_dir):
        os.makedirs(args.temp_dir)

    asyncio.run(main(args))
