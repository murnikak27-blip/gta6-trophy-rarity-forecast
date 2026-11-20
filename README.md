# GTA VI trophy rarity forecast

An entry for make.fun's **gta6-trophy-rarity-forecast-01**: forecast, for
every PlayStation 5 trophy of Grand Theft Auto VI, the share of tracked
players who will have earned it one week after release, as printed by the
trophy's Exophase page.

## What the program does

`main.py` (Python 3, standard library only) is run once per case. A case
gives it every read the house made of the game's Exophase trophy page
before a checkpoint: the players tracked and each trophy's earn rate at
each read. It writes one forecast file holding, for each trophy, five
quantiles (5%, 25%, 50%, 75%, 95%) of the earn rate at the case's target.

For each trophy, on the logit scale the contest scores on, it blends:

- a recency-weighted trend fit of the rate against ln(1 + hours since
  release), damped the further the target sits past the fitted span and
  capped so a steep week-one line cannot run to 100%;
- an earners decomposition that extrapolates the implied earners and the
  players tracked separately and rebuilds the rate, which separates real
  progress from the dilution a growing player base causes.

The spread around the median grows with the horizon and with how far the
two legs disagree. The program is deterministic: two runs on the same
case write the same bytes.

## Running it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

reads every `*.in` case file in the input directory and writes the
matching `*.out` forecast files to the output directory.
