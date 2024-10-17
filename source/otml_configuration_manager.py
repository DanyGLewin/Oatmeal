#Python2 and Python 3 compatibility:
from __future__ import absolute_import, division, print_function, unicode_literals

from configuration_manager import ConfigurationManager
from copy import deepcopy

from six import StringIO

from source.errors import OtmlConfigurationError
from unicode_mixin import UnicodeMixin


CONFIGURATION_DICTIONARY_FIELDS = [
    "LEXICON_MUTATION_WEIGHTS",
    "CONSTRAINT_SET_MUTATION_WEIGHTS",
    "CONSTRAINT_INSERTION_WEIGHTS",
]


class OtmlConfigurationManager(ConfigurationManager, UnicodeMixin): #
    def __init__(self, json_str):
        ConfigurationManager.__init__(self, json_str, json_decoder=OtmlConfigurationManager.json_decoder)
        self.initial_configurations_dict = deepcopy(self.configurations)
        self.initial_derived_configurations_dict = deepcopy(self.derived_configurations)

    def reset_to_original_configurations(self):
        self.configurations = deepcopy(self.initial_configurations_dict)
        self.derived_configurations = deepcopy(self.initial_derived_configurations_dict)


    @staticmethod
    def json_decoder(string):
        CONSTANTS = {
            "True": True,
            "False": False,
            "INF": float('inf')
        }
        if string in CONSTANTS:
            return CONSTANTS[string]

        if "**" in string: #convert "x**y" literal to x**y
            x, y = string.split("**")
            return int(x) ** int(y)

        return string

    def validate_configurations(self):
        _validate_required_dictionary_fields(self.configurations)

        _check_weights_total_is_not_zero(
            self.configurations["LEXICON_MUTATION_WEIGHTS"],
             self.configurations["CONSTRAINT_SET_MUTATION_WEIGHTS"],
         )
        _check_weights_total_is_not_zero(self.configurations["CONSTRAINT_INSERTION_WEIGHTS"])

        _validate_not_implemented_features(self.configurations)

        _validate_feature_number(self.configurations)

        #TODO link between ["LEXICON_MUTATION_WEIGHTS"]["change_segment"] and ["ALLOW_CANDIDATES_WITH_CHANGED_SEGMENTS"]

    def derive_configurations(self):
        lexicon_mutation_weights = self.configurations["LEXICON_MUTATION_WEIGHTS"]
        constraint_set_mutation_weights = self.configurations["CONSTRAINT_SET_MUTATION_WEIGHTS"]
        constraint_insertion_weights = self.configurations["CONSTRAINT_INSERTION_WEIGHTS"]

        self.derived_configurations["LEXICON_SELECTION_WEIGHT"] = sum(lexicon_mutation_weights.values())
        self.derived_configurations["CONSTRAINT_SET_SELECTION_WEIGHT"] = sum(constraint_set_mutation_weights.values())

        self.derived_configurations["INSERT_SEGMENT_WEIGHT"] = lexicon_mutation_weights["insert_segment"]
        self.derived_configurations["DELETE_SEGMENT_WEIGHT"] = lexicon_mutation_weights["delete_segment"]
        self.derived_configurations["CHANGE_SEGMENT_WEIGHT"] = lexicon_mutation_weights["change_segment"]

        self.derived_configurations["INSERT_CONSTRAINT_WEIGHT"] = constraint_set_mutation_weights["insert_constraint"]
        self.derived_configurations["REMOVE_CONSTRAINT_WEIGHT"] = constraint_set_mutation_weights["remove_constraint"]
        self.derived_configurations["DEMOTE_CONSTRAINT_WEIGHT"] = constraint_set_mutation_weights["demote_constraint"]
        self.derived_configurations["INSERT_FEATURE_BUNDLE_PHONOTACTIC_CONSTRAINT_WEIGHT"] = constraint_set_mutation_weights["insert_feature_bundle_phonotactic_constraint"]
        self.derived_configurations["REMOVE_FEATURE_BUNDLE_PHONOTACTIC_CONSTRAINT_WEIGHT"] = constraint_set_mutation_weights["remove_feature_bundle_phonotactic_constraint"]
        self.derived_configurations["AUGMENT_FEATURE_BUNDLE_WEIGHT"] = constraint_set_mutation_weights["augment_feature_bundle"]

        self.derived_configurations["DEP_WEIGHT_FOR_INSERT"] = constraint_insertion_weights["Dep"]
        self.derived_configurations["MAX_WEIGHT_FOR_INSERT"] = constraint_insertion_weights["Max"]
        self.derived_configurations["IDENT_WEIGHT_FOR_INSERT"] = constraint_insertion_weights["Ident"]
        self.derived_configurations["PHONOTACTIC_WEIGHT_FOR_INSERT"] = constraint_insertion_weights["Phonotactic"]

    def __unicode__(self):
        values_str_io = StringIO()
        print("Otml configuration manager with:", end="\n", file=values_str_io)
        for (key, value) in sorted(self.configurations.items()):
            value_string = ""
            if type(value) == dict:
                for (secondary_key, secondary_value) in self.configurations[key].items():

                    value_string += (len(key)+2) * " " + "{}: {}\n".format(secondary_key, secondary_value)
                value_string = value_string.strip()
            else:
                value_string = str(value)
            print("{}: {}".format(key, value_string), end="\n", file=values_str_io)

        return values_str_io.getvalue().strip()


def _check_weight_values_validity(weight_dict):
    for weight in weight_dict.values():
        if not isinstance(weight, int) or weight < 0:
            raise OtmlConfigurationError("Illegal weight", {"weight": weight})


def _check_weights_total_is_not_zero(*weight_dicts):
    total = 0
    for weight_dict in weight_dicts:
        total = total + sum(weight_dict.values())
    if total == 0:
        raise OtmlConfigurationError("Sum of weights is zero")

#
def _validate_required_dictionary_fields(configurations):
    for dictionary_configuration_name in CONFIGURATION_DICTIONARY_FIELDS:
        if type(configurations[dictionary_configuration_name]) != dict:
            raise OtmlConfigurationError("Required field should be a dictionary", {"field": dictionary_configuration_name})

    for dictionary_configuration_name in CONFIGURATION_DICTIONARY_FIELDS:
        _check_weight_values_validity(configurations[dictionary_configuration_name])


def _validate_not_implemented_features(configurations):
    if configurations["CONSTRAINT_SET_MUTATION_WEIGHTS"]["augment_feature_bundle"]:
        raise NotImplementedError
    if configurations["LEXICON_MUTATION_WEIGHTS"]["change_segment"]:
        raise NotImplementedError
    if configurations["ALLOW_CANDIDATES_WITH_CHANGED_SEGMENTS"]:
        raise NotImplementedError

def _validate_feature_number(configurations):
    if (configurations["MIN_FEATURE_BUNDLES_IN_PHONOTACTIC_CONSTRAINT"]
            > configurations["INITIAL_NUMBER_OF_FEATURES"]
    ):
        raise OtmlConfigurationError("MIN_FEATURE_BUNDLES_IN_PHONOTACTIC_CONSTRAINT is bigger then INITIAL_NUMBER_OF_FEATURES")