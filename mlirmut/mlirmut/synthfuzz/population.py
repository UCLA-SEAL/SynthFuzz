import logging
import random
from itertools import batched
from grammarinator.tool.default_population import DefaultPopulation, DefaultTree

logger = logging.getLogger(__name__)

# Grammarinator's left and right sibling properties are broken
# since the __getattr__ workaround overrides them
def left_sibling(node):
    if not node.parent:
        return None
    idx = node.parent.children.index(node)
    return node.parent.children[idx - 1] if idx > 0 else None
def right_sibling(node):
    if not node.parent:
        return None
    idx = node.parent.children.index(node)
    return node.parent.children[idx + 1] if idx < len(node.parent.children) - 1 else None

class ContextFilter:
    def __init__(self, k_ancestors: int, l_siblings: int, r_siblings: int, limit_by_donor_context: bool = True):
        self.k_ancestors = k_ancestors
        self.l_siblings = l_siblings
        self.r_siblings = r_siblings
        self.limit_by_donor_context = limit_by_donor_context

    def verify_k_ancestors(self, recipient, donor):
        r_node = recipient.parent
        d_node = donor.parent
        for _ in range(self.k_ancestors):
            if self.limit_by_donor_context and d_node is None:
                break
            if r_node is None or d_node is None:
                return False
            if r_node.name != d_node.name:
                return False
            r_node = r_node.parent
            d_node = d_node.parent
        return True
    def verify_l_siblings(self, recipient, donor):
        r_node = left_sibling(recipient)
        d_node = left_sibling(donor)
        for _ in range(self.l_siblings):
            if self.limit_by_donor_context and d_node is None:
                break
            if r_node is None or d_node is None:
                return False
            if r_node.name != d_node.name:
                return False
            r_node = left_sibling(r_node)
            d_node = left_sibling(d_node)
        return True
    def verify_r_siblings(self, recipient, donor):
        r_node = right_sibling(recipient)
        d_node = right_sibling(donor)
        for _ in range(self.r_siblings):
            if self.limit_by_donor_context and d_node is None:
                break
            if r_node is None or d_node is None:
                return False
            if r_node.name != d_node.name:
                return False
            r_node = right_sibling(r_node)
            d_node = right_sibling(d_node)
        return True


# TODO: implement a recombine selector that considers context length
class SynthFuzzPopulation(DefaultPopulation):
    def __init__(
        self,
        directory,
        k_ancestors: int,
        l_siblings: int,
        r_siblings: int,
        min_depths=None,
        limit_by_donor_context: bool = True,
    ):
        super().__init__(directory=directory, min_depths=min_depths)
        self.context_filter = ContextFilter(k_ancestors, l_siblings, r_siblings, limit_by_donor_context)
    
    def select_to_insert(self, max_depth):
        tree_fn_options = self._random_individuals(n=len(self._files))
        for batch in batched(tree_fn_options, 2):
            if len(batch) < 2:
                break
            recipient_tree = DefaultTree.load(batch[0])
            donor_tree = DefaultTree.load(batch[1])
            return recipient_tree, donor_tree

    def select_to_edit(self, max_depth):
        return self.select_to_recombine(self, max_depth)

    def select_to_recombine(self, max_depth):
        tree_fn_options = self._random_individuals(n=len(self._files))
        for batch in batched(tree_fn_options, 2):
            if len(batch) < 2:
                break
            recipient_tree = DefaultTree.load(batch[0])
            donor_tree = DefaultTree.load(batch[1])

            common_types = set(recipient_tree.nodes_by_name.keys()).intersection(
                set(donor_tree.nodes_by_name.keys())
            )
            recipient_options = self._filter_nodes(
                recipient_tree,
                (
                    node
                    for rule_name in common_types
                    for node in recipient_tree.nodes_by_name[rule_name]
                ),
                max_depth,
            )
            # Shuffle suitable nodes with sample.
            for recipient_node in random.sample(
                recipient_options, k=len(recipient_options)
            ):
                donor_options = tuple(donor_tree.nodes_by_name[recipient_node.name])
                for donor_node in random.sample(donor_options, k=len(donor_options)):
                    # Make sure that the ancestors and siblings match
                    if not (self.context_filter.verify_k_ancestors(recipient_node, donor_node)
                        and self.context_filter.verify_l_siblings(recipient_node, donor_node)
                        and self.context_filter.verify_r_siblings(recipient_node, donor_node)):
                        continue
                    # Make sure that the output tree won't exceed the depth limit.
                    if (
                        recipient_tree.node_levels[recipient_node]
                        + donor_tree.node_depths[donor_node]
                        <= max_depth
                    ):
                        return recipient_node, donor_node
