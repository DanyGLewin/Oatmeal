# Python2 and Python 3 compatibility:
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
from random import choice

from six import iterkeys, StringIO

from src.exceptions import GrammarParseError
from src.exceptions import OtmlConfigurationError
from src.models.otml_configuration import settings

logger = logging.getLogger(__name__)


class FeatureBundle:
    __slots__ = ["feature_dict", "feature_table"]

    def __init__(self, feature_dict, feature_table):
        for feature in feature_dict.keys():
            if not feature_table.is_valid_feature(feature):
                raise GrammarParseError(f"Illegal feature: {feature}")

        self.feature_dict = feature_dict
        self.feature_table = feature_table

    def get_encoding_length(self):
        return 2 * len(self.feature_dict)

    def get_keys(self):
        return list(iterkeys(self.feature_dict))

    def get_feature_dict(self):
        return self.feature_dict

    def augment_feature_bundle(self):
        if len(self.feature_dict) < settings["MAX_FEATURES_IN_BUNDLE"]:
            all_feature_labels = self.feature_table.get_features()
            feature_labels_in_feature_bundle = iterkeys(self.feature_dict)
            available_feature_labels = list(set(all_feature_labels) - set(feature_labels_in_feature_bundle))
            if available_feature_labels:
                feature_label = choice(available_feature_labels)
                self.feature_dict[feature_label] = self.feature_table.get_random_value(feature_label)
                return True
        return False

    @classmethod
    def generate_random(cls, feature_table):
        if settings.initial_number_of_features > feature_table.get_number_of_features():
            raise OtmlConfigurationError("INITIAL_NUMBER_OF_FEATURES is bigger from number of available features")

        feature_dict = dict()
        available_feature_labels = list(feature_table.get_features())

        for i in range(settings.initial_number_of_features):
            feature_label = choice(available_feature_labels)
            feature_dict[feature_label] = feature_table.get_random_value(feature_label)
            available_feature_labels.remove(feature_label)
        return FeatureBundle(feature_dict, feature_table)

    def __eq__(self, other):
        return self.feature_dict == other.feature_dict

    def __str__(self):
        return str(self.feature_dict)

    def __getitem__(self, item):
        return self.feature_dict[item]

    # moved from constraint.py as-is, should probably be prettified
    def pretty_string(self, force_parentheses=False):
        str_io = StringIO()
        if len(self.feature_dict) > 1 or force_parentheses:
            print("[", file=str_io, end="")

        for i_feature, feature in enumerate(sorted(self.get_keys())):  # sorted to avoid differences in
            if i_feature != 0:  # implementations (esp between Py2 and # Py3) - tests
                print(", ", file=str_io, end="")
            print("{0}{1}".format(self[feature], feature), file=str_io, end="")

        if len(self.feature_dict) > 1 or force_parentheses:
            print("]", file=str_io, end="")
        return str_io.getvalue()