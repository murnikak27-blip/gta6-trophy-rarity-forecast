"""Forecast each GTA VI PS5 trophy's Exophase earn rate at a future target.

Written for make.fun's gta6-trophy-rarity-forecast-01 (program/v1). The
program reads one case file per run from the input directory: the case
names every trophy and holds every read the house made of the game's
Exophase trophy page before the case's checkpoint (players tracked and
each trophy's earn rate at each read). For each trophy it writes five
quantiles (the case's levels) of the earn rate at the case's target.

Model, per trophy, on the logit scale the contest scores on:

  * a recency-weighted straight-line fit of the rate's logit against
    ln(1 + hours since release), extrapolated to the target and shrunk
    toward the last observed rate (the ln clock makes growth saturate
    the way trophy earning does over a launch week);
  * an earners decomposition: the implied earners (rate x players
    tracked) and the players tracked are each extrapolated on the same
    clock, and the rate is rebuilt as earners / players, which separates
    real progress from the dilution a growing player base causes;
  * the median is the average of the two on the logit scale, each leg's
    move capped so a noisy fit cannot run away.

The spread around the median grows with the horizon (a random walk's
sqrt(days) term, like the house baseline's) plus the trophy's own fit
residual, floored so a flat, stale history never reads as certainty.

Standard library only, no network, fully deterministic: two runs on the
same case write the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

RATE_LO = 0.01
RATE_HI = 99.99
# Recency weighting for the fits: a read this many hours before the last
# one counts half as much.
HALF_LIFE_HOURS = 30.0
# Cap on how far either leg may move a trophy's logit from its last read.
MAX_MOVE = 2.2


def clamp_rate(pct):
    return min(RATE_HI, max(RATE_LO, pct))


def logit(pct):
    p = clamp_rate(pct) / 100.0
    return math.log(p / (1.0 - p))


def inv_logit(y):
    return 100.0 / (1.0 + math.exp(-y))


def norm_quantile(p):
    """The standard normal's quantile at p (Acklam's approximation)."""
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285984469534e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def round4(x):
    """Round to 4 decimals, half up; whole numbers come back as ints."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if float(value).is_integer() else value


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def wlsq(xs, ys, ws):
    """Weighted least squares y ~ a + b x. Returns (a, b, residual_std)."""
    sw = sum(ws)
    if sw <= 0:
        return ys[-1], 0.0, 0.0
    sx = sum(w * x for x, w in zip(xs, ws))
    sy = sum(w * y for y, w in zip(ys, ws))
    sxx = sum(w * x * x for x, w in zip(xs, ws))
    sxy = sum(w * x * y for x, y, w in zip(xs, ys, ws))
    denom = sw * sxx - sx * sx
    if abs(denom) < 1e-12:
        a, b = sy / sw, 0.0
    else:
        b = (sw * sxy - sx * sy) / denom
        a = (sy - b * sx) / sw
    var = sum(w * (y - (a + b * x)) ** 2 for x, y, w in zip(xs, ys, ws)) / sw
    return a, b, math.sqrt(max(var, 0.0))


def capped(value, lo, hi):
    return min(hi, max(lo, value))


def build_weights(ages_hours):
    return [0.5 ** (age / HALF_LIFE_HOURS) for age in ages_hours]


def forecast_case(case):
    levels = case["levels"]
    zs = [norm_quantile(tau) for tau in levels]
    release = parse_time(case["game"]["release_date"] + "T00:00:00Z")
    checkpoint = parse_time(case["at"])
    target = parse_time(case["target"])
    days = case["horizon_minutes"] / 1440.0

    def hours(at):
        return (at - release).total_seconds() / 3600.0

    def x_of(at):
        return math.log(1.0 + max(0.0, hours(at)))

    target_x = x_of(target)
    history = case["history"]
    read_hours = [hours(parse_time(r["at"])) for r in history]
    read_x = [math.log(1.0 + max(0.0, h)) for h in read_hours]
    players_series = [(read_hours[j], read_x[j], float(r["players_tracked"]))
                      for j, r in enumerate(history) if r.get("players_tracked")]

    rows = []
    for i, trophy in enumerate(case["trophies"]):
        series = [(read_hours[j], read_x[j], float(r["rates"][i]))
                  for j, r in enumerate(history)
                  if i < len(r["rates"]) and r["rates"][i] is not None]
        median, sigma = forecast_one(series, players_series, target_x, days)
        qs = []
        for z in zs:
            qs.append(round4(inv_logit(median + z * sigma)))
        # Keep the row non-decreasing after rounding.
        for k in range(1, len(qs)):
            if qs[k] < qs[k - 1]:
                qs[k] = qs[k - 1]
        rows.append({"id": trophy["id"], "q": qs})
    return {"trophies": rows}


