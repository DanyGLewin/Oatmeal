import json
import os
import sys
from io import StringIO
from typing import Any, Self

from pydantic import BaseModel, field_validator, model_validator, ConfigDict, NonNegativeInt

from src.exceptions import OtmlConfigurationError
from src.models.singelton import Singleton

CONFIG_FILE_NAME = "config.json"

DATA_FILES = {
    "config_file": "config.json",
    "constraints_file": "constraints.json",
    "features_file": "features.json",
    "corpus_file": "corpus.txt",
}


class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",  # disallow extra fields
        validate_assignment=True,  # run validations after every value assignment
    )

    def dict(self, *args, **kwargs) -> dict[str, Any]:
        return self.model_dump(*args, **kwargs)

    def items(self):
        return self.dict().items()

    def keys(self):
        return self.dict().keys()

    def values(self):
        return self.dict().values()

    def __repr__(self):
        buffer = StringIO()
        name = self.__class__.__name__
        buffer.write(f"{name}:\n")
        for key, val in self.items():
            buffer.write(f"\t{key}: {val}\n")
        return buffer.getvalue()


class Weights(Model):
    @property
    def sum(self) -> int:
        return sum(self.values())

    @field_validator("*")
    @classmethod
    def parse_int(cls, value):
        if type(value) is int:
            return value
        return int(value)


class LexiconMutationWeights(Weights):
    insert_segment: NonNegativeInt
    delete_segment: NonNegativeInt
    change_segment: NonNegativeInt


class ConstraintSetMutationWeights(Weights):
    insert_constraint: NonNegativeInt
    remove_constraint: NonNegativeInt
    demote_constraint: NonNegativeInt
    insert_feature_bundle_phonotactic_constraint: NonNegativeInt
    remove_feature_bundle_phonotactic_constraint: NonNegativeInt
    augment_feature_bundle: NonNegativeInt


class ConstraintInsertionWeights(Weights):
    dep: NonNegativeInt
    max: NonNegativeInt
    ident: NonNegativeInt
    phonotactic: NonNegativeInt
    tiered: NonNegativeInt


class OtmlConfiguration(Model, Singleton):
    simulation_name: str

    config_folder: str
    config_file: str
    constraints_file: str
    target_constraints_file: str | None = None
    features_file: str
    corpus_file: str

    log_file_name: str
    log_lexicon_words: bool

    corpus_duplication_factor: int

    allow_candidates_with_changed_segments: bool

    restriction_on_alphabet: bool

    max_constraints_in_constraint_set: float | int
    min_constraints_in_constraint_set: int
    max_feature_bundles_in_phonotactic_constraint: int
    min_feature_bundles_in_phonotactic_constraint: int
    max_features_in_bundle: float | int
    initial_number_of_features: int
    initial_number_of_bundles_in_phonotactic_constraint: int
    random_position_for_feature_bundle_insertion_in_phonotactic: bool
    random_position_for_feature_bundle_removal_in_phonotactic: bool

    lexicon_mutation_weights: LexiconMutationWeights
    constraint_set_mutation_weights: ConstraintSetMutationWeights
    constraint_insertion_weights: ConstraintInsertionWeights

    initial_temp: int
    threshold: float
    cooling_factor: float
    debug_logging_interval: int
    clear_modules_caching_interval: int
    steps_limitation: int | float

    random_seed: bool
    seed: int

    data_encoding_length_multiplier: int
    grammar_encoding_length_multiplier: int

    @field_validator("*", mode="before")
    @classmethod
    def _parse_json_field(cls, raw):
        if type(raw) is not str:
            return raw
        try:
            if raw.casefold() == "inf":
                return sys.maxsize
            if "**" in raw:
                x, y = raw.split("**")
                return float(x) ** int(y)
        except ValueError:
            raise OtmlConfigurationError(f"Invalid config.json value", {"value": raw})
        return raw

    @classmethod
    def load(cls, config_folder_path: str) -> None:
        absolute_folder_path = os.path.join(os.getcwd(), config_folder_path)

        config_dict = {"config_folder": absolute_folder_path}
        for field_name, file_name in DATA_FILES.items():
            config_dict[field_name] = os.path.join(absolute_folder_path, file_name)

        with open(config_dict["config_file"], "r") as f:
            config_dict.update(json.load(f))

        config = cls.model_validate(config_dict)
        global _settings
        _settings = config

    def reset(self) -> Self:
        """
        returns a copy of the configuration's original state
        """
        return self.load(self.config_folder)

    def update(self, **updates) -> Self:
        """
        returns a copy of the configuration, updating the values per the given kwargs
        """
        return self.model_copy(update=updates, deep=True)

    @model_validator(mode="after")
    def _validate_weights(self):
        if self.lexicon_mutation_weights.sum + self.constraint_set_mutation_weights.sum == 0:
            raise OtmlConfigurationError("Sum of mutation weights is zero")

        if self.constraint_insertion_weights.sum == 0 and self.constraint_set_mutation_weights.insert_constraint > 0:
            raise OtmlConfigurationError("Sum of insertion weights is zero")
        return self

    @model_validator(mode="after")
    def _validate_not_implemented_features(self):
        for value in (
                self.constraint_set_mutation_weights.augment_feature_bundle,
                self.lexicon_mutation_weights.change_segment,
                self.allow_candidates_with_changed_segments,
        ):
            if value:
                raise NotImplementedError
        return self

    @model_validator(mode="after")
    def _validate_feature_number(self):
        if self.min_feature_bundles_in_phonotactic_constraint > self.initial_number_of_features:
            raise OtmlConfigurationError(
                "MIN_FEATURE_BUNDLES_IN_PHONOTACTIC_CONSTRAINT is bigger then INITIAL_NUMBER_OF_FEATURES",
            )
        return self

    @model_validator(mode="after")
    def _validate_change_segment_has_logical_weight(self):  # the logic for these isn't actually implemented yet
        if self.lexicon_mutation_weights.change_segment ^ self.allow_candidates_with_changed_segments:
            raise OtmlConfigurationError(
                "Either neither or both of `lexicon_mutation_weights.change_segment` and `allow_candidates_with_changed_segments` must be positive",
            )
        return self

    @model_validator(mode="after")
    def _validate_min_constraints_in_constraint_set(self):
        if self.min_constraints_in_constraint_set < 1:
            raise OtmlConfigurationError(
                "Min constraint set size cannot be zero (because FAITH constraints always exist)")
        return self


# from here on: code to let us easily access configs in the project by doing
# >>> from source.otml_configuration import settings
# >>> settings.[any config field]
# TODO: see if we can make this less ugly, or move it to a separate file

_settings: OtmlConfiguration | None = None


class LazySettings:
    def __getattr__(self, item):
        if _settings is None:
            raise OtmlConfigurationError("Settings have not been initialized. Call 'OtmlConfiguration.load' first.")
        return getattr(_settings, item)


settings: OtmlConfiguration = LazySettings()
