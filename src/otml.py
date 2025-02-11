"""
This is the entry point of the otml project
The working directory for activating this file should be "otml"
"""

import click

from src.grammar.constraint_set import ConstraintSet
from src.grammar.features.feature_table import FeatureTable
from src.grammar.grammar import Grammar
from src.grammar.lexicon import Lexicon
from src.models.corpus import Corpus
from src.models.otml_configuration import OtmlConfiguration, settings
from src.models.traversable_grammar_hypothesis import TraversableGrammarHypothesis
from src.simulated_annealing import SimulatedAnnealing


@click.command()
@click.option(
    "-c", "--configuration", "config_folder_path", required=True, help="Relative path to the configuration folder"
)
def main(config_folder_path):
    # load configurations
    OtmlConfiguration.load(config_folder_path)

    # load grammar and data
    feature_table = FeatureTable.load(settings.features_file)
    corpus = Corpus.load(settings.corpus_file)
    constraint_set = ConstraintSet.load(settings.constraints_file, feature_table)
    lexicon = Lexicon(corpus.get_words(), feature_table)
    grammar = Grammar(feature_table, constraint_set, lexicon)
    data = corpus.get_words()

    # prepare data for optimization
    traversable_hypothesis = TraversableGrammarHypothesis(grammar, data)
    simulated_annealing = SimulatedAnnealing(traversable_hypothesis)

    print("Starting optimization")
    step, hypothesis = simulated_annealing.run()
    print(f"Ran {step} steps with seed {settings.seed}.")
    print(f"Finished with {hypothesis}")
    print(f"  - {hypothesis.grammar.constraint_set}")
    print(f"  - {hypothesis.grammar.lexicon}")

    print("Done")


if __name__ == "__main__":
    main()
