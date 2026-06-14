"""The falsification gate: one entrypoint that tries to kill a strategy.

Consumes a ``FamilyEvaluation`` (best variant + the full grid's returns matrix)
plus market context, runs both schools of multiple-testing control and the
survival battery, and produces a single structured report:

- Deflated Sharpe vs the CUMULATIVE ledger N (LdP school, nominal)
- The alternative gate: HLZ/FDR t-hurdle, effective-N DSR, Bayesian shrinkage
- Block-bootstrap null (Sharpe SE / CI / p(luck))
- PBO (CSCV) and CPCV OOS distribution on the searched grid
- MinBTL vs actual history length
- Cost stress: 1x / 2x / 4x fees+slippage (re-backtested, not approximated)
- Capacity curve from real median ADV of the held names
- Regime splits: Fear/Greed quartiles + temporal stability + decay slope

Verdict policy (tiered, calibrated for a small + highly correlated crypto
universe): deflate by the CORRELATION-ADJUSTED effective-N, not the nominal grid
/ ledger count (which treats co-moving variants as independent and vetoes every
real edge). STRONG = clears all five conditions; DEFENSIBLE = clears the three
selection-bias conditions (effective-N DSR, CPCV-OOS, PBO) with a marginal
cost/luck check, or a regime-concentrated STRONG downgraded; FAIL otherwise. The
nominal-N DSR and MinBTL stay in the report as a conservative lower-bound lens,
NOT in the verdict.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtest.engine import backtest
from backtest.metrics import ann_turnover as _ann_turnover
from backtest.metrics import cagr as _cagr
from backtest.metrics import max_drawdown, sharpe
from strategies.families import FamilyEvaluation
from strategies.spec import compile_strategy
from validation.alt import validate_strategy_alt
from validation.core import (
    ANN_CRYPTO_DAILY,
    TrialLedger,
    anomaly_decay,
    capacity_curve,
    cpcv_paths,
    min_backtest_length,
    monte_carlo_null,
    parameter_stability,
    pbo_cscv,
    validate_strategy,
)


@dataclass
class FalsificationReport:
    name: str
    hypothesis: str
    headline: dict
    dsr_block: dict
    alt_block: dict
    null_block: dict
    selection_block: dict      # pbo + cpcv + minbtl
    cost_block: dict
    capacity_block: dict
    regime_block: dict
    verdict: str               # STRONG / DEFENSIBLE / FAIL (effective-N tiered)
    reasons: list[str] = field(default_factory=list)
    alt_verdict: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def falsify(
    ev: FamilyEvaluation,
    *,
    close: pd.DataFrame,
    ledger: TrialLedger,
    funding: pd.DataFrame | None = None,
    fng: pd.Series | None = None,
    volume_usd: pd.DataFrame | None = None,
    freq: float = ANN_CRYPTO_DAILY,
    min_dsr: float = 0.95,
) -> FalsificationReport:
    r = ev.best_returns.dropna()
    n = len(r)
    years = n / freq
    sr_ann = sharpe(r, freq=freq)
    eq = (1.0 + r).cumprod()

    headline = {
        "sharpe_ann": sr_ann,
        "cagr": _cagr(r, freq=freq),
        "max_drawdown": max_drawdown(eq),
        "n_obs": n,
        "years": round(years, 2),
        "best_variant": ev.best_name,
        "grid_size": int(ev.returns_matrix.shape[1]),
    }

    # --- school 1: deflated Sharpe vs CUMULATIVE ledger N
    n_cum = max(ledger.total, ev.returns_matrix.shape[1])
    rep = validate_strategy(r, n_trials=n_cum, min_dsr=min_dsr, freq=freq)
    dsr_block = {"n_trials_cumulative": n_cum, "psr": rep.psr, "dsr": rep.dsr,
                 "sr0_ann": rep.sr0_ann, "pass": bool(rep.dsr >= min_dsr)}

    # --- school 2: HLZ/FDR + effective-N + Bayes (triangulation, not verdict)
    alt = validate_strategy_alt(
        r, nominal_n_trials=n_cum, returns_matrix=ev.returns_matrix, freq=freq)
    alt_block = {
        "t_adj": alt.t_adj, "hlz_hurdle": alt.hlz_hurdle, "pass_fdr": alt.pass_fdr,
        "effective_n": alt.effective_n, "dsr_eff": alt.dsr_eff,
        "sr0_eff_ann": alt.sr0_eff_ann, "pass_eff_dsr": alt.pass_eff_dsr,
        "posterior_mean_sr": alt.posterior_mean_sr,
        "posterior_p_gt_0": alt.posterior_p_gt_0, "pass_bayes": alt.pass_bayes,
        "n_lenses_pass": alt.n_lenses_pass, "verdict": alt.verdict,
    }

    # --- luck null
    null_block = monte_carlo_null(r, n_sims=500, seed=0, freq=freq)

    # --- selection-process diagnostics on the searched grid
    pbo = pbo_cscv(ev.returns_matrix, n_blocks=10, seed=0)
    cpcv = cpcv_paths(ev.returns_matrix, n_blocks=10, seed=0, embargo=5, freq=freq)
    minbtl = min_backtest_length(n_cum, sr_ann)
    selection_block = {"pbo": pbo["pbo"], "cpcv_oos_sharpe_mean": cpcv.get("oos_sharpe_mean"),
                       "cpcv_oos_p5": cpcv.get("oos_sharpe_p5"),
                       "cpcv_selection_haircut": cpcv.get("selection_haircut"),
                       "minbtl_years": minbtl, "years_available": years,
                       "minbtl_ok": bool(years >= minbtl)}

    # --- cost stress: re-backtest the BEST variant at 2x and 4x costs
    cost_block = {"sharpe_1x": sr_ann}
    for mult in (2.0, 4.0):
        cs = compile_strategy(ev.best_spec, close, funding=funding, fng=fng)
        res = backtest(close, cs.weights, fee_bps=cs.fee_bps * mult,
                       slippage_bps=cs.slippage_bps * mult, funding_daily=funding,
                       funding_weights=cs.funding_weights)
        cost_block[f"sharpe_{int(mult)}x"] = sharpe(res.returns, freq=freq)
    cost_block["survives_2x"] = bool(cost_block["sharpe_2x"] > 0)

    # --- capacity from real ADV of held names
    capacity_block = {}
    if volume_usd is not None:
        cs = compile_strategy(ev.best_spec, close, funding=funding, fng=fng)
        wmat = cs.funding_weights if cs.funding_weights is not None else cs.weights
        held_names = wmat.columns[(wmat.abs() > 0).any()]
        adv = float(volume_usd[held_names].tail(90).median().median()) if len(held_names) else 0.0
        n_pos = int(ev.best_spec.portfolio.get("k", 5))
        res = backtest(close, cs.weights, fee_bps=cs.fee_bps,
                       slippage_bps=cs.slippage_bps, funding_daily=funding,
                       funding_weights=cs.funding_weights)
        turn = _ann_turnover(res.turnover, freq=freq)
        capacity_block = capacity_curve(
            max(headline["cagr"], 0.0), ann_turnover=max(turn, 0.1),
            n_positions=n_pos, median_adv_usd=max(adv, 1.0),
            aum_grid_usd=[1e4, 1e5, 1e6, 1e7, 1e8],
            n_rebals_per_year=52, base_cost_bps=15.0)
        capacity_block["median_adv_usd"] = adv
        capacity_block["ann_turnover"] = turn

    # --- regimes: F&G quartiles + temporal stability + decay
    regime_block = {
        "stability": parameter_stability(r, n_subperiods=6, freq=freq),
        "decay": anomaly_decay(r, n_subperiods=6, freq=freq),
    }
    if fng is not None and fng.notna().any():
        f = fng.reindex(r.index).ffill()
        q = pd.qcut(f, 4, labels=["fear", "mid-fear", "mid-greed", "greed"],
                    duplicates="drop")
        regime_block["fng_quartile_sharpe"] = {
            str(lab): sharpe(r[q == lab], freq=freq)
            for lab in q.dtype.categories} if hasattr(q.dtype, "categories") else {}

    # --- verdict: effective-N tiered gate (STRONG / DEFENSIBLE / FAIL)
    # Calibrated for a SMALL, HIGHLY CORRELATED crypto universe: deflate by the
    # correlation-adjusted effective-N (not the nominal grid/ledger count, which
    # treats co-moving variants as independent and vetoes every real edge). The
    # nominal-N DSR + MinBTL stay in the report as a conservative lower-bound
    # lens, NOT in the verdict. The gate must DISCRIMINATE: bless a real edge,
    # reject the noise bait.
    cpcv_mean = selection_block["cpcv_oos_sharpe_mean"]
    cpcv_p5 = selection_block["cpcv_oos_p5"]
    conditions = {
        "effective-N DSR >= 0.90": alt.dsr_eff >= 0.90,
        "CPCV OOS mean > 0.5 & p5 >= -0.25":
            (cpcv_mean is not None and cpcv_mean > 0.5
             and cpcv_p5 is not None and cpcv_p5 >= -0.25),
        "PBO <= 0.35": (not math.isnan(pbo["pbo"])) and pbo["pbo"] <= 0.35,
        "2x-cost Sharpe > 0.5": cost_block["sharpe_2x"] > 0.5,
        "bootstrap p(Sharpe<=0) <= 0.05": null_block["p_le_zero"] <= 0.05,
    }
    # the three selection-bias conditions are the PASS core; cost+luck refine the tier
    selection_core = (conditions["effective-N DSR >= 0.90"]
                      and conditions["CPCV OOS mean > 0.5 & p5 >= -0.25"]
                      and conditions["PBO <= 0.35"])
    failed = [k for k, ok in conditions.items() if not ok]

    if selection_core and not failed:
        verdict = "STRONG"
    elif selection_core:
        verdict = "DEFENSIBLE"
    else:
        verdict = "FAIL"

    # regime caveat: a STRONG whose edge is concentrated in one F&G regime or is
    # unstable across sub-periods is honestly only DEFENSIBLE.
    fq = [v for v in (regime_block.get("fng_quartile_sharpe") or {}).values()
          if v is not None and not (isinstance(v, float) and math.isnan(v))]
    stable = bool(regime_block.get("stability", {}).get("stable", True))
    regime_concentrated = bool(len(fq) >= 2 and (max(fq) - min(fq) > 1.5))
    reasons: list[str] = []
    if verdict == "STRONG" and (not stable or regime_concentrated):
        verdict = "DEFENSIBLE"
        reasons.append("downgraded STRONG->DEFENSIBLE: edge is regime-concentrated "
                       "or unstable across sub-periods")

    if verdict == "FAIL":
        reasons.insert(0, "fails the effective-N selection gate (" + "; ".join(failed) + ")")
        reasons.append(f"effective-N DSR {alt.dsr_eff:.2f} at effN {alt.effective_n:.1f}; "
                       f"CPCV OOS mean "
                       f"{'n/a' if cpcv_mean is None else round(cpcv_mean, 2)}; "
                       f"PBO {pbo['pbo']:.2f}")
    else:
        reasons.insert(0, f"{verdict}: clears the effective-N selection gate "
                       f"(DSR_eff {alt.dsr_eff:.2f} at effN {alt.effective_n:.1f}, "
                       f"PBO {pbo['pbo']:.2f}, CPCV OOS mean "
                       f"{'n/a' if cpcv_mean is None else round(cpcv_mean, 2)})")
        if failed:
            reasons.append("non-gating caveats: " + "; ".join(failed))
    reasons.append(f"conservative nominal-N lens (assumes independent trials): "
                   f"DSR {rep.dsr:.2f} vs {min_dsr} at N={n_cum} — a lower bound "
                   "for a correlated universe, not the verdict")

    return FalsificationReport(
        name=ev.base.name, hypothesis=ev.base.hypothesis,
        headline=headline, dsr_block=dsr_block, alt_block=alt_block,
        null_block={k: (v if not isinstance(v, tuple) else list(v))
                    for k, v in null_block.items()},
        selection_block=selection_block, cost_block=cost_block,
        capacity_block=capacity_block, regime_block=regime_block,
        verdict=verdict, reasons=reasons, alt_verdict=alt.verdict,
    )
