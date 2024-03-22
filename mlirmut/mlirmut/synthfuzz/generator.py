from enum import Flag, auto
import importlib
import tomllib
import codecs
import logging
import os
import random
from copy import deepcopy
from dataclasses import dataclass
import dill
import math
from pathlib import Path

from contextlib import nullcontext
from math import inf
from os.path import abspath, dirname
from shutil import rmtree

from grammarinator.tool.default_population import DefaultTree
from grammarinator.runtime.rule import Rule, UnlexerRule, UnparserRule

logger = logging.getLogger(__name__)

class FitnessViolation(Flag):
    NONE = 0
    SUB = auto()
    DUPE = auto()
    NO_INSERT_LOC = auto()

@dataclass(slots=True)
class NodePair:
    concrete: Rule
    abstract: Rule

@dataclass(eq=True, frozen=True)
class QuantifierSpec:
    min: int
    max: int
    rule_name: str
    # TODO: support more complex patterns
    # Currently, the quantifier can only have a single rule
    #production_pattern: list[str | UnlexerRule]

@dataclass(eq=True, frozen=True)
class InsertMatchPattern:
    # TODO: support more complex patterns
    match_pattern: list[str | QuantifierSpec]
    child_rules: set[str]

@dataclass
class CreatorResult:
    mutant: UnparserRule

@dataclass
class RecombineResult(CreatorResult):
    donor: Rule | None
    recipient: Rule | None

@dataclass
class EditResult(RecombineResult):
    substitutions: dict[Rule, Rule] | None
    is_fit: bool | None
    fitness_violation: FitnessViolation

@dataclass
class InsertResult(EditResult):
    # TODO: support multiple edits
    pass

@dataclass
class MutateResult(CreatorResult):
    mutated_node: Rule
    original_node: Rule

