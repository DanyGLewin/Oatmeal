# Oatmeal: MDL Phonology Learner

Oatmeal is a phonological learner based on the Minimum Description Length (MDL) principle. It extends and builds upon
the original `otml` project from [TAU Computational Linguistics](https://github.com/taucompling/otml), adding support
for category-specific phonological systems, tier-based 2-local constraints, and enhanced simulations.

## Running Simulations
To run a simulation, run the following command:
```bash
python3 src/otml.py -c [PATH_TO_SIMULATION_FOLDER]
```

For example, to run a simulation for 'blocking' interactions with $TSL_2$ constraints, run
```bash
python3 src/otml.py -c simulations/tiered-local/blocking
```

## Building Simulations
To build a simulation, you need to configure a few models. To begin with, create a folder in the `simulations` directory, to house your simulation. Then, create the following files:

### 1. Features and Segments
This file defines three key models: the features that are used in the simulation, the segments that exist, and a mapping from segments to feature sets.

A `features.json` file has the following schema:

```json
{
  "feature": [
    {
      "label": "FEATURE_1",
      "values": [
        "VALUE_1",
        "VALUE_2",
        ...
      ]
    },
    ...
  ],
  "feature_table": [
    "SYMBOL": {
      "FEATURE_1": "VALUE_1",
      "FEATURE_2": "VALUE_2",
      ...
    },
    ...
  ]
}
```
**Note:** every segment in the `feature_table` part of the file must set a value for every feature defined in the `features` part, in the same order they are defined.

### 2. Corpus
This file is a simple list of surface forms in the language, separated by spaces. For example:
```text
sataxa stxa staxa satxa xasataxa xasataxasa sasa xaxa xasa xasasa xaxasa
```
### 3. Constraint definitions
This file defines the constraints in the language, as well as their initial order.

Every constraint has a `type` (typically one of `Faith / Dep / Max / Phonotactic `), and a list a features bundle to apply the constraint to. Importantly, there must always be exactly one `Faith` constraint. 

A `constraints.json` file has the following schema:

```json
[
  {
    "type": "Faith",
    "bundles": []
  },
  {
    "type": "CONSTRAINT_TYPE",
    "bundles": [
      {
        "FEATURE_1": "VALUE_1",
        "FEATURE_2": "VALUE_2",
        ...
      },
      ...
    ]
  },
  ...
]
```
**Note:** every feature and value used in a constraint must also be defined in `features.json`.

### Simulation configuration
The `config.json` file defines many parameters of the simulation. It's recommended to initially copy an existing configuration file from another simulation, then tweak as necessary.

Some of the more important options in `config.json` are:
 * `initial_temp`, `cooling_factor`, `threshold`: parameters for the simulated annealing process.
 * `debug_logging_interval`: the number of steps between logs. Set this to `0` to only print the final result.
 * `seed`: the seed for the random number generator. Set this to `0` for random seed.
 * `lexicon_mutation_weights`: the relative weights for inserting, deleting, and changing segments from the lexicon.
 * `constraint_set_mutation_weights`: the relative weights for different operations on the constraint set.
 * `constraint_insertion_weights`: the relative weights of different constraint classes, when one is to be inserted.
 * `allow_candidates_with_changed_segments`: must be enabled if the weight of `change_segment` is positive.

**⚠️️ TODO: document all the options in config.json ⚠️️**



## Credits

Oatmeal is based on the original [otml](https://github.com/taucompling/otml) project. Special thanks to the TAU
Computational Linguistics group for providing the foundation for this work.

## License

This project is provided for educational and research purposes. Feel free to modify and extend it for your needs.
