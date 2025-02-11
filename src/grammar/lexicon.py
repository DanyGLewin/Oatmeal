# Python2 and Python 3 compatibility:
from __future__ import absolute_import, division, print_function, unicode_literals

import codecs
import logging
from ast import literal_eval
from math import log, ceil
from random import choice, randint

from src.exceptions import GrammarError
from src.grammar.features.feature_table import FeatureTable, Segment, NULL_SEGMENT, JOKER_SEGMENT
from src.models.otml_configuration import settings
from src.models.transducer import CostVector, Arc, State, Transducer
from src.utils.randomization_tools import get_weighted_list

DEFAULT_LEX_CATEGORY = "default"

logger = logging.getLogger(__name__)

word_transducers = dict()


class Word:
    __slots__ = ["word_string", "feature_table", "segments"]

    def __init__(self, word_string: str, feature_table: FeatureTable):
        """
        word_string and segment should be in sync at any time
        """  # TODO: consider adding the lexical category here
        self.word_string: str = word_string
        self.feature_table: FeatureTable = feature_table
        self.segments: list[Segment] = [Segment(char, self.feature_table) for char in self.word_string]

    def __str__(self):
        return self.word_string

    def change_segment(self):
        """changing the word_string and therefore the segments composing it
           and making sure the new segment is not identical to segment being replaced"""
        logging.debug("change_segment")
        word_string_list = list(self.word_string)  # Making a mutable list from immutable string
        index_of_change = randint(0, len(self.word_string) - 1)
        old_segment = word_string_list[index_of_change]

        segment_options_list = self.feature_table.get_alphabet()
        segment_options_list.remove(
            old_segment)  # Making sure that the new segment is not identical to segment being replaced

        if not segment_options_list:  # there are no change candidates
            return False

        new_segment = choice(segment_options_list)
        word_string_list[index_of_change] = new_segment
        new_word_string = ''.join(word_string_list)
        self._set_word_string(new_word_string)
        return True

    @staticmethod
    def is_appropriate(word_string):
        # for forbidden_sequence in ["'p", "'t", "'k"]:
        #     if forbidden_sequence in word_string:
        #         return False
        return True

    def insert_segment(self, segment_to_insert):
        logging.debug("insert_segment")
        old_word_string = self.word_string
        index_of_insertion = randint(0, len(self.word_string))
        new_word_string = self.word_string[:index_of_insertion] + segment_to_insert + \
                          self.word_string[index_of_insertion:]

        if self.is_appropriate(new_word_string):
            self._set_word_string(new_word_string)
            # logger.info("insert_segment: put {} in {} (at position {}) ".format(segment_to_insert, new_word_string,
            #                                                               index_of_insertion))
            return True
        else:
            return False

    def delete_segment(self):
        logging.debug("delete_segment")
        old_word_string = self.word_string
        index_of_deletion = randint(0, len(self.word_string) - 1)
        new_word_string = self.word_string[:index_of_deletion] + self.word_string[index_of_deletion + 1:]
        if not self.is_appropriate(new_word_string):
            return False
        self._set_word_string(new_word_string)
        # print(f"delete segment: {old_word_string} -> {new_word_string}")
        return True

    def _set_word_string(self, new_word_string):
        self.word_string = new_word_string
        self.segments = [Segment(char, self.feature_table) for char in self.word_string]

    def get_transducer(self):
        word_key = str(self)
        if word_key in word_transducers:
            return word_transducers[word_key]
        else:
            transducer = self._make_transducer()
            word_transducers[word_key] = transducer
            return transducer

    def _make_transducer(self):
        segments = self.feature_table.get_segments()
        transducer = Transducer(segments, length_of_cost_vectors=0)
        word_segments = self.get_segments()
        n = len(self.word_string)
        states = [State("q{}".format(i), i) for i in range(n + 1)]
        for i, state in enumerate(states):
            transducer.add_state(state)
            transducer.add_arc(Arc(state, NULL_SEGMENT, JOKER_SEGMENT, CostVector.get_empty_vector(), state))
            if i != n:
                transducer.add_arc(
                    Arc(states[i], word_segments[i], JOKER_SEGMENT, CostVector.get_empty_vector(), states[i + 1]))

        transducer.initial_state = states[0]
        transducer.add_final_state(states[n])
        return transducer

    def get_encoding_length(self):
        return sum(segment.get_encoding_length() for segment in self.get_segments()) + 1

    def get_segments(self):
        return self.segments

    @staticmethod
    def clear_caching():
        global word_transducers
        word_transducers = dict()

    def __str__(self):
        return self.word_string

    def __len__(self):
        return len(self.word_string)

    def __eq__(self, other):
        return self.word_string == other.word_string

    def __hash__(self):
        return hash(self.word_string)


