"""Alternative anti-overfitting gate — the Harvey-Liu / FDR / Bayesian school.

This is the COUNTERPART to ``validation.core`` (Bailey & Lopez de Prado: deflated
Sharpe + PBO + CSCV), built deliberately as a second, equally-respected school so
we can triangulate instead of trusting one philosophy. The two disagree on one
load-bearing question: how hard to penalise a candidate Sharpe for the number of
strategies searched.

The LdP gate deflates by the NOMINAL cumulative trial count, which for a large
ledger pushes the selection bar sr0 to multi-Sharpe levels — and even real
strategies fail. The Harvey-Liu school argues this over-penalises whenever the
trials are correlated (grid-searched configs are ~all "long crypto beta"),
because the EFFECTIVE number of independent tests is far below nominal.
Verified against primary sources (Harvey-Liu-Zhu RFS 2016; Harvey-Liu J.Finance
2020; "Lucky Factors" JFE 2021; Benjamini-Yekutieli 2001; Komiyama et al. 2021;
Pastor 2000; Jorion 1986; Bailey-Lopez de Prado PSR 2012):

- Multiple-testing penalty SHRINKS with correlation; in the perfect-correlation
  limit no adjustment is needed at all (HLZ). An independence assumption can
  inflate a p-value ~20x for 100 perfectly-correlated tests (Lucky Factors).
- FDR control (Benjamini-Hochberg/Yekutieli) gives a t-hurdle that STABILISES
  (law of large numbers) rather than ballooning with cumulative trials: HLZ report
  the BHY bar settling near t=2.78 (FDR 5%) to t=3.39 (FDR 1%), while Bonferroni
  climbs 1.96 -> 3.78 -> 4.00. Their summary recommendation is t > 3.0.
- Under arbitrary unknown dependence the BY correction divides the FDR level by
  c(N)=sum 1/i ~ ln(N)+0.577, i.e. the penalty grows like log(N), NOT N
  (Benjamini-Yekutieli 2001; Komiyama 2021).
- Bayesian/shrinkage estimation puts a full posterior on the Sharpe and shrinks it
  toward an economically-motivated prior, so a short sample need not prove the
  edge from scratch (Pastor 2000; Jorion 1986).

t-stat vs Sharpe: every HLZ hurdle is an absolute t-statistic floor for FACTOR
DISCOVERY, converted to our setting via the skew/kurtosis-aware significance of the
Sharpe, t_adj = Phi^-1(PSR(SR>0)). This automatically raises the bar for fat tails
/ negative skew (the honest version of t = SR_ann * sqrt(years)) — crypto returns
are exactly the fat-tailed, negatively-skewed case this matters for.

CAVEATS we keep visible: (1) effective-N-into-deflation is a defensible-by-analogy
HYBRID the FDR school does not itself endorse — they keep all N tests and let
correlation enter via a joint bootstrap null; we report it as one lens, not the
verdict. (2) HLZ call t=3.0/3.18 MINIMUMS; the true hurdle may be higher. (3) the
Bayesian prior is calibrated on TradFi factor evidence; crypto premia are younger
and noisier, so report prior sensitivity rather than one number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from validation.core import (
    ANN,
    deflated_sharpe_ratio,
    effective_n_trials,
    probabilistic_sharpe_ratio,
)

EULER_GAMMA = 0.5772156649015329

# HLZ / BHY reference t-hurdles (Harvey-Liu-Zhu, RFS 2016, verified against the
# NBER WP and the published paper). These are FDR-stable: they do NOT grow with the
# cumulative trial count, which is the whole point versus Bonferroni/nominal-N.
HLZ_T_HURDLES: dict[str, float] = {
    "bhy_fdr_5pct": 2.78,   # BHY false-discovery-rate at 5%, stabilised post-2010
    "hlz_recommended": 3.0,  # HLZ headline "newly discovered factor needs t > 3.0"
    "bhy_min": 3.18,         # minimum threshold under BHY at 5% significance
    "bhy_fdr_1pct": 3.39,    # BHY FDR at 1%
    "bonferroni_now": 3.78,  # Bonferroni/FWER at current factor count (for contrast)
}


def benjamini_yekutieli_constant(n_trials: int) -> float:
    """c(N) = sum_{i=1}^N 1/i ~ ln(N) + Euler-gamma. Benjamini-Yekutieli (2001):
    under ARBITRARY (unknown) dependence among tests, control FDR at level q by
    running Benjamini-Hochberg at q/c(N). The penalty therefore grows like log(N),
    not N — the formal basis for "nominal-N deflation over-penalises". For N=151k,
    c(N) ~ 12.5, vs a Bonferroni factor of 151,000."""
    if n_trials <= 1:
        return 1.0
    # exact harmonic number for small N, asymptotic series for large N
    if n_trials <= 100_000:
        return float(np.sum(1.0 / np.arange(1, n_trials + 1)))
    return float(math.log(n_trials) + EULER_GAMMA + 0.5 / n_trials)


def skew_kurt_adjusted_tstat(sr_per_period: float, n_obs: int, skew: float, kurt: float) -> float:
    """The skew/kurtosis-aware single-test significance of (true Sharpe > 0), in
    t-units. Equals Phi^-1(PSR): PSR = P(SR>0) = Phi(z), so z is the honest t-stat
    that already discounts fat tails and negative skew. This is what we compare to
    the HLZ t-hurdles — the rigorous replacement for the naive t = SR_ann*sqrt(yrs).
    ``kurt`` is RAW (normal = 3)."""
    psr = probabilistic_sharpe_ratio(sr_per_period, n_obs, skew, kurt, 0.0)
    psr = min(max(psr, 1e-12), 1.0 - 1e-12)
    return float(norm.ppf(psr))


def bayesian_sharpe_posterior(
    sr_ann: float, n_obs: int, *, prior_sr_ann: float, prior_sd_ann: float,
    skew: float = 0.0, kurt: float = 3.0, freq: float = ANN,
) -> dict:
    """Normal-Normal conjugate posterior on the ANNUAL Sharpe, shrinking the noisy
    sample estimate toward an economically-motivated prior (Pastor 2000 / Jorion
    1986 logic). The prior encodes "momentum/carry premia exist across asset
    classes" so a short crypto sample is not asked to prove the edge from scratch.

    Sample likelihood: SR_hat_ann ~ N(true, se^2). We derive ``se`` from the
    skew/kurt-aware t (se = SR_ann / t_adj) so fat tails widen it honestly; falls
    back to the iid Lo (2002) se = sqrt((1 + 0.5 SR^2)/years) when t_adj <= 0.
    Posterior precision = prior precision + sample precision; posterior mean is the
    precision-weighted blend. Returns posterior mean/sd, P(true SR_ann>0), P(>prior),
    and the 95% credible interval."""
    years = n_obs / freq
    sr_per = sr_ann / math.sqrt(freq)
    t_adj = skew_kurt_adjusted_tstat(sr_per, n_obs, skew, kurt)
    if t_adj > 1e-6:
        se = abs(sr_ann) / t_adj
    else:  # degenerate / non-positive significance -> iid Lo se
        se = math.sqrt(max(1e-9, (1.0 + 0.5 * sr_ann * sr_ann) / max(years, 1e-9)))
    prec_prior = 1.0 / (prior_sd_ann ** 2)
    prec_data = 1.0 / (se ** 2)
    prec_post = prec_prior + prec_data
    mean_post = (prior_sr_ann * prec_prior + sr_ann * prec_data) / prec_post
    sd_post = math.sqrt(1.0 / prec_post)
    return {
        "sample_sr_ann": sr_ann,
        "sample_se_ann": se,
        "prior_sr_ann": prior_sr_ann,
        "prior_sd_ann": prior_sd_ann,
        "posterior_mean": mean_post,
        "posterior_sd": sd_post,
        "p_sr_gt_0": float(norm.cdf(mean_post / sd_post)),
        "p_sr_gt_prior": float(norm.cdf((mean_post - prior_sr_ann) / sd_post)),
        "ci95": (float(mean_post - 1.96 * sd_post), float(mean_post + 1.96 * sd_post)),
        "shrinkage_weight_data": float(prec_data / prec_post),
    }


@dataclass(frozen=True)
class AltValidationReport:
    sharpe_ann: float
    n_obs: int
    years: float
    # lens 1 — Harvey-Liu / BHY FDR t-hurdle
    t_adj: float
    t_naive: float
    hlz_hurdle: float
    pass_fdr: bool
    # lens 2 — effective-N deflated Sharpe (hybrid)
    nominal_n: int
    effective_n: float
    dsr_eff: float
    sr0_eff_ann: float
    dsr_nominal: float
    sr0_nominal_ann: float
    pass_eff_dsr: bool
    # lens 3 — Bayesian shrinkage
    posterior_mean_sr: float
    posterior_p_gt_0: float
    pass_bayes: bool
    # verdict
    n_lenses_pass: int
    verdict: str

    def __str__(self) -> str:
        return (
            f"Sharpe {self.sharpe_ann:.2f} over {self.years:.1f}y | "
            f"[FDR] t_adj {self.t_adj:.2f} vs {self.hlz_hurdle:.2f} "
            f"{'PASS' if self.pass_fdr else 'fail'} | "
            f"[effN-DSR] N {self.nominal_n}->{self.effective_n:.1f}, "
            f"DSR {self.dsr_nominal:.2f}->{self.dsr_eff:.2f} (sr0 "
            f"{self.sr0_nominal_ann:.2f}->{self.sr0_eff_ann:.2f}) "
            f"{'PASS' if self.pass_eff_dsr else 'fail'} | "
            f"[Bayes] post-mean {self.posterior_mean_sr:.2f}, P(SR>0) "
            f"{self.posterior_p_gt_0:.3f} {'PASS' if self.pass_bayes else 'fail'} | "
            f"=> {self.n_lenses_pass}/3 {self.verdict}"
        )


def validate_strategy_alt(
    returns: pd.Series,
    *,
    nominal_n_trials: int,
    returns_matrix: pd.DataFrame | None = None,
    effective_n: float | None = None,
    hlz_hurdle: float = 3.0,
    prior_sr_ann: float = 0.5,
    prior_sd_ann: float = 0.5,
    min_dsr: float = 0.95,
    bayes_p: float = 0.95,
    freq: float = ANN,
) -> AltValidationReport:
    """Run the Harvey-Liu / FDR / Bayesian alternative gate on per-period returns
    sampled at ``freq`` periods/year. Three independent lenses; the verdict reports
    how many pass (majority = a defensible "real").

    ``returns_matrix`` (time x strategies) is used to estimate the EFFECTIVE number
    of independent trials via the correlation-eigenvalue participation ratio; pass
    ``effective_n`` directly to override. ``hlz_hurdle`` defaults to the HLZ
    recommended t>3.0 (use HLZ_T_HURDLES for the band). Prior defaults encode a
    skeptical-but-positive cross-asset momentum/carry premium (annual Sharpe ~0.5)."""
    from scipy.stats import kurtosis as _kurtosis
    from scipy.stats import skew as _skew

    r = pd.Series(returns).dropna().astype(float)
    n = len(r)
    mu, sd = float(r.mean()), float(r.std(ddof=1))
    sr_per = mu / sd if sd > 1e-12 else 0.0
    sk = float(_skew(r)) if n > 2 else 0.0
    ku = float(_kurtosis(r, fisher=False)) if n > 3 else 3.0
    sr_ann = sr_per * math.sqrt(freq)
    years = n / freq

    # lens 1 — FDR / Harvey-Liu t-hurdle (skew/kurt aware)
    t_adj = skew_kurt_adjusted_tstat(sr_per, n, sk, ku)
    t_naive = sr_ann * math.sqrt(max(years, 1e-9))
    pass_fdr = t_adj >= hlz_hurdle

    # lens 2 — effective-N deflated Sharpe (the hybrid, clearly labelled)
    if effective_n is None:
        effective_n = (
            effective_n_trials(returns_matrix)
            if returns_matrix is not None and returns_matrix.shape[1] >= 2
            else float(nominal_n_trials)
        )
    if not np.isfinite(effective_n):  # degenerate matrix -> no discount, use nominal
        effective_n = float(nominal_n_trials)
    eff_n_int = max(2, int(round(effective_n)))
    dsr_eff, sr0_eff = deflated_sharpe_ratio(sr_per, n, sk, ku, eff_n_int)
    dsr_nom, sr0_nom = deflated_sharpe_ratio(sr_per, n, sk, ku, nominal_n_trials)
    pass_eff_dsr = dsr_eff >= min_dsr

    # lens 3 — Bayesian shrinkage toward a cross-asset momentum/carry prior
    post = bayesian_sharpe_posterior(
        sr_ann, n, prior_sr_ann=prior_sr_ann, prior_sd_ann=prior_sd_ann,
        skew=sk, kurt=ku, freq=freq,
    )
    pass_bayes = post["p_sr_gt_0"] >= bayes_p

    n_pass = int(pass_fdr) + int(pass_eff_dsr) + int(pass_bayes)
    verdict = {0: "FAIL", 1: "WEAK", 2: "DEFENSIBLE", 3: "PASS"}[n_pass]

    return AltValidationReport(
        sharpe_ann=sr_ann, n_obs=n, years=years,
        t_adj=t_adj, t_naive=t_naive, hlz_hurdle=hlz_hurdle, pass_fdr=pass_fdr,
        nominal_n=nominal_n_trials, effective_n=float(effective_n),
        dsr_eff=dsr_eff, sr0_eff_ann=sr0_eff * math.sqrt(freq),
        dsr_nominal=dsr_nom, sr0_nominal_ann=sr0_nom * math.sqrt(freq),
        pass_eff_dsr=pass_eff_dsr,
        posterior_mean_sr=post["posterior_mean"], posterior_p_gt_0=post["p_sr_gt_0"],
        pass_bayes=pass_bayes,
        n_lenses_pass=n_pass, verdict=verdict,
    )


__all__ = [
    "HLZ_T_HURDLES",
    "benjamini_yekutieli_constant",
    "skew_kurt_adjusted_tstat",
    "bayesian_sharpe_posterior",
    "AltValidationReport",
    "validate_strategy_alt",
]
