"""Render a FalsificationReport as a markdown evidence pack.

Styled after the CMC Skill Hub house format: summary first, then report,
decision basis, insights and a freshness note — so the artifact reads natively
inside an Agent Hub conversation.
"""

from __future__ import annotations

from validation.gate import FalsificationReport


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def render_markdown(rep: FalsificationReport, *, stamp: str = "",
                    regime_context: dict | None = None) -> str:
    h = rep.headline
    d = rep.dsr_block
    a = rep.alt_block
    nl = rep.null_block
    s = rep.selection_block
    c = rep.cost_block

    banner = {
        "STRONG": "✅ STRONG — clears the effective-N falsification gate",
        "DEFENSIBLE": "🟡 DEFENSIBLE — a real but caveated edge",
    }.get(rep.verdict, "❌ FAIL — indistinguishable from noise")
    lines: list[str] = []
    lines.append(f"# Proof of Alpha — falsification report: `{rep.name}`")
    if stamp:
        lines.append(f"*Generated {stamp}*")
    lines.append("")
    lines.append(f"## {banner}")
    lines.append("")
    lines.append("**Summary.** "
                 f"Best variant `{h['best_variant']}` from a declared grid of "
                 f"{h['grid_size']} configs: Sharpe {h['sharpe_ann']:.2f}, CAGR "
                 f"{_pct(h['cagr'])}, MDD {_pct(h['max_drawdown'])} over "
                 f"{h['years']}y. Verdict: **{rep.verdict}** — " + rep.reasons[0] + ".")
    lines.append("")
    lines.append(f"**Hypothesis under test.** {rep.hypothesis}")
    lines.append("")

    lines.append("## Report")
    lines.append("")
    lines.append("### 1. Selection-bias deflation (Bailey & López de Prado)")
    lines.append(f"- Cumulative trials ever run on this dataset: **{d['n_trials_cumulative']}** "
                 "(persistent ledger — every config ever evaluated counts)")
    lines.append(f"- PSR P(SR>0): {d['psr']:.3f}; **DSR: {d['dsr']:.3f}** vs required ≥ 0.95")
    lines.append(f"- Selection bar: the best of {d['n_trials_cumulative']} noise strategies "
                 f"is expected to show Sharpe ≈ {d['sr0_ann']:.2f} — the candidate must beat THAT")
    lines.append(f"- Result: {'PASS' if d['pass'] else 'FAIL'}")
    lines.append("")
    lines.append("### 2. Second school: FDR / effective-N / Bayes (triangulation)")
    lines.append(f"- Skew/kurtosis-aware t-stat {a['t_adj']:.2f} vs HLZ hurdle "
                 f"{a['hlz_hurdle']:.1f}: {'pass' if a['pass_fdr'] else 'fail'}")
    lines.append(f"- Effective independent trials (correlation-adjusted): "
                 f"{a['effective_n']:.1f}; DSR at effective-N: {a['dsr_eff']:.3f} "
                 f"({'pass' if a['pass_eff_dsr'] else 'fail'})")
    lines.append(f"- Bayesian posterior Sharpe {a['posterior_mean_sr']:.2f}, "
                 f"P(SR>0)={a['posterior_p_gt_0']:.3f} ({'pass' if a['pass_bayes'] else 'fail'})")
    lines.append(f"- Alt-school verdict: **{a['n_lenses_pass']}/3 = {a['verdict']}**")
    lines.append("")
    lines.append("### 3. Luck null (block bootstrap)")
    lines.append(f"- Sharpe {nl['sharpe']:.2f} ± {nl['se']:.2f} "
                 f"(95% CI [{nl['ci'][0]:.2f}, {nl['ci'][1]:.2f}])")
    lines.append(f"- P(Sharpe ≤ 0 under resampling): {nl['p_le_zero']:.3f}")
    lines.append("")
    lines.append("### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)")
    lines.append(f"- PBO: **{s['pbo']:.2f}** (≈0.5 = picking on noise; ≤0.2 healthy)")
    lines.append(f"- CPCV out-of-sample Sharpe of the would-be-selected variant: "
                 f"mean {s['cpcv_oos_sharpe_mean']:.2f}, 5th pct {s['cpcv_oos_p5']:.2f}, "
                 f"selection haircut {s['cpcv_selection_haircut']:.2f}")
    lines.append(f"- Minimum backtest length for N={d['n_trials_cumulative']}: "
                 f"{s['minbtl_years']:.1f}y vs available {s['years_available']:.1f}y "
                 f"({'ok' if s['minbtl_ok'] else 'NOT ENOUGH DATA'})")
    lines.append("")
    lines.append("### 5. Cost & capacity stress")
    lines.append(f"- Sharpe at 1x / 2x / 4x costs: {c['sharpe_1x']:.2f} / "
                 f"{c['sharpe_2x']:.2f} / {c['sharpe_4x']:.2f}")
    if rep.capacity_block:
        cap = rep.capacity_block
        lines.append(f"- Median ADV of held names: ${cap['median_adv_usd']:,.0f}; "
                     f"annual turnover {cap['ann_turnover']:.1f}x")
        lines.append(f"- Capacity (net return holds ≥ half small-size net): "
                     f"**${cap['capacity_usd']:,.0f}**")
    lines.append("")
    lines.append("### 6. Regime robustness")
    st = rep.regime_block.get("stability", {})
    if st.get("subperiod_sharpe"):
        lines.append(f"- Sharpe by sub-period: {st['subperiod_sharpe']} "
                     f"(stable: {st['stable']})")
    dec = rep.regime_block.get("decay", {})
    if dec.get("subperiod_sharpe"):
        lines.append(f"- Decay slope: {dec['slope']:.2f} per period "
                     f"(first half {dec['first_half']:.2f} → second half {dec['second_half']:.2f})")
    fq = rep.regime_block.get("fng_quartile_sharpe")
    if fq:
        pretty = ", ".join(f"{k}: {v:.2f}" for k, v in fq.items())
        lines.append(f"- Sharpe by Fear & Greed quartile: {pretty}")
    lines.append("")

    lines.append("## Decision basis")
    for reason in rep.reasons:
        lines.append(f"- {reason}")
    lines.append("")
    lines.append("## Insights")
    if rep.verdict == "FAIL" and a["verdict"] in ("DEFENSIBLE", "PASS"):
        lines.append("- The two schools DISAGREE: nominal-N deflation kills it, but the "
                     "FDR/effective-N school finds it defensible. This is the honest grey "
                     "zone — the difference is entirely the multiple-testing philosophy, "
                     "and the only arbiter left is live out-of-sample track record.")
    if rep.verdict == "FAIL":
        lines.append("- A FAIL does not mean the mechanism is false — it means THIS evidence "
                     "does not distinguish the strategy from the best of the noise searched.")
    else:
        lines.append(f"- {rep.verdict} means it cleared the effective-N gate (deflated for a "
                     "correlated crypto universe), not guaranteed-alpha: paper-trade before "
                     "capital, size to the capacity figure, monitor decay.")
    lines.append("")

    if regime_context and regime_context.get("fear_greed"):
        fg = regime_context["fear_greed"]
        lines.append("## Live CMC regime context")
        lines.append(f"- Fear & Greed now: **{fg['value']} ({fg['classification']})** "
                     f"— source: {regime_context.get('source', 'cmc')}")
        lines.append("- Compare to the Fear & Greed quartile where this strategy "
                     "earned (section 6). If today's regime is far from it, size down.")
        lines.append("")

    lines.append("*Freshness: backtest data ends at the last cached bar; re-run "
                 "`scripts/fetch_history.py` and the gate for a current verdict.*")
    return "\n".join(lines)