class SynthFuzzGeneratorTool:
    """
    Class to create new test cases using the generator produced by ``grammarinator-process``.
    """

    def __init__(self, generator_factory, out_format, lock=None, rule=None, max_depth=inf,
                 population=None, generate=True, mutate=True, recombine=True, edit=True, insert=True, keep_trees=False,
                 transformers=None, serializer=None, insert_patterns=None, mutation_config_path=None,
                 cleanup=True, encoding='utf-8', errors='strict', edit_seed=None, edit_log=None,
                 max_inserts_per_quantifier=20, save_to_file=True, driver=None, save_errors_only=False,
                 test_output_path=None, fitness_log_only=False, disable_parameters=False):
        """
        :param generator_factory: A callable that can produce instances of a
            generator. It is a generalization of a generator class: it has to
            instantiate a generator object, and it may also set the decision
            model and the listeners of the generator as well. In the simplest
            case, it can be a ``grammarinator-process``-created subclass of
            :class:`~grammarinator.runtime.Generator`, but in more complex
            scenarios a factory can be used, e.g., an instance of
            :class:`DefaultGeneratorFactory`.
        :param str rule: Name of the rule to start generation from (default: the
            default rule of the generator).
        :param str out_format: Test output description. It can be a file path pattern possibly including the ``%d``
               placeholder which will be replaced by the index of the test case. Otherwise, it can be an empty string,
               which will result in printing the test case to the stdout (i.e., not saving to file system).
        :param multiprocessing.Lock lock: Lock object necessary when printing test cases in parallel (optional).
        :param int or float max_depth: Maximum recursion depth during generation (default: ``inf``).
        :param ~grammarinator.tool.Population population: Tree pool for mutation
            and recombination.
        :param bool generate: Enable generating new test cases from scratch, i.e., purely based on grammar.
        :param bool mutate: Enable mutating existing test cases, i.e., re-generate part of an existing test case based on grammar.
        :param bool recombine: Enable recombining existing test cases, i.e., replace part of a test case with a compatible part from another test case.
        :param bool keep_trees: Keep generated trees to participate in further mutations or recombinations
               (otherwise, only the initial population will be mutated or recombined). It has effect only if
               population is defined.
        :param list transformers: List of transformers to be applied to postprocess
               the generated tree before serializing it.
        :param serializer: A seralizer that takes a tree and produces a string from it (default: :class:`str`).
               See :func:`grammarinator.runtime.simple_space_serializer` for a simple solution that concatenates tokens with spaces.
        :param bool cleanup: Enable deleting the generated tests at :meth:`__exit__`.
        :param str encoding: Output file encoding.
        :param str errors: Encoding error handling scheme.
        """

        self._generator_factory = generator_factory
        self._transformers = transformers or []
        self._serializer = serializer or str
        self._rule = rule

        if out_format:
            os.makedirs(abspath(dirname(out_format)), exist_ok=True)

        self._save_to_file = save_to_file
        self._out_format = out_format
        self._lock = lock or nullcontext()
        self._max_depth = max_depth
        self._population = population
        self._enable_generation = generate
        self._enable_mutation = mutate
        self._enable_recombination = recombine
        self._enable_edit = edit
        self._enable_insert = insert
        self._keep_trees = keep_trees
        self._cleanup = cleanup
        self._encoding = encoding
        self._errors = errors

        self._edit_rand = random.Random(edit_seed)
        self._edit_log = edit_log
        self._max_inserts_per_quantifier = max_inserts_per_quantifier
        self._insert_parents = set(insert_patterns.keys())
        self._insert_patterns: dict[str, InsertMatchPattern] = insert_patterns
        if mutation_config_path is None:
            mutation_config = {'fitness_criteria': {'should_substitute': [], 'no_duplicate': []}, 'parameterization': {'blacklist': []}}
        else:
            with mutation_config_path.open("rb") as f:
                mutation_config = tomllib.load(f)
        def build_match_dict(config_list):
            match_dict = dict()
            for entry in config_list:
                if "." in entry:
                    parent, child = entry.split(".")
                    if child not in match_dict:
                        match_dict[child] = []
                    match_dict[child].append(parent)
                else:
                    # any parent
                    match_dict[child] = "*"
            return match_dict
        self._parameter_blacklist = build_match_dict(mutation_config["parameterization"]["blacklist"])
        self._fitness_no_dupes = build_match_dict(mutation_config["fitness_criteria"]["no_duplicate"])
        self._fitness_should_sub = build_match_dict(mutation_config["fitness_criteria"]["should_substitute"])
        self._fitness_log_only = fitness_log_only

        self._driver = driver
        self._save_errors_only = save_errors_only
        self._test_output_path = Path(test_output_path) if test_output_path else None

        self._disable_parameters = disable_parameters

       
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Delete the output directory if the tests were saved to files and if ``cleanup`` was enabled.
        """
        if self._cleanup and self._out_format:
            rmtree(dirname(self._out_format))

    def create(self, index):
        """
        Create new test case with a randomly selected generator method from the available
        options (i.e., via :meth:`generate`, :meth:`mutate`, or :meth:`recombine`). The
        generated tree is transformed, serialized and saved according to the parameters
        used to initialize the current generator object.

        :param int index: Index of the test case to be generated.
        :return: Tuple of the path to the generated serialized test file and the path to the tree file. The second item,
               (i.e., the path to the tree file) might be ``None``, if either ``population`` or ``keep_trees`` were not set
               in :meth:`__init__` and hence the tree object was not saved either.
        :rtype: tuple[str, str]
        """
        creators = []
        if self._enable_generation:
            creators.append(("generate", self.generate))
        if self._population:
            if self._enable_mutation and self._population.can_mutate():
                creators.append(("mutate", lambda: self.mutate(self._population.select_to_mutate(self._max_depth))))
            if self._enable_recombination and self._population.can_recombine():
                creators.append(("recombine", lambda: self.recombine(*self._population.select_to_recombine(self._max_depth))))
            if self._enable_edit and self._population.can_recombine():
                creators.append(("edit", lambda: self.edit(*self._population.select_to_recombine(self._max_depth))))
            if self._enable_insert and self._population.can_recombine():
                creators.append(("insert", lambda: self.insert(*self._population.select_to_insert(self._max_depth))))
        strategy, creator = random.choice(creators)

        if strategy in ["edit", "insert"]:
            result = creator()
            # retry if it fails the fitness criteria
            tries = 1
            while (not self._fitness_log_only) and (not result.is_fit) and (tries < 10):
                result = creator()
                tries += 1
            if not result.is_fit:
                logger.warning('Failed to generate fit mutant after 10 tries; keeping the mutant anyway.')
        else:
            result = creator()
        for transformer in self._transformers:
            result.mutant = transformer(result.mutant)

        test = self._serializer(result.mutant)
        if self._save_to_file:
            test_fn = self._out_format % index if '%d' in self._out_format else self._out_format
            if self._save_errors_only:
                # check if the result is an error
                is_real_error, retcode, stderr = self._driver.test_one(test)
                # only add every 1000 mutants
                if retcode == 0 and index % 1000 == 0 and self._population and self._keep_trees:
                    self._population.add_individual(result.mutant, path=test_fn)
                if retcode == 0 or not is_real_error:
                    return None, index
                with open(self._test_output_path / f'{index}.log', 'w') as f:
                    f.write("Return code: %d\n" % retcode)
                    f.write(stderr)
            if self._edit_log:
                log_path = self._edit_log / f'{index}.pkl'
                info = {"strategy": strategy} | result.__dict__
                with open(log_path, 'wb') as f:
                    dill.dump(info, f)

            if not self._save_errors_only and self._population and self._keep_trees:
                self._population.add_individual(result.mutant, path=test_fn)

            if test_fn:
                with codecs.open(test_fn, 'w', self._encoding, self._errors) as f:
                    f.write(test)
            else:
                with self._lock:
                    print(test)

            return test_fn, index
        else:
            return test, index

    def generate(self, *, rule=None, max_depth=None):
        """
        Instantiate a new generator and generate a new tree from scratch.

        :param str rule: Name of the rule to start generation from.
        :param int max_depth: Maximum recursion depth during generation.
        :return: The root of the generated tree.
        :rtype: Rule
        """
        max_depth = max_depth if max_depth is not None else self._max_depth
        generator = self._generator_factory(max_depth=max_depth)

        rule = rule or self._rule or generator._default_rule.__name__
        start_rule = getattr(generator, rule)
        if not hasattr(start_rule, 'min_depth'):
            logger.warning('The \'min_depth\' property of %s is not set. Fallback to 0.', rule)
        elif start_rule.min_depth > max_depth:
            raise ValueError(f'{rule} cannot be generated within the given depth: {max_depth} (min needed: {start_rule.min_depth}).')

        return CreatorResult(mutant=start_rule())

    def mutate(self, mutated_node):
        """
        Mutate a tree at a given position, i.e., discard and re-generate its
        sub-tree at the specified node.

        :param Rule mutated_node: The root of the sub-tree that should be
            re-generated.
        :return: The root of the mutated tree.
        :rtype: Rule
        """
        original_node = deepcopy(mutated_node)
        node, level = mutated_node, 0
        while node.parent:
            node = node.parent
            level += 1

        mutated_node = mutated_node.replace(self.generate(rule=mutated_node.name, max_depth=self._max_depth - level))

        node = mutated_node
        while node.parent:
            node = node.parent
        return MutateResult(mutant=node, mutated_node=mutated_node, original_node=original_node)

    def recombine(self, recipient_node, donor_node):
        """
        Recombine two trees at given positions where the nodes are compatible
        with each other (i.e., they share the same node name). One of the trees
        is called the recipient while the other is the donor. The sub-tree
        rooted at the specified node of the recipient is discarded and replaced
        by the sub-tree rooted at the specified node of the donor.

        :param Rule recipient_node: The root of the sub-tree in the recipient.
        :param Rule donor_node: The root of the sub-tree in the donor.
        :return: The root of the recombined tree.
        :rtype: Rule
        """
        original_donor = deepcopy(donor_node)
        original_recipient = deepcopy(recipient_node)
        if recipient_node.name != donor_node.name:
            raise ValueError(f'{recipient_node.name} cannot be replaced with {donor_node.name}')

        node = recipient_node.replace(donor_node)
        while node.parent:
            node = node.parent
        return EditResult(mutant=node, is_fit=True, fitness_violation=FitnessViolation.NONE, donor=original_donor, recipient=original_recipient, substitutions=dict())
    def insert(self, recipient_tree: DefaultTree, donor_tree: DefaultTree):
        valid_parents = list(self._insert_parents & set(recipient_tree.nodes_by_name.keys()))
        random.shuffle(valid_parents)
        # for each possible parent node in the recipient tree:
        for parent_name in valid_parents:
            # verify that the donor tree has the required nodes for this insertion pattern
            insert_pattern = self._insert_patterns[parent_name]
            if len(insert_pattern.child_rules - set(donor_tree.nodes_by_name.keys())) > 0:
                continue
            
            # TODO: perform backtracking search for more complex patterns
            def greedy_quantifier_match(recipient_parent):
                """Try to match the children of the recipient node with the insert match pattern.
                The algorithm (*should be back-tracking) is greedy and assumes that quantifiers are for single nodes.
                Returns the child indicies where possible insertions can be made for each quantifier.
                """
                children = recipient_parent.children
                child_idx = 0
                insertion_locations = dict()
                for match_node in insert_pattern.match_pattern:
                    if isinstance(match_node, str):
                        if children[child_idx].name == match_node:
                            child_idx += 1
                        else:
                            return None  # no match
                    elif isinstance(match_node, QuantifierSpec):
                        # also check pattern index???
                        # TODO exit early if the the minimum is not satisfied
                        num_matches = 0
                        possible_locs = []
                        while child_idx < len(children):
                            # TODO handle quantifier multi-node patterns
                            if children[child_idx].name != match_node.rule_name:
                                break
                            possible_locs.append(child_idx)
                            num_matches += 1
                            child_idx += 1
                            if num_matches >= match_node.max:
                                break
                        if num_matches < match_node.min:
                            return None
                        # remove num_matches locations so that only max - num_matches remains
                        random.shuffle(possible_locs)
                        # check if max is math.inf
                        if match_node.max != math.inf:
                            possible_locs = possible_locs[:match_node.max-num_matches]
                        insertion_locations[match_node] = possible_locs
                    else:
                        raise ValueError(f'Unexpected match node type: {type(match_node)}')
                return insertion_locations    
               
            # for each possible insertion location in the recipient tree:
            recipient_parents = list(recipient_tree.nodes_by_name[parent_name])
            for recipient_parent in recipient_parents:
                insertion_locations = greedy_quantifier_match(recipient_parent)
                if insertion_locations is None:
                    continue
                for spec, locs in insertion_locations.items():
                    # remove excess locations
                    locs = locs[:self._max_inserts_per_quantifier]
                    for loc in locs:
                        # create a placeholder node
                        # we intentionally construct it with parent=None and then add the parent later
                        # to circumvent the default constructor behavior
                        recipient_node = UnparserRule(name=spec.rule_name, parent=None)
                        # a side effect of insert_child is to set the parent of the child
                        recipient_parent.insert_child(idx=loc, node=recipient_node)
                        donor_node = random.choice(list(donor_tree.nodes_by_name[spec.rule_name]))
                        #donor_node = list(donor_tree.nodes_by_name[spec.rule_name])[0]
                        # Make sure that the ancestors and siblings match
                        if not (self._population.context_filter.verify_k_ancestors(recipient_node, donor_node)
                            and self._population.context_filter.verify_l_siblings(recipient_node, donor_node)
                            and self._population.context_filter.verify_r_siblings(recipient_node, donor_node)):
                            continue

                        # TODO allow multiple edits
                        return self.edit(recipient_node, donor_node)
        return InsertResult(mutant=recipient_tree.root, donor=donor_tree.root, recipient=recipient_tree.root, substitutions=None, is_fit=False, fitness_violation=FitnessViolation.NO_INSERT_LOC)
    
    def index_nodes(self, current, nodes_by_name, exclude_subtree):
        if current == exclude_subtree:
            return
        # exclude nodes in the parameter blacklist
        if (current.name in self._parameter_blacklist
            and (
                self._parameter_blacklist[current.name] == "*"
                or current.parent.name in self._parameter_blacklist[current.name]
            )):
            return
        if "*" in self._parameter_blacklist and current.name in self._parameter_blacklist['*']:
            return
        if current.name not in nodes_by_name:
            nodes_by_name[current.name] = []
        nodes_by_name[current.name].append(current)
        if current.children:
            for child in current.children:
                self.index_nodes(child, nodes_by_name, exclude_subtree)

    def edit(self, recipient_node, donor_node):
        original_donor = deepcopy(donor_node)
        original_recipient = deepcopy(recipient_node)
        substitutions = dict()

        # if the donor has no children, then we can't do any adaptations
        # if we disabled parameters, just do a regular recombine
        if not donor_node.children or self._disable_parameters:
            return self.recombine(recipient_node, donor_node)

        # get the root node of the donor tree
        def get_root(node):
            root = node
            while root.parent:
                root = root.parent
            return root
        donor_root = get_root(donor_node)

        # index the donor tree for possible substitutions
        fragment_nodes = dict()
        for child in donor_node.children:
            self.index_nodes(child, fragment_nodes, exclude_subtree=None)
        context_nodes = dict()
        self.index_nodes(donor_root, context_nodes, exclude_subtree=donor_node)
        common_names = set(fragment_nodes.keys()) & set(context_nodes.keys())

        # traverse the recipient and donor trees to find substitutions
        # we assume exact matches occur when the source strings match exactly
        def get_matching_nodes(ref_value, value_list, node_list):
            return [node_list[i] for i, value in enumerate(value_list) if value == ref_value]

        # locate parameters
        parameters = dict()
        for name in common_names:
            nodes_in_fragment = fragment_nodes[name]
            nodes_in_context = context_nodes[name]
            node_strings_in_fragment = [str(node) for node in nodes_in_fragment]
            node_strings_in_context = [str(node) for node in nodes_in_context]
            for unique_node_string in set(node_strings_in_fragment):
                param_nodes_in_fragment = get_matching_nodes(ref_value=unique_node_string, value_list=node_strings_in_fragment, node_list=nodes_in_fragment)
                param_nodes_in_context = get_matching_nodes(ref_value=unique_node_string, value_list=node_strings_in_context, node_list=nodes_in_context)
                for param_node in param_nodes_in_context:
                    parameters[param_node] = param_nodes_in_fragment

        # first collect all common ancestors
        # ancestors will be a list from closest to furthest ancestor
        ancestors_concrete = [recipient_node]
        ancestors_abstract = [donor_node]
        concrete, abstract = recipient_node, donor_node
        while (concrete.parent and abstract.parent and
        (concrete.parent.name == abstract.parent.name)):
            concrete, abstract = concrete.parent, abstract.parent
            ancestors_concrete.append(concrete)
            ancestors_abstract.append(abstract)

        # TODO: when we explore, we should stop exploring a path when there are no parameters to find along that path
        def get_siblings(idx, ancestors):
            ancestor_parent: Rule = ancestors[idx]
            ancestor_child: Rule = ancestors[idx-1]
            siblings = ancestor_parent.children
            ancestor_child_idx = siblings.index(ancestor_child)
            siblings_left = siblings[:ancestor_child_idx]
            siblings_right = siblings[ancestor_child_idx+1:]
            return siblings_left, siblings_right
        parameter_values = dict()
        def save_param(a_node, c_node):
            if a_node in parameter_values:
                parameter_values[a_node].append(c_node)
            else:
                parameter_values[a_node] = [c_node]
        def match_nodes(abstract_nodes: list[Rule], concrete_nodes: list[Rule]):
            matching_nodes = []
            # for each abstract node, we look for a matching concrete node
            c_idx = 0
            for a_idx in range(len(abstract_nodes)):
                a_node = abstract_nodes[a_idx]
                old_idx = c_idx
                while c_idx < len(concrete_nodes):
                    c_node = concrete_nodes[c_idx]
                    c_idx += 1
                    # if we find a matching pair, we stop and go to the next abstract node
                    if a_node.name == c_node.name:
                        if a_node in parameters:
                            save_param(a_node=a_node, c_node=c_node)
                        else:
                            # continue matching down the chain
                            matching_nodes.append(NodePair(concrete=c_node, abstract=a_node))
                        break
                # if we've exhausted the concrete nodes for this abstract node, then we reset to after the last maching concrete node
                if c_idx >= len(concrete_nodes):
                    c_idx = old_idx

            return matching_nodes
        def recursively_match_nodes(abstract_nodes: list[Rule], concrete_nodes: list[Rule]):
            matching_nodes = match_nodes(abstract_nodes=abstract_nodes, concrete_nodes=concrete_nodes)
            for pair in matching_nodes:
                if pair.abstract.children is None or pair.concrete.children is None:
                    continue
                recursively_match_nodes(abstract_nodes=pair.abstract.children, concrete_nodes=pair.concrete.children)

        # get parameters
        assert len(ancestors_concrete) == len(ancestors_abstract)
        for ancestor_idx in range(1, len(ancestors_concrete)):
            siblings_concrete_left, siblings_concrete_right = get_siblings(ancestor_idx, ancestors_concrete)
            siblings_abstract_left, siblings_abstract_right = get_siblings(ancestor_idx, ancestors_abstract)
            recursively_match_nodes(abstract_nodes=siblings_abstract_left, concrete_nodes=siblings_concrete_left)
            recursively_match_nodes(abstract_nodes=siblings_abstract_right, concrete_nodes=siblings_concrete_right)

        # determine which parameter nodes in the fragment must be substituted according to the fitness criteria
        to_check = set()
        for param_nodes in parameters.values():
            for param_node in param_nodes:
                if (param_node.name in self._fitness_should_sub
                    and (self._fitness_should_sub[param_node.name] == "*"
                         or param_node.parent.name in self._fitness_should_sub[param_node.name])):
                    to_check.add(param_node)
            
        # substitute parameters and check fitness
        for a_node, param_values in parameter_values.items():
            if len(param_values) == 0:
                continue
            # randomly choose one of the possible parameter values
            param_value = self._edit_rand.choice(param_values)
            substitutions[a_node] = param_value
            for param_node in parameters[a_node]:
                param_node.replace(param_value)
                if param_node in to_check:
                    to_check.remove(param_node)
        is_fit = len(to_check) == 0
        fitness_violation = FitnessViolation.NONE if is_fit else FitnessViolation.SUB
                        
        # insert fragment
        node = recipient_node.replace(donor_node)
        while node.parent:
            node = node.parent
        
        # check if the resulting mutant satisfies the no duplicate criteria
        seen_potential_dupes = set()
        def has_duplicates(node):
            if node.name in self._fitness_no_dupes and (
                self._fitness_no_dupes[node.name] == "*" or
                node.parent.name in self._fitness_no_dupes[node.name]):
                if str(node) in seen_potential_dupes:
                    return True
                seen_potential_dupes.add(str(node))
            if node.children:
                for child in node.children:
                    if has_duplicates(child):
                        return True
            return False
        has_dupes = has_duplicates(node)
        is_fit = is_fit and not has_dupes
        if has_dupes:
            fitness_violation |= FitnessViolation.DUPE
        
        return EditResult(mutant=node, donor=original_donor, recipient=original_recipient, substitutions=substitutions, is_fit=is_fit, fitness_violation=fitness_violation)