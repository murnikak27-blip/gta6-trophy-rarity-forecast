# gta6-trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/murnikak27-blip/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/murnikak27-blip/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts every GTA VI PS5 trophy's Exophase earn rate one week after release, from the trophy page's read history: a trend fit blended with an earners-and-dilution model.

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

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=y32rxgm2&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
