# Python2 and Python 3 compatibility:
from __future__ import absolute_import, division, print_function, unicode_literals

import codecs
import json
import logging
import pickle
from math import ceil, log
from random import choice, randrange
from typing import Any

from src.exceptions import GrammarParseError
from src.grammar.constraint import Constraint, _get_number_of_constraints, TieredLocalConstraint
from src.grammar.constraint import MaxConstraint, DepConstraint, PhonotacticConstraint, IdentConstraint
from src.models.otml_configuration import settings
from src.models.transducer import Transducer
from src.utils.randomization_tools import get_weighted_list

logger = logging.getLogger(__name__)

CONSTRAINTS_DELIM = " >> "
DEMOTE_CASHING_FLAG = True

constraint_set_transducers = dict()


class ConstraintSet:
    def __init__(self, constraint_set_list: list[dict[str, Any]], feature_table):
        self.feature_table = feature_table
        self.constraints: list[Constraint] = list()

        constraint: dict[str, Any]
        for constraint in constraint_set_list:
            constraint_name = constraint["type"]
            if not constraint_name:
                raise GrammarParseError("Missing 'type' key")

            constraint_class = Constraint.get_constraint_class_by_name(constraint_name)
            self.constraints.append(constraint_class.from_dict(feature_table, constraint))

    def __str__(self):
        return f"Constraint Set (energy {self.get_encoding_length()}): {CONSTRAINTS_DELIM.join([str(cons) for cons in self.constraints])}"

    def __hash__(self):
        return hash(str(self))

    @staticmethod
    def clear_caching():
        global constraint_set_transducers
        constraint_set_transducers = dict()

    @classmethod
    def loads(cls, constraint_set_json_str, feature_table):
        constraint_set_list = json.loads(constraint_set_json_str)
        return cls(constraint_set_list, feature_table)

    @classmethod
    def load(cls, grammar_filename, feature_table):

        with codecs.open(grammar_filename, "r") as f:
            file_string = f.read()
            try:
                constraint_set_list = json.loads(file_string)
            except ValueError:
                return ConstraintSet.load_from_printed_string_representation(file_string, feature_table)
        return cls(constraint_set_list, feature_table)

    @classmethod
    def load_from_printed_string_representation(cls, constraint_set_string, feature_table):
        constraint_set_json = cls.json_from_printed_string_representation(constraint_set_string)
        constraint_set_list = json.loads(constraint_set_json)
        return cls(constraint_set_list, feature_table)

    @classmethod
    def json_from_printed_string_representation(cls, constraint_set_string):
        """
        dict order of features in a bundle in irrelevant
        """
        # Phonotactic[[+stop][+syll]]

        # Phonotactic[[+stop, -voice][+syll]]
        # {"type": "Phonotactic", "bundles": [{"stop": "+", "voice": "-"}, {"syll": "+}]}

        # Faith[] >> Phonotactic[+cons] >> Max[+cons]

        constraint_set_list = list()
        string_constraints = constraint_set_string.split(CONSTRAINTS_DELIM)
        for string_constraint in string_constraints:
            constraint_set_list.append(_parse_constraint(string_constraint))

        constraint_set_json = str(constraint_set_list).replace("'", '"')  # ' -> "
        return constraint_set_json

    def get_encoding_length(self):
        k = ceil(log(_get_number_of_constraints() + self.feature_table.get_number_of_features() + 2 + 1, 2))
        return k * (1 + sum([constraint.get_encoding_length() for constraint in self.constraints]))

    def make_mutation(self):
        mutation_weights = [
            (self._insert_constraint, settings.constraint_set_mutation_weights.insert_constraint),
            (self._remove_constraint, settings.constraint_set_mutation_weights.remove_constraint),
            (self._demote_constraint, settings.constraint_set_mutation_weights.demote_constraint),
            (self._insert_feature_bundle_phonotactic_constraint,
             settings.constraint_set_mutation_weights.insert_feature_bundle_phonotactic_constraint),
            (self._remove_feature_bundle_phonotactic_constraint,
             settings.constraint_set_mutation_weights.remove_feature_bundle_phonotactic_constraint),
            (self._augment_feature_bundle,
             settings.constraint_set_mutation_weights.augment_feature_bundle)
        ]

        weighted_mutation_function_list = get_weighted_list(mutation_weights)
        return choice(weighted_mutation_function_list)()

    def _remove_constraint(self):
        logger.debug("In _remove_constraint")
        if len(self.constraints) > settings.min_constraints_in_constraint_set:
            removable_constraints = list(filter(lambda x: x.get_constraint_name() != "Faith", self.constraints))
            self.constraints.remove(choice(removable_constraints))
            return True
        else:  # cannot remove constraint, resulting constraint_set length will br beneath minimum length
            return False

    def _insert_feature_bundle_phonotactic_constraint(self):
        """
        insert a feature bundle in a Phonotactic constraint
        """
        logger.debug("In _insert_feature_bundle_phonotactic_constraint")
        phonotactic_constraints = list(filter(lambda x: x.get_constraint_name() == "Phonotactic", self.constraints))
        if not phonotactic_constraints:
            return False  # there no phonotactic constraints to update
        if choice(phonotactic_constraints).insert_feature_bundle():
            return True
        return False  # augment_constraint did not succeed

    def _remove_feature_bundle_phonotactic_constraint(self):
        """
        removes a feature bundle from a Phonotactic constraint
        """
        logger.debug("In _remove_feature_bundle_phonotactic_constraint")
        phonotactic_constraints = list(filter(lambda x: x.get_constraint_name() == "Phonotactic", self.constraints))
        if not phonotactic_constraints:
            return False  # there no phonotactic constraints to update
        if choice(phonotactic_constraints).remove_feature_bundle():
            return True
        return False  # augment_constraint did not succeed

    def _augment_feature_bundle(self):
        logger.debug("In _augment_feature_bundle")
        augmentable_constraints = list(filter(lambda x: x.get_constraint_name() != "Faith", self.constraints))
        if augmentable_constraints:
            if choice(augmentable_constraints).augment_feature_bundle():
                return True
            else:  # augment_feature_bundle did not succeed
                return False

    def _demote_constraint(self):
        """
        The highest-ranking constraint is at index 0
        """
        logger.debug("In _demote_constraint")

        if len(self.constraints) <= 1:
            return False

        if DEMOTE_CASHING_FLAG:
            transducer = pickle.loads(pickle.dumps(self.get_transducer(), -1))

        index_of_demotion = randrange(len(self.constraints) - 1)  # index of a random constraint
        i = index_of_demotion  # (which is not the lowest ranked)
        j = index_of_demotion + 1  # index of the constraint lower by 1
        self.constraints[i], self.constraints[j] = self.constraints[j], self.constraints[i]  # swap places

        if DEMOTE_CASHING_FLAG:
            transducer.swap_weights_on_arcs(index_of_demotion, index_of_demotion + 1)
            constraint_set_transducers[str(self)] = transducer

        return True

    def _insert_constraint(self):
        logger.debug("In _insert_constraint")
        if len(self.constraints) >= settings.max_constraints_in_constraint_set:
            return False
        mutation_weights_for_insert = [
            (DepConstraint, settings.constraint_insertion_weights.dep),
            (MaxConstraint, settings.constraint_insertion_weights.max),
            (IdentConstraint, settings.constraint_insertion_weights.ident),
            (PhonotacticConstraint, settings.constraint_insertion_weights.phonotactic),
            (TieredLocalConstraint, settings.constraint_insertion_weights.tiered)
        ]

        weighted_constraint_class_for_insert = get_weighted_list(mutation_weights_for_insert)

        new_constraint_class = choice(weighted_constraint_class_for_insert)
        new_constraint = new_constraint_class.generate_random(self.feature_table)
        index_of_insertion = randrange(len(self.constraints) + 1)
        if new_constraint in self.constraints:  # newly generated constraint is already in constraint_set
            return False
        self.constraints.insert(index_of_insertion, new_constraint)
        return True

    def get_transducer(self):
        constraint_set_key = str(self)

        if constraint_set_key in constraint_set_transducers:
            return constraint_set_transducers[constraint_set_key]

        transducer = self._make_transducer()
        constraint_set_transducers[constraint_set_key] = transducer
        return transducer

    def _make_transducer(self):
        if len(self.constraints) == 1:  # if there is only on constraint in the
            # constraint set there is no need to intersect
            return pickle.loads(pickle.dumps(self.constraints[0].get_transducer(), -1))

        constraints_transducers = [constraint.get_transducer() for constraint in self.constraints]
        return Transducer.intersection(*constraints_transducers)


