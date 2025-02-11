# Python2 and Python 3 compatibility:
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import pickle
import sys
from math import ceil, log

from src.grammar.grammar import Grammar
from src.models.otml_configuration import settings

logger = logging.getLogger(__name__)


class TraversableGrammarHypothesis:

    def __init__(self, grammar: Grammar, data: list[str]):
        self.grammar: Grammar = grammar
        self.data: list[str] = data
        self.data_parse: dict[str, set[tuple[str, int]]] | None = None

        self.grammar_energy: int = sys.maxsize
        self.data_energy: int = sys.maxsize
        self.combined_energy: int = sys.maxsize

    def update_energy(self) -> int:
        data_length = self.get_data_length_given_grammar()
        grammar_length = self.grammar.get_encoding_length()
        data_multiplier = settings.data_encoding_length_multiplier
        grammar_multiplier = settings.grammar_encoding_length_multiplier

        self.grammar_energy = grammar_length * grammar_multiplier
        self.data_energy = data_length * data_multiplier
        self.combined_energy = self.grammar_energy + self.data_energy
        return self.combined_energy

    def get_data_length_given_grammar(self) -> int:
        """
        data_parse_dict is a dictionary with:
            keys: words of the data;
            values: sets of parses of a word [parse = a pair (input, number_of_outputs)]

        """
        data_parse_dict = self.parse_data()

        for word in self.data:
            if not data_parse_dict[word]:  # if data_parse_dict[word] is the empty set
                return sys.maxsize

        input_choice_length = ceil(log(self.grammar.lexicon.get_number_of_distinct_words(), 2))

        total_length = 0
        for word in self.data:
            total_length += min([self.encode_output(parse, input_choice_length) for parse in data_parse_dict[word]])

        self.data_parse = data_parse_dict
        return total_length

    def get_recent_data_parse(self) -> str:
        if not self.data_parse:
            return "No data parsed"
        result = ""
        data_parse_with_string_keys = dict()
        for word in self.data_parse:
            data_parse_with_string_keys[str(word)] = self.data_parse[word]

        word_list = [word for word in data_parse_with_string_keys]
        word_list.sort(key=lambda item: (len(item), item))  # sort by length first and then alphabetically
        for output_word in word_list:
            parse_set = data_parse_with_string_keys[output_word]
            for parse in parse_set:
                input_word = parse[0]
                number_of_outputs = parse[1]
                if str(input_word) != output_word:
                    result += "{} --> {} ({}) # ".format(input_word, output_word, number_of_outputs)

        if len(result):
            result = result[:-3]  # remove final delimiter

        return result

    def get_recent_energy_signature(self) -> str:
        return f"Energy: {self.combined_energy:,} bits (Grammar = {self.grammar_energy:,}) + (Data = {self.data_energy:,})"

    def parse_data(self) -> dict[str, set[tuple[str, int]]]:
        """Parses Words

        :rtype: A dictionary that has the Words in data as keys and the values are sets of tuples. Each tuple
        contains (Word, int) which the Word is able to generate the Word in the key of the dictionary and
        the int is the number of outputs that the Word can generate.

        A word that not able to parsed will return an empty set in the value of the word
        entry in the dictionary.

        The number of outputs an input can generate is later used to calculate the probability of a word under
        the grammar.
        """
        data_parse = {word: set() for word in self.data}
        lexicon_word_set = set(self.grammar.lexicon.get_words())
        for word_in_lexicon in lexicon_word_set:
            outputs = self.grammar.generate(word_in_lexicon)  # outputs in a list of Words
            number_of_outputs = len(outputs)
            for output in outputs:
                if output in self.data:
                    parse = (word_in_lexicon, number_of_outputs)
                    data_parse[output].add(parse)
        return data_parse

    # @timeit
    @staticmethod
    def encode_output(parse: tuple[str, int], input_choice_length: int) -> int:
        input, number_of_outputs = parse
        output_choice_length = ceil(log(number_of_outputs, 2))
        return input_choice_length + output_choice_length

    def get_neighbor(self):
        new_hypothesis = self.get_hypothesis_copy()
        mutation_result = new_hypothesis.grammar.make_mutation()
        return mutation_result, new_hypothesis

    # @timeit
    def get_hypothesis_copy(self):
        grammar_copy = pickle.loads(pickle.dumps(self.grammar, -1))
        return TraversableGrammarHypothesis(grammar_copy, self.data)

    def __str__(self):
        return "Hypothesis with energy {0}".format(self.update_energy())
