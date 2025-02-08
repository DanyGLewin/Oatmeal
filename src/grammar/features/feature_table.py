import codecs
import json
import logging
import os
from copy import deepcopy
from io import StringIO
from random import choice
from typing import Any

from six import iterkeys, string_types, integer_types

from src.exceptions import FeatureParseError, UnknownFeatureError
from src.grammar.features.feature_list import FeatureList

logger = logging.getLogger(__name__)


class FeatureTable:
    def __init__(self, feature_table_raw: dict[str, Any]):
        self._segment_to_feature_dict: dict[str, dict[str, str]] = dict()
        self._features: FeatureList = FeatureList.model_validate(dict(features=feature_table_raw["feature"]))
        self._segments: list[Segment] = list()

        self._index_to_feature: dict = dict()

        for i, feature in enumerate(self._features):
            self._index_to_feature[i] = feature

        for symbol in feature_table_raw["feature_table"].keys():
            feature_values = feature_table_raw["feature_table"][symbol]
            if len(feature_values) != len(self._features):
                raise FeatureParseError("Mismatch in number of features for segment {0}".format(symbol))
            symbol_feature_dict = dict()
            for i, feature_value in enumerate(feature_values):
                feature = self._features[i]
                if feature_value not in feature.values:
                    raise FeatureParseError("Illegal feature was found for segment {0}".format(symbol))
                symbol_feature_dict[feature.label] = feature_value
            self._segment_to_feature_dict[symbol] = symbol_feature_dict

        for symbol in self.get_alphabet():
            self._segments.append(Segment(symbol, self))

    def __repr__(self):
        return str(self)

    def __str__(self):
        return self.get_human_readable_feature_table()

    def __getitem__(self, item):
        if isinstance(item, string_types):
            result = self._segment_to_feature_dict.get(item)
            if result is None:
                raise UnknownFeatureError(f"{item} is invalid")
            return self._segment_to_feature_dict[item]
        if isinstance(item, integer_types):  # TODO this should support an ordered access to the feature table.
            #  is this a good implementation?
            return self._segment_to_feature_dict[self._index_to_feature[item]]
        else:
            segment, feature = item
            return self._segment_to_feature_dict[segment][feature]

    @classmethod
    def load(cls, feature_table_filename: str):
        """
        Load feature table from a file.

        Args:
            feature_table_filename: filename

        Returns:
            FeatureTable: a new feature table instance
        """
        file = codecs.open(feature_table_filename, "r")
        if os.path.splitext(feature_table_filename)[1] == ".json":
            feature_table_dict = json.load(file)
        else:
            feature_table_dict = FeatureTable._get_feature_table_dict_form_csv(file)
        file.close()
        return cls(feature_table_dict)

    @staticmethod
    def _get_feature_table_dict_form_csv(file):
        """
        Parse feature table from a CSV file.
        """
        feature_table_dict = dict()
        feature_table_dict["feature"] = list()
        feature_table_dict["feature_table"] = dict()
        lines = file.readlines()
        lines = [x.strip() for x in lines]
        feature_label_list = lines[0][1:].split(",")  # first line, ignore first comma (,cons, labial..)
        feature_table_dict["feature"] = list()
        for label in feature_label_list:
            feature_table_dict["feature"].append({"label": label, "values": ["-", "+"]})

        for line in lines[1:]:
            values_list = line.split(",")
            feature_table_dict["feature_table"][values_list[0]] = values_list[1:]

        return feature_table_dict

    def get_number_of_features(self) -> int:
        return len(self._features)

    def get_features(self) -> set[str]:
        return self._features.labels

    def get_random_feature(self) -> dict[str, Any]:
        feature_label = choice(list(self.get_features()))
        return {feature_label: self.get_random_value(feature_label)}

    def get_random_value(self, feature: int) -> str:
        return choice(self._features[feature])

    def get_alphabet(self) -> list[str]:
        return list(iterkeys(self._segment_to_feature_dict))

    def get_segments(self) -> list['Segment']:
        """Returns a ***copy*** of the segments' list"""
        return deepcopy(self._segments)

    def get_random_segment(self) -> str:
        return choice(self.get_alphabet())

    def get_ordered_feature_vector(self, char) -> list[str]:
        return [self[char][str(feature)] for feature in self._index_to_feature.values()]

    def is_valid_feature(self, feature_label) -> bool:
        """Validate that the label exists in features."""
        return feature_label in self._features

    def _is_valid_symbol(self, symbol) -> bool:
        """Validate that the symbol exists in the segment to feature dictionary."""
        return symbol in self._segment_to_feature_dict

    def get_human_readable_feature_table(self):
        values_str_io = StringIO()
        print(f"Feature Table with {len(self._features)} features and {len(self._segments)} segments:",
              file=values_str_io)

        print("{:20s}".format("Segment/Feature"),
              end="",
              file=values_str_io)

        for i in range(len(self._index_to_feature)):
            print("{:10s}".format(str(self._index_to_feature[i])), end="", file=values_str_io)

        print("", file=values_str_io)  # new line

        for segment in sorted(iterkeys(self._segment_to_feature_dict)):
            print("{:20s}".format(segment), end="", file=values_str_io)

            for i in range(len(self._index_to_feature)):
                feature = str(self._index_to_feature[i])
                print("{:10s}".format(self._segment_to_feature_dict[segment][feature]), end="", file=values_str_io)
            print("", file=values_str_io)

        return values_str_io.getvalue()


class Segment:
    def __init__(self, symbol: str, feature_table: FeatureTable | None = None):
        self.symbol: str = symbol  # JOKER and NULL segments need feature_table=None

        if feature_table:
            self.feature_table: FeatureTable = feature_table
            self.feature_dict: dict[str, str] = feature_table[symbol]

        self.hash = hash(self.symbol)

    @staticmethod
    def intersect(x, y):
        """Intersect two segments, a segment and a set, or two sets.

        :type x: Segment or set
        :type y: Segment or set
        """
        if isinstance(x, set):
            x, y = y, x  # if x is a set then maybe y is a segment, switch between them so that
            # Segment.__and__ will take effect
        return x & y

    def __and__(self, other):
        """Based on ```(17) symbol unification```(Riggle, 2004)

        :type other: Segment or set
        """
        if self == JOKER_SEGMENT:
            return other
        elif isinstance(other, set):
            if self.symbol in other:
                return self
        else:
            if self == other:
                return self
            elif other == JOKER_SEGMENT:
                return self
        return None

    def __eq__(self, other):
        if other is None:
            return False
        return self.symbol == other.symbol

    def __hash__(self):
        return self.hash

    def __str__(self):  # TODO: check if this gives the constraints order
        if hasattr(self, "feature_table"):
            values_str_io = StringIO()
            ordered_feature_vector = self.feature_table.get_ordered_feature_vector(self.symbol)

            for value in ordered_feature_vector:
                print(value, end=", ", file=values_str_io)
            return "Segment {0}[{1}]".format(self.symbol, values_str_io.getvalue()[:-2])
        else:
            return self.symbol

    def __getitem__(self, item):
        return self.feature_dict[item]

    def get_encoding_length(self) -> int:
        return len(self.feature_dict)

    def has_feature_bundle(self, feature_bundle) -> bool:
        return all(item in self.feature_dict.items() for item in feature_bundle.get_feature_dict().items())

    def get_symbol(self) -> str:
        return self.symbol


# Special segments - required for transducer construction
NULL_SEGMENT = Segment("-")
JOKER_SEGMENT = Segment("*")