def forecast_one(series, players_series, target_x, days):
    """One trophy's (median logit, sigma): the trend leg and the earners
    leg, blended; the spread from the horizon and the fit residual."""
    base_sigma = 0.5 * math.sqrt(days)
    if not series:
        return logit(1.0), max(0.30, base_sigma)
    last_rate = series[-1][2]
    y_last = logit(last_rate)
    if len(series) < 3:
        return y_last, max(0.30, base_sigma)

    last_hours = series[-1][0]
    xs = [s[1] for s in series]
    ys = [logit(s[2]) for s in series]
    ws = build_weights([last_hours - s[0] for s in series])
    a, b, resid = wlsq(xs, ys, ws)
    x_last = xs[-1]
    shrink = sum(ws) / (sum(ws) + 8.0)
    # Damp the extrapolation: a line fitted over an ln-clock span of
    # x_span is trusted less the further past it the target sits, since
    # earning saturates as a trophy nears the share who will ever get it.
    horizon_x = max(0.0, target_x - x_last)
    x_span = max(0.05, x_last - xs[0])
    damp = x_span / (x_span + horizon_x)
    move = capped(b * horizon_x, -MAX_MOVE, MAX_MOVE)
    median_trend = y_last + shrink * damp * move

    median = median_trend
    earners_leg = earners_median(series, players_series, target_x)
    leg_gap = 0.0
    if earners_leg is not None:
        # In a fast-growing player base the earners leg carries the
        # dilution signal, so it weighs more; in a settled base the
        # rate's own trend says as much.
        if players_series and players_series[0][2] > 0:
            growth = players_series[-1][2] / players_series[0][2]
        else:
            growth = 1.0
        w_earners = 0.6 if growth >= 1.2 else 0.4
        median = (1.0 - w_earners) * median_trend + w_earners * earners_leg
        leg_gap = abs(median_trend - earners_leg)

    # Ceiling guard: a week-one rate cannot run far past anything the
    # trophy has already shown, however steep its recent line looks.
    cap_rate = min(99.0, max(s[2] for s in series) * 2.5 + 10.0)
    median = min(median, logit(cap_rate))

    sigma = math.sqrt(0.30 * days
                      + 0.6 * resid * resid * min(days, 3.0)
                      + 0.09
                      + (0.35 * leg_gap) ** 2)
    sigma = capped(sigma, max(0.30, 0.8 * base_sigma), 2.4)
    return median, sigma


def earners_median(series, players_series, target_x):
    """The rate's logit at the target if earners and players tracked each
    follow their own ln-clock trend; None when the data cannot say."""
    if len(players_series) < 3 or len(series) < 3:
        return None
    p_last = players_series[-1]
    if p_last[2] <= 0:
        return None
    pxs = [p[1] for p in players_series]
    pws = build_weights([p_last[0] - p[0] for p in players_series])
    pa, pb, _ = wlsq(pxs, [math.log(p[2]) for p in players_series], pws)
    horizon_x = max(0.0, target_x - pxs[-1])
    p_span = max(0.05, pxs[-1] - pxs[0])
    d_log_players = capped(pb * horizon_x * (p_span / (p_span + horizon_x)),
                           0.0, 1.6)
    players_target = p_last[2] * math.exp(d_log_players)

    # Implied earners at each read of this trophy's series: the reads of
    # the series are a subsequence of all reads, matched by their hours.
    by_hours = {p[0]: p[2] for p in players_series}
    pts = []
    for hours_, x_, rate in series:
        pl = by_hours.get(hours_)
        if pl:
            pts.append((hours_, x_, rate / 100.0 * pl))
    if len(pts) < 3:
        return None
    exs = [p[1] for p in pts]
    ews = build_weights([pts[-1][0] - p[0] for p in pts])
    ea, eb, _ = wlsq(exs, [math.log(p[2] + 0.5) for p in pts], ews)
    e_span = max(0.05, exs[-1] - exs[0])
    d_log_earners = capped(eb * horizon_x * (e_span / (e_span + horizon_x)),
                           -0.2, 1.8)
    earners_target = max(0.0, (pts[-1][2] + 0.5) * math.exp(d_log_earners) - 0.5)
    earners_target = min(earners_target, players_target * 0.9999)
    if players_target <= 0:
        return None
    rate = 100.0 * earners_target / players_target
    return logit(rate)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
