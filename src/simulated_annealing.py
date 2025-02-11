# Python2 and Python 3 compatibility:
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import os
import random
import re
import subprocess
import sys
import time
from datetime import timedelta
from math import exp
from random import choice

from src.grammar.constraint import Constraint
from src.grammar.constraint_set import ConstraintSet
from src.grammar.grammar import Grammar
from src.grammar.lexicon import Word
from src.models.otml_configuration import settings
from src.models.traversable_grammar_hypothesis import TraversableGrammarHypothesis

logger = logging.getLogger(__name__)

process_id = os.getpid()

_STARS = '*' * 10
_LINE_SEPARATOR = '-' * 80
HEADLINE_FORMAT = "{stars} {headline} {stars}"


class SimulatedAnnealing(object):

    def __init__(self, initial_hypothesis: TraversableGrammarHypothesis,
                 target_lexicon_indicator_function: int | None = None,
                 sample_target_lexicon: int | None = None,
                 sample_target_outputs: int | None = None,
                 target_energy: int | None = None):

        self.initial_hypothesis = initial_hypothesis
        self.current_hypothesis = initial_hypothesis
        self.target_lexicon_indicator_function = target_lexicon_indicator_function
        self.target_energy = target_energy

        # all these parameters are going to be set DURING RUN
        self.step = 0
        self.current_temperature = None
        self.threshold = None
        self.cooling_parameter = None
        self.current_hypothesis_energy = None
        self.neighbor_hypothesis = None
        self.neighbor_hypothesis_energy = None
        self.step_limitation = None
        self.number_of_expected_steps = None
        self.start_time = None
        self.previous_interval_time = None
        self.previous_interval_energy = None
        self.target_data = False
        self.sample_target_lexicon = None
        self.sample_target_outputs = None

        if sample_target_lexicon and sample_target_outputs:
            self.target_data = True
            self.sample_target_lexicon = sample_target_lexicon
            self.sample_target_outputs = sample_target_outputs

    def run(self) -> tuple[int, TraversableGrammarHypothesis]:
        """
        Run the simulated annealing.

        Returns:
            The number of steps taken and the final hypothesis.
        """
        self.before_loop()

        while (self.current_temperature > self.threshold) and (self.step != self.step_limitation):
            if (settings.debug_logging_interval) and (self.step % settings.debug_logging_interval == 0):
                print(f"{self._pretty_step_label()} - {self.current_hypothesis.grammar}")
            self.make_step()

        self._after_loop()
        return self.step, self.current_hypothesis

    # @timeit
    def make_step(self):
        self.step += 1
        self.current_temperature *= self.cooling_parameter

        self._check_for_intervals()

        mutation_result, neighbor_hypothesis = self.current_hypothesis.get_neighbor()
        if not mutation_result:
            return  # mutation failed - the neighbor hypothesis is the same as the current hypothesis

        self.neighbor_hypothesis = neighbor_hypothesis
        self.neighbor_hypothesis_energy = self.neighbor_hypothesis.update_energy()
        delta = self.neighbor_hypothesis_energy - self.current_hypothesis_energy

        if delta < 0:
            p = 1
        else:
            p = exp(-delta / self.current_temperature)
        if random.random() < p:
            logger.info("switch")
            self.current_hypothesis = self.neighbor_hypothesis
            self.current_hypothesis_energy = self.neighbor_hypothesis_energy
        else:
            logger.info("did not switch")

    def before_loop(self):
        self.start_time = time.time()
        self.previous_interval_time = self.start_time
        logger.info(f"Process Id: {process_id}")
        if not settings.seed:
            settings.seed = choice(range(1, 1000))
        random.seed(settings.seed)
        logger.info(settings)
        logger.info(self.current_hypothesis.grammar.feature_table)
        self.step_limitation = settings.steps_limitation
        self.number_of_expected_steps = min(self.step_limitation, self._calculate_num_of_steps())

        logger.info("Number of expected steps is: {:,}".format(self.number_of_expected_steps))
        self.current_hypothesis_energy = self.current_hypothesis.update_energy()
        if self.current_hypothesis_energy == sys.maxsize:
            raise ValueError("first hypothesis energy can not be INF")

        self._log_hypothesis_state()
        self.previous_interval_energy = self.current_hypothesis_energy
        self.current_temperature = settings.initial_temp
        self.threshold = settings.threshold
        self.cooling_parameter = settings.cooling_factor

    def _check_for_intervals(self):
        if settings.debug_logging_interval and not (self.step % settings.debug_logging_interval):
            self._debug_interval()
        if not self.step % settings.clear_modules_caching_interval:
            self.clear_modules_caching()

    def _debug_interval(self):
        current_time = time.time()
        logger.info(_LINE_SEPARATOR)
        percentage_completed = 100 * float(self.step) / float(self.number_of_expected_steps)
        logger.info("Step {0:,} of {1:,} ({2:.2f}%)".format(self.step, self.number_of_expected_steps,
                                                            percentage_completed))
        logger.info(_LINE_SEPARATOR)
        elapsed_time = current_time - self.start_time
        logger.info(f"Time from simulation start: {_pretty_runtime_str(elapsed_time)}")
        logger.info(f"Expected simulation time: {_pretty_runtime_str(elapsed_time * (100 / percentage_completed))}")
        logger.info(f"Current temperature: {self.current_temperature}")
        self._log_hypothesis_state()
        logger.info(
            f"Energy difference from last interval: {self.current_hypothesis_energy - self.previous_interval_energy}")
        self.previous_interval_energy = self.current_hypothesis_energy
        time_from_last_interval = current_time - self.previous_interval_time
        logger.info(f"Time from last interval: {_pretty_runtime_str(time_from_last_interval)}")
        logger.info(f"Time to finish based on current interval: {self.by_interval_time(time_from_last_interval)}")
        self.previous_interval_time = current_time

    def by_interval_time(self, time_from_last_interval):
        number_of_remaining_steps = self.number_of_expected_steps - self.step
        number_of_remaining_intervals = int(number_of_remaining_steps / settings.debug_logging_interval) + 1
        expected_time = number_of_remaining_intervals * time_from_last_interval
        return _pretty_runtime_str(expected_time)

    def _after_loop(self):
        current_time = time.time()
        logger.info(HEADLINE_FORMAT.format(stars=_STARS, headline="Final Hypothesis"))
        self._log_hypothesis_state()
        logger.info(f"simulated annealing runtime was: {_pretty_runtime_str(current_time - self.start_time)}")

    def _log_hypothesis_state(self):
        logger.info(f"Grammar with: {self.current_hypothesis.grammar.constraint_set}:")
        if settings.restriction_on_alphabet:
            restricted_alphabet = self.current_hypothesis.grammar.lexicon.get_distinct_segments()
            restricted_alphabet_list = [segment.symbol for segment in restricted_alphabet]
            logger.info(f"Alphabet: {restricted_alphabet_list}")
        logger.info(f"Lexicon: {self.current_hypothesis.grammar.lexicon}")
        logger.info(f"Parse: {self.current_hypothesis.get_recent_data_parse()}")
        logger.info(self.current_hypothesis.get_recent_energy_signature())
        if self.target_energy:
            energy_delta = self.current_hypothesis.combined_energy - self.target_energy
            logger.info("Distance from target energy: {:,}".format(energy_delta))

        if self.target_lexicon_indicator_function:
            lexicon_string_words = [str(word) for word in self.current_hypothesis.grammar.lexicon.get_words()]
            logger.info(self.target_lexicon_indicator_function(lexicon_string_words))

        if self.target_data is not None and self.sample_target_outputs is not None:
            outputs = self.current_hypothesis.grammar.get_all_outputs_grammar(
                new_string_word_list=self.sample_target_lexicon)
            result = {str(word) for word in outputs}
            logger.info(f"Desired grammar: {result == set(self.sample_target_outputs)}")

    @staticmethod
    def _get_memory_usage():
        p = subprocess.Popen("ps -o rss= -p {}".format(process_id), stdout=subprocess.PIPE, shell=True)
        (output, err) = p.communicate()
        return int((int(output) / 1024))  # memory usage in MB

    @staticmethod
    def _calculate_num_of_steps():
        step = 0
        temp = settings.initial_temp
        while temp > settings.threshold:
            step += 1
            temp *= settings.cooling_factor
        return step

    def clear_modules_caching(self):
        Grammar.clear_caching()
        ConstraintSet.clear_caching()
        Constraint.clear_caching()
        Word.clear_caching()

        diagnostics_flag = False
        if diagnostics_flag:
            def object_size_in_mb(object_):
                from pympler.asizeof import asizeof

                return int((asizeof(object_) / (1024 ** 2)))

            import grammar.grammar
            import grammar.constraint_set
            import grammar.constraint
            import grammar.lexicon

            memoization_size = object_size_in_mb(grammar.grammar.generation_memoization)
            grammar_transducers_size = object_size_in_mb(grammar.grammar.grammar_transducers)
            constraint_set_transducers_size = object_size_in_mb(grammar.constraint_set.constraint_set_transducers)
            constraint_transducers_size = object_size_in_mb(grammar.constraint.constraint_transducers)
            word_transducers_size = object_size_in_mb(grammar.lexicon.word_transducers)

            logger.info(f"asizeof generation_memoization: {memoization_size} MB")
            logger.info(f"length generation_memoization: {len(grammar.grammar.generation_memoization)}")

            logger.info("asizeof grammar_transducers: {} MB".format(grammar_transducers_size))
            logger.info("length grammar_transducers: {}".format(len(grammar.grammar.grammar_transducers)))
            logger.info("asizeof constraint_set_transducers: {} MB".format(constraint_set_transducers_size))
            logger.info("asizeof constraint_transducers: {} MB".format(constraint_transducers_size))

            logger.info("asizeof word_transducers: {} MB".format(word_transducers_size))
            logger.info("length word_transducers: {}".format(len(grammar.lexicon.word_transducers)))

            sum_asizeof = (memoization_size + grammar_transducers_size + constraint_set_transducers_size +
                           constraint_transducers_size + word_transducers_size)

            logger.info(f"sum asizeof: {sum_asizeof} MB")
            logger.info(f"Memory usage: {self._get_memory_usage()} MB")

    def _pretty_step_label(self):
        padding_size = len(str(self.number_of_expected_steps))
        current_step = f"{self.step:>{padding_size}}"
        return f"{current_step}/{self.number_of_expected_steps}"


def _pretty_runtime_str(run_time_in_seconds):
    time_delta = timedelta(seconds=run_time_in_seconds)
    timedelta_string = str(time_delta)

    m = re.search(r'(\d* (days|day), )?(\d*):(\d*):(\d*)', timedelta_string)
    days_string = m.group(1)
    hours = int(m.group(3))
    minutes = int(m.group(4))
    seconds = int(m.group(5))

    if days_string:
        days_string = days_string[:-2]
        return f"{days_string}, {hours} hours, {minutes} minutes, {seconds} seconds"
    elif hours:
        return f"{hours} hours, {minutes} minutes, {seconds} seconds"
    elif minutes:
        return f"{minutes} minutes, {seconds} seconds"
    else:
        return f"{seconds} seconds"
