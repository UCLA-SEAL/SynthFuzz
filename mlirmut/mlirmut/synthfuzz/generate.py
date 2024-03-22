import inspect
import json
import os
import codecs
import random
import pickle
import logging
from pathlib import Path
from importlib import import_module

from argparse import ArgumentParser, ArgumentTypeError, SUPPRESS
from functools import partial
from itertools import count
from math import inf
from multiprocessing import Manager, Pool
from os.path import abspath, exists, isdir, join

from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument
from inators.imp import import_object

from grammarinator.cli import add_encoding_argument, add_encoding_errors_argument, add_jobs_argument, import_list, init_logging, logger
from grammarinator.tool.generator import DefaultGeneratorFactory

from .generator import SynthFuzzGeneratorTool
from .population import SynthFuzzPopulation
from mlirmut.pkgdata import __version__

def restricted_float(value):
    value = float(value)
    if value <= 0.0 or value > 1.0:
        raise ArgumentTypeError(f'{value!r} not in range (0.0, 1.0]')
    return value


def process_args(args):
    args.generator = import_object(args.generator)
    args.model = import_object(args.model)
    args.listener = import_list(args.listener)
    args.transformer = import_list(args.transformer)
    args.serializer = import_object(args.serializer) if args.serializer else None

    if args.weights:
        if not exists(args.weights):
            raise ValueError('Custom weights should point to an existing JSON file.')

        with open(args.weights, 'r') as f:
            weights = {}
            for rule, alts in json.load(f).items():
                for alternation_idx, alternatives in alts.items():
                    for alternative_idx, w in alternatives.items():
                        weights[(rule, int(alternation_idx), int(alternative_idx))] = w
            args.weights = weights
    else:
        args.weights = {}

    if args.population:
        if not isdir(args.population):
            raise ValueError('Population must point to an existing directory.')
        args.population = abspath(args.population)


def generator_tool_helper(args, weights, lock, save_to_file):
    if args.insert_patterns is not None:
        with open(args.insert_patterns, 'rb') as f:
            insert_patterns = pickle.load(f)
    else:
        insert_patterns = None
    if args.driver_class:
        driver_module_name, driver_class_name = args.driver_class.rsplit('.', 1)
        driver_module = import_module(driver_module_name)
        driver_class = getattr(driver_module, driver_class_name)
        driver = driver_class(args.driver_config)
    else:
        driver = None
    return SynthFuzzGeneratorTool(generator_factory=DefaultGeneratorFactory(args.generator,
                                                                   model_class=args.model,
                                                                   cooldown=args.cooldown,
                                                                   weights=weights,
                                                                   lock=lock,
                                                                   listener_classes=args.listener),
                         driver=driver,
                         test_output_path=args.test_output_path,
                         save_errors_only=args.save_errors_only,
                         rule=args.rule, out_format=args.out,
                         max_depth=args.max_depth,
                         population=SynthFuzzPopulation(args.population,
                                                      min_depths={name: method.min_depth
                                                                  for name, method in inspect.getmembers(args.generator, inspect.ismethod)
                                                                  if hasattr(method, 'min_depth')}, k_ancestors=args.k_ancestors, l_siblings=args.l_siblings, r_siblings=args.r_siblings) if args.population else None,
                         generate=args.generate, mutate=args.mutate, recombine=args.recombine, edit=args.edit, insert=args.insert,
                         keep_trees=args.keep_trees, insert_patterns=insert_patterns, mutation_config_path=args.mutation_config,
                         transformers=args.transformer, serializer=args.serializer,
                         cleanup=False, encoding=args.encoding, errors=args.encoding_errors,
                         edit_seed=args.edit_seed, edit_log=args.edit_log, max_inserts_per_quantifier=args.max_inserts,
                         save_to_file=save_to_file, fitness_log_only=args.fitness_log_only, disable_parameters=args.disable_parameters)


def create_test(generator_tool, index, *, seed):
    if seed:
        random.seed(seed + index)
    return generator_tool.create(index)


