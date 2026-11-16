"""Extra features, and helper functions for checking features.

Only information known when the loan starts is used.
  add_features        adds log_upb, ltv_gap, state_region and rate_spread (the ENGINEERED list)
  numeric_bins, categorical_bins   cut a feature into groups
  iv_table            information value of a feature that has been cut into groups
  iv_from_codes       the same, but fast (used by the permutation test)
  permutation_iv      information value plus a test against pure noise
  psi                 population stability index, how much a feature shifted
"""
import numpy as np
import pandas as pd

# US Census regions. PR, GU and VI are territories.
REGION = {}
for region, states in {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
    "Territory": "PR GU VI",
}.items():
    for s in states.split():
        REGION[s] = region

ENGINEERED = ["log_upb", "ltv_gap", "state_region", "rate_spread"]


def add_features(df):
    """Return a copy of the table with the extra features added.

    Use the whole table, not a piece of a year: rate_spread uses the median rate of each loan year.
    """
    out = df.copy()
    if out.groupby("vintage").size().min() < 1000:
        raise ValueError("add_features needs whole loan years: the yearly median rate would be unreliable")
    # balance on a log scale, so a few very large loans do not dominate
    out["log_upb"] = np.log(out["original_upb"])
    # combined LTV minus LTV: above zero means there is a second loan on the property
    out["ltv_gap"] = out["combined_ltv"] - out["ltv"]
    # 54 states grouped into 5 regions
    out["state_region"] = out["state"].map(REGION)
    # the loan's rate minus the median rate of loans from the same year (a rough market rate at the time),
    # so it shows how expensive the loan was for its year and not which year it was
    out["rate_spread"] = out["interest_rate"] - out.groupby("vintage")["interest_rate"].transform("median")
    return out


def numeric_bins(x, q=10, edges=None, max_levels=12, mode_share=0.2):
    """Cut a number column into groups. Blanks get group -1. Edges come from x unless you pass them in.

    - Few different values (up to max_levels): every value is its own group.
    - One value holds at least 20% of the loans (like 0 for mortgage insurance): that value is its
      own group, and the rest is cut into quantile groups.
    - Otherwise: ten quantile groups (deciles).
    """
    if edges is None:
        v = x.dropna()
        vals = np.sort(v.unique())
        if len(vals) <= max_levels:
            inner = (vals[:-1] + vals[1:]) / 2
        else:
            counts = v.value_counts()
            mode = counts.index[0]
            special = counts.iloc[0] / len(v) >= mode_share
            rest = v[v != mode] if special else v
            inner = np.unique(np.quantile(rest, np.linspace(0, 1, q + 1)))[1:-1]
            if special:
                extra = []
                below, above = vals[vals < mode], vals[vals > mode]
                if len(below):
                    extra.append((below.max() + mode) / 2)
                if len(above):
                    extra.append((mode + above.min()) / 2)
                inner = np.unique(np.concatenate((inner, extra)))
        edges = np.concatenate(([-np.inf], inner, [np.inf]))
    codes = pd.cut(x, bins=edges, labels=False, include_lowest=True)
    codes = codes.astype("float").where(x.notna(), -1).astype(int)
    return codes, edges


def categorical_bins(x, min_share=0.01, keep=None):
    """Groups for a text column. Rare values become 'other' and blanks become 'missing'.

    Rare means below min_share of the loans that are not blank. To cut another sample the same way,
    pass in the keep set that this function returned the first time.
    """
    x = x.astype(object)
    if keep is None:
        share = x.value_counts(normalize=True)
        keep = set(share[share >= min_share].index)
    out = x.where(x.isin(keep), "other").where(x.notna(), "missing")
    return out.astype(str), keep


def iv_table(bins, y):
    """Default rate, weight of evidence and information value for each group. Returns (table, total IV).

    A positive weight of evidence means the group is safer than average, a negative one means riskier.
    """
    t = pd.DataFrame({"bin": np.asarray(bins), "bad": np.asarray(y)})
    g = t.groupby("bin")["bad"].agg(loans="count", defaults="sum")
    g["goods"] = g["loans"] - g["defaults"]
    # add 0.5 so an empty group does not give infinity
    pb = (g["defaults"] + 0.5) / (g["defaults"].sum() + 0.5 * len(g))
    pg = (g["goods"] + 0.5) / (g["goods"].sum() + 0.5 * len(g))
    g["woe"] = np.log(pg / pb)
    g["iv"] = (pg - pb) * g["woe"]
    g["default_rate_%"] = 100 * g["defaults"] / g["loans"]
    return g, float(g["iv"].sum())


def iv_from_codes(codes, y):
    """The same information value as iv_table, but fast. codes must be whole numbers from 0 up."""
    codes, y = np.asarray(codes), np.asarray(y)
    if codes.min() < 0:
        raise ValueError("codes must be 0 or more; numeric_bins gives -1 to blanks, so use pd.factorize first")
    loans = np.bincount(codes).astype(float)
    bad = np.bincount(codes, weights=y, minlength=len(loans))
    keep = loans > 0
    bad, good = bad[keep], loans[keep] - bad[keep]
    pb = (bad + 0.5) / (bad.sum() + 0.5 * len(bad))
    pg = (good + 0.5) / (good.sum() + 0.5 * len(good))
    return float(((pg - pb) * np.log(pg / pb)).sum())


def permutation_iv(bins, y, n=1000, seed=0):
    """Returns the IV of a feature, the IVs you get from pure noise (y shuffled n times), and a p-value.

    A small p-value means the feature separates defaults better than shuffled labels do.
    The smallest possible p-value is 1 / (n + 1).
    """
    codes = pd.factorize(pd.Series(np.asarray(bins)))[0]
    y = np.asarray(y)
    iv = iv_from_codes(codes, y)
    rng = np.random.default_rng(seed)
    noise = np.array([iv_from_codes(codes, rng.permutation(y)) for _ in range(n)])
    return iv, noise, (1 + int((noise >= iv).sum())) / (n + 1)


def psi(base_bins, new_bins):
    """Population stability index between two samples cut into the same groups.

    Rule of thumb: below 0.1 is stable, 0.1 to 0.25 a moderate shift, above 0.25 a large shift.
    """
    p = pd.Series(np.asarray(base_bins)).value_counts(normalize=True)
    q = pd.Series(np.asarray(new_bins)).value_counts(normalize=True)
    idx = p.index.union(q.index)
    p = p.reindex(idx).fillna(0) + 1e-4
    q = q.reindex(idx).fillna(0) + 1e-4
    return float(((q - p) * np.log(q / p)).sum())
