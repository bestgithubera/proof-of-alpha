"""Tests for the Harvey-Liu / FDR / Bayesian alternative gate."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from validation import alt as VA


def test_by_constant_grows_like_log_not_n():
    # c(N) ~ ln(N) + gamma; for 151k it must be ~12.5, NOT ~151000
    c = VA.benjamini_yekutieli_constant(151_521)
    assert 12.0 < c < 13.0
    assert VA.benjamini_yekutieli_constant(1) == 1.0
    # monotone increasing, but only logarithmically
    assert VA.benjamini_yekutieli_constant(10) < VA.benjamini_yekutieli_constant(1000) < c


def test_adjusted_tstat_matches_naive_under_normal():
    # under (near) normal iid returns, t_adj ~= SR_per * sqrt(n_obs)
    rng = np.random.default_rng(0)
    n = 2000
    r = rng.normal(0.001, 0.01, n)
    sr_per = r.mean() / r.std(ddof=1)
    t_adj = VA.skew_kurt_adjusted_tstat(sr_per, n, float(pd.Series(r).skew()),
                                        float(pd.Series(r).kurtosis() + 3.0))
    t_naive = sr_per * math.sqrt(n)
    assert t_adj == pytest.approx(t_naive, rel=0.1)


def test_negative_skew_fat_tails_lower_the_tstat():
    # fat-tailed, negatively-skewed returns must be PENALISED (lower t_adj) vs normal
    n = 1500
    sr_per = 0.05
    normal_t = VA.skew_kurt_adjusted_tstat(sr_per, n, 0.0, 3.0)
    fat_t = VA.skew_kurt_adjusted_tstat(sr_per, n, -1.0, 8.0)
    assert fat_t < normal_t


def test_bayesian_shrinkage_blends_prior_and_sample():
    # posterior mean must lie strictly between a positive prior and a higher sample
    out = VA.bayesian_sharpe_posterior(2.0, 1095, prior_sr_ann=0.5, prior_sd_ann=0.5)
    assert 0.5 < out["posterior_mean"] < 2.0
    assert 0.0 <= out["p_sr_gt_0"] <= 1.0
    assert 0.0 < out["shrinkage_weight_data"] < 1.0


def test_strong_positive_prior_lifts_p_sr_gt_0_vs_null_prior():
    # the whole point: a positive prior gives higher P(SR>0) than a null prior
    p_null = VA.bayesian_sharpe_posterior(1.0, 400, prior_sr_ann=0.0, prior_sd_ann=0.5)["p_sr_gt_0"]
    p_pos = VA.bayesian_sharpe_posterior(1.0, 400, prior_sr_ann=0.5, prior_sd_ann=0.5)["p_sr_gt_0"]
    assert p_pos > p_null


def test_alt_gate_passes_a_strong_correlated_signal():
    # a Sharpe ~2 strategy over 3y with effective-N small should clear >=2/3 lenses
    rng = np.random.default_rng(1)
    n = 1095  # ~3 years of daily crypto bars
    z = rng.normal(0.0, 1.0, n)
    z = (z - z.mean()) / z.std(ddof=1)          # standardise, then impose exact SR
    daily = 0.01 * (z + 2.0 / math.sqrt(365))    # SR_ann == 2.0 by construction
    r = pd.Series(daily)
    rep = VA.validate_strategy_alt(r, nominal_n_trials=151_521, effective_n=1.6, hlz_hurdle=3.0)
    assert rep.n_lenses_pass >= 2
    # and the nominal-N deflation is strictly harsher than the effective-N one
    assert rep.sr0_nominal_ann > rep.sr0_eff_ann
    assert rep.dsr_eff > rep.dsr_nominal