class Lexicon:

    def __init__(self, words: list[str], feature_table):
        """
        input_words is either a list of words or a file than contains a list of words
        """
        if len(words) == 0:
            raise GrammarError("Lexicon must contain at least one word")
        self.words: list[Word] = [Word(word_string, feature_table) for word_string in words]
        self.feature_table: FeatureTable = feature_table

    def __str__(self):
        if settings.log_lexicon_words:
            return (f"Lexicon (energy {self.get_encoding_length()}): {len(self.words)} words {[str(word) for word in self.words]} "
                    f"and {self._get_number_of_segments()} segments in total")
        else:
            return f"Lexicon, number of words: {len(self.words)}, number of segments: {self._get_number_of_segments()}"

    # we can optimize this by creating dict
    def __getitem__(self, item):
        return self.words[item].get_segments()

    def __len__(self):
        return len(self.words)

    def make_mutation(self):
        """
        rtype: boolean - the mutation success
        """
        mutation_weights = [(self._insert_segment, settings.lexicon_mutation_weights.insert_segment),
                            (self._delete_segment, settings.lexicon_mutation_weights.delete_segment),
                            (self._change_segment, settings.lexicon_mutation_weights.change_segment)]

        weighted_mutation_function_list = get_weighted_list(mutation_weights)
        return choice(weighted_mutation_function_list)()

    def _change_segment(self):
        return choice(self.words).change_segment()

    def _insert_segment(self):
        segment_to_insert = self.feature_table.get_random_segment()
        n = len(self.words)
        index_of_word_to_change = randint(0, n)
        if index_of_word_to_change == n:
            w = Word(segment_to_insert, self.feature_table)  # create a new monosegmental word
            self.words.append(w)
            return True
        else:
            return self.words[index_of_word_to_change].insert_segment(segment_to_insert)

    def _delete_segment(self):
        try:
            selected_word = choice(self.words)
        except IndexError:
            pass
        if len(selected_word) == 1:
            self.words.remove(selected_word)
            return True
        else:
            return selected_word.delete_segment()

    def get_encoding_length(self):
        if settings.restriction_on_alphabet:
            alphabet_size = len(self.feature_table.get_alphabet())
            restricted_alphabet_size = len(self.get_distinct_segments())
            number_of_bits = ceil(log(alphabet_size + 1, 2))
            restriction_set_length = number_of_bits * (restricted_alphabet_size + 1)
            number_of_bits = ceil(log(restricted_alphabet_size + 1, 2))
            lexicon_length = number_of_bits * (sum((len(word) + 1) for word in self.words) + 1)
            return restriction_set_length + lexicon_length
        else:
            number_of_bits = 2
            return number_of_bits * (sum(word.get_encoding_length() for word in self.words) + 1)

    def get_distinct_segments(self):
        distinct_segments = set()
        for word in self.words:
            distinct_segments = distinct_segments | set(word.get_segments())
        return distinct_segments

    def get_words(self):
        return self.words

    def get_number_of_distinct_words(self):
        return len(set(self.words))

    def _get_number_of_segments(self):
        return sum([len(word) for word in self.words])


def get_words_from_file(corpus_file_name):
    with codecs.open(corpus_file_name, "r") as f:
        corpus_string = f.read()

    if "[" not in corpus_string:
        words = corpus_string.split()
    else:
        words = literal_eval(corpus_string)

    return words


def parse_words_per_category_from_file(corpus_file_name):
    with codecs.open(corpus_file_name, "r", encoding="utf-8") as f:
        corpus_string = f.read()

    if "[" in corpus_string:
        raise NotImplementedError()

    words_raw = corpus_string.split()
    words_split = [word.split("_") for word in words_raw]
    categories = {word[1] for word in words_split if len(word) > 1}
    words_per_category = {cat: [word[0] for word in words_split if len(word) > 1 and word[1] == cat] for cat in
                          categories}
    words_per_category[DEFAULT_LEX_CATEGORY] = [word[0] for word in words_split if len(word) == 1]
    return words_per_category