def _parse_bundle(bundle_string):
    # [+stop, -voice]  -> {"stop": "+", "voice": "-"}
    # [+syll]  - > {"syll": "+}
    bundle_dict = dict()

    if bundle_string.count("[") > 0:
        bundle_string = bundle_string[1:-1]  # remove surrounding []
    features = bundle_string.split(", ")

    for feature_string in features:
        bundle_dict[feature_string[1:]] = feature_string[0]
    return bundle_dict


def _parse_bundle_list(bundle_list_string):
    #  [[+stop, -voice][+syll]] -> [{"stop": "+", "voice": "-"}, {"syll": "+}]
    bundle_list = list()

    if bundle_list_string == "[]":
        return list()

    bundle_list_string = bundle_list_string[1:-1]  # remove surrounding []
    bundle_list_string = bundle_list_string.replace("][", "]|[")  # [+stop, -voice][+syll] -> [+stop, -voice]|[+syll]

    for bundle_string in bundle_list_string.split("|"):
        bundle_list.append(_parse_bundle(bundle_string))

    return bundle_list


def _parse_constraint(constraint_string):
    constraint_dict = dict()
    constraint_string = constraint_string.replace("[", "|[", 1)
    split_ = constraint_string.split("|")
    constraint_name = split_[0]
    constraint_bundle_list = split_[1]

    constraint_dict["type"] = constraint_name
    constraint_dict["bundles"] = _parse_bundle_list(constraint_bundle_list)

    return constraint_dict