def execute():
    parser = ArgumentParser(description='Grammarinator: Generate', epilog="""
        The tool acts as a default execution harness for generators
        created by Grammarinator:Processor.
        """)
    # Settings for generating from grammar.
    parser.add_argument('generator', metavar='NAME',
                        help='reference to the generator created by grammarinator-process (in package.module.class format).')
    parser.add_argument('-r', '--rule', metavar='NAME',
                        help='name of the rule to start generation from (default: the parser rule set by grammarinator-process).')
    parser.add_argument('-m', '--model', metavar='NAME', default='grammarinator.runtime.DefaultModel',
                        help='reference to the decision model (in package.module.class format) (default: %(default)s).')
    parser.add_argument('-l', '--listener', metavar='NAME', action='append', default=[],
                        help='reference to a listener (in package.module.class format).')
    parser.add_argument('-t', '--transformer', metavar='NAME', action='append', default=[],
                        help='reference to a transformer (in package.module.function format) to postprocess the generated tree '
                             '(the result of these transformers will be saved into the serialized tree, e.g., variable matching).')
    parser.add_argument('-s', '--serializer', metavar='NAME',
                        help='reference to a seralizer (in package.module.function format) that takes a tree and produces a string from it.')
    parser.add_argument('-d', '--max-depth', default=inf, type=int, metavar='NUM',
                        help='maximum recursion depth during generation (default: %(default)f).')
    parser.add_argument('-c', '--cooldown', default=1.0, type=restricted_float, metavar='NUM',
                        help='cool-down factor defines how much the probability of an alternative should decrease '
                             'after it has been chosen (interval: (0, 1]; default: %(default)f).')
    parser.add_argument('-w', '--weights', metavar='FILE',
                        help='JSON file defining custom weights for alternatives.')

    # Evolutionary settings.
    parser.add_argument('--population', metavar='DIR',
                        help='directory of grammarinator tree pool.')
    parser.add_argument('--no-generate', dest='generate', default=True, action='store_false',
                        help='disable test generation from grammar.')
    parser.add_argument('--no-mutate', dest='mutate', default=True, action='store_false',
                        help='disable test generation by mutation (disabled by default if no population is given).')
    parser.add_argument('--no-recombine', dest='recombine', default=True, action='store_false',
                        help='disable test generation by recombination (disabled by default if no population is given).')
    parser.add_argument('--no-edit', dest='edit', default=True, action='store_false',
                        help='disable test generation by SynthFuzz (disabled by default if no population is given).')
    parser.add_argument('--no-insert', dest='insert', default=True, action='store_false',
                        help='disable test generation by SynthFuzz insertion (disabled by default if no population is given).')
    parser.add_argument('--max-inserts', default=20, type=int,
                        help='maximum number of insertions per quantifier (default: %(default)d).')
    parser.add_argument('--insert-patterns', default=None, metavar='FILE', help='Pickle file containing insert patterns.')
    parser.add_argument('--mutation-config', metavar='FILE', default=None, type=Path, help='TOML file containing mutation config.')
    parser.add_argument('--edit-log', type=Path)
    parser.add_argument('--keep-trees', default=False, action='store_true',
                        help='keep generated tests to participate in further mutations or recombinations (only if population is given).')
    parser.add_argument('--k-ancestors', default=0, type=int, metavar='NUM',
                        help='number of ancestors to consider for SynthFuzz (default: %(default)d).')
    parser.add_argument('--l-siblings', default=0, type=int, metavar='NUM',
                        help='number of left siblings to consider for SynthFuzz (default: %(default)d).')
    parser.add_argument('--r-siblings', default=0, type=int, metavar='NUM',
                        help='number of right siblings to consider for SynthFuzz (default: %(default)d).')
    parser.add_argument('--batch-size', default=1, type=int, metavar='NUM',
                        help='number of tests to generate at once (default: %(default)d).')
    parser.add_argument('--batch-dir', metavar='DIR', help='directory to store batched tests.')
    parser.add_argument('--batch-ext', default='', help='File extension for batched tests including the "." (example: ".txt").')
    parser.add_argument('--test-output-path', default=None, help='path to the directory where the test output will be saved.')
    parser.add_argument('--save-errors-only', action='store_true', help='save only tests that cause the test driver to return non-zero.')
    parser.add_argument('--driver-class', default=None, type=str, help='fully qualified name of the test driver class.')
    parser.add_argument('--driver-config', default=None, metavar='FILE', help='TOML file containing driver config.')
    parser.add_argument('--fitness-log-only', action='store_true', help='Only log fitness values instead of applying.')
    parser.add_argument('--disable-parameters', action='store_true', help='Disable parameters during generation.')


    # Auxiliary settings.
    parser.add_argument('-o', '--out', metavar='FILE', default=join(os.getcwd(), 'tests', 'test_%d'),
                        help='output file name pattern (default: %(default)s).')
    parser.add_argument('--stdout', dest='out', action='store_const', const='', default=SUPPRESS,
                        help='print test cases to stdout (alias for --out=%(const)r)')
    parser.add_argument('-n', default=1, type=int, metavar='NUM',
                        help='number of tests to generate, \'inf\' for continuous generation (default: %(default)s).')
    parser.add_argument('--random-seed', type=int, metavar='NUM',
                        help='initialize random number generator with fixed seed (not set by default).')
    parser.add_argument('--edit-seed', type=int, metavar='NUM',
                        help='initialize random number generator with fixed seed (not set by default). We use a separate RNG for edits for reproducibility with recombination.')               
    add_encoding_argument(parser, help='output file encoding (default: %(default)s).')
    add_encoding_errors_argument(parser)
    add_jobs_argument(parser)
    add_sys_path_argument(parser)
    add_sys_recursion_limit_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    init_logging()
    process_log_level_argument(args, logger)
    process_sys_path_argument(args)
    process_sys_recursion_limit_argument(args)
    try:
        process_args(args)
    except ValueError as e:
        parser.error(e)

    save_to_file = True
    # If the batch size is > 1, then we need a separate batch directory
    if args.batch_size > 1:
        save_to_file = False  # Don't save to individual files; we'll save batches at a time instead.
        if args.batch_dir is None:
            raise ValueError(f'Batch directory must be specified if batch size is > 1. (batch_size={args.batch_size})')
        elif exists(args.batch_dir) and not isdir(args.batch_dir):
            raise ValueError(f'Batch directory must be a directory if batch size is > 1. (batch_dir={args.batch_dir})')
        elif not exists(args.batch_dir):
            os.makedirs(args.batch_dir)

    if args.jobs > 1:
        with Manager() as manager:
            with generator_tool_helper(args, weights=manager.dict(args.weights), lock=manager.Lock(), save_to_file=save_to_file) as generator_tool:  # pylint: disable=no-member
                parallel_create_test = partial(create_test, generator_tool, seed=args.random_seed)
                with Pool(args.jobs) as pool:
                    if args.batch_size > 1:
                        batched_run(pool, parallel_create_test, args)
                    else:
                        for idx, _ in enumerate(pool.imap_unordered(parallel_create_test, count(0) if args.n == inf else range(args.n))):
                            print(f'\rGenerated test case #{idx}', end='')

    else:
        with generator_tool_helper(args, weights=args.weights, lock=None) as generator_tool:
            for i in count(0) if args.n == inf else range(args.n):
                create_test(generator_tool, i, seed=args.random_seed)

def batched_run(pool, parallel_create_test, args):
    last_idx = 0
    test_batch = []
    for test, index in pool.imap(parallel_create_test, count(0) if args.n == inf else range(args.n)):
        if ((index+1) % args.batch_size) == 0:
            batch_fn = join(args.batch_dir, f"batch_{last_idx}-{index}{args.batch_ext}")
            with codecs.open(batch_fn, 'w', args.encoding, args.encoding_errors) as f:
                f.write("\n// -----\n".join(test_batch))
            test_batch = []
            last_idx = index
        # batch range is exclusive of the last index
        test_batch.append(test)
    # final batch
    if len(test_batch) > 0:
        batch_fn = join(args.batch_dir, f"batch_{last_idx}-{args.n}{args.batch_ext}")
        with codecs.open(batch_fn, 'w', args.encoding, args.encoding_errors) as f:
            f.write("\n// -----\n".join(test_batch))


if __name__ == "__main__":
    execute()