"""Build the modelling table: one row per loan, for 2002-2007.

Run it from the project folder:
    python src/build_modelling_table.py

It writes data/processed/loans.parquet, and loans_columns.json which lists what each column is for.

The columns are: the keys (loan id, year, group), the target default_24m, two modification flags,
and the features. The modification flags are only for analysis. They are not features, because a
modification happens after the loan starts, so using them would give the model the answer.

Choices (provisional):
- loans with an unknown outcome are dropped (there are none in this data)
- modified loans are kept and flagged
- "Not Available" codes become blanks, with a "was missing" flag for credit score and DTI
- not used: columns that are blank or constant for every loan, dates, the loan id, the metropolitan
  area, the postal code and the seller name
- 2005 is its own group and is never used for training
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from columns import ORIG_COLUMNS, NOT_AVAILABLE          # noqa: E402
from check_default_rates import loan_outcomes, RAW  # noqa: E402

OUT = RAW.parent / "processed"      # data/processed

GROUP = {2002: "train", 2003: "train", 2004: "train", 2005: "transition", 2006: "test", 2007: "test"}

NUMERIC = ["credit_score", "mi_percent", "num_units", "combined_ltv", "dti", "original_upb", "ltv",
           "interest_rate", "loan_term", "num_borrowers"]
CATEGORICAL = ["first_time_homebuyer", "occupancy_status", "channel", "property_type", "loan_purpose",
               "prepayment_penalty", "state"]
MISSING_FLAGS = ["credit_score", "dti"]          # each of these gets a "was missing" column
ANALYSIS_FLAGS = ["modified_in_window", "modified_ever"]
KEYS = ["loan_id", "vintage", "group"]
TARGET = "default_24m"

FEATURES = NUMERIC + CATEGORICAL + [f"{c}_missing" for c in MISSING_FLAGS]
assert not set(FEATURES) & set(ANALYSIS_FLAGS + KEYS + [TARGET]), "a feature overlaps a non-feature column"


def build_year(year):
    # read as text, with the names from columns.py
    o = pd.read_csv(RAW / f"sample_orig_{year}.txt", sep="|", header=None, names=ORIG_COLUMNS,
                    dtype=str, keep_default_na=False)

    # "Not Available" codes become blanks
    for col in NUMERIC:
        o[col] = pd.to_numeric(o[col], errors="coerce")
        code = NOT_AVAILABLE.get(col)
        if code is not None:
            o.loc[o[col] == code, col] = np.nan
    for col in CATEGORICAL:
        code = NOT_AVAILABLE.get(col)
        if code is not None:
            o.loc[o[col] == code, col] = np.nan
    # "was missing" columns
    for col in MISSING_FLAGS:
        o[f"{col}_missing"] = o[col].isna().astype(int)

    # the target and the flags come from the shared default rule
    loans, _ = loan_outcomes(year)
    out = pd.DataFrame({
        "loan_id": loans.index,
        TARGET: loans["dA"].astype(int).to_numpy(),
        "modified_in_window": loans["mod_in_window"].astype(int).to_numpy(),
        "modified_ever": loans["modified"].astype(int).to_numpy(),
        "_unknown": loans["unknown"].to_numpy(),      # same definition as in check_default_rates.py
    })
    df = o.merge(out, on="loan_id", how="inner", validate="one_to_one")
    # the merge must not lose any loans
    assert len(df) == len(o), f"{len(o) - len(df)} origination loans have no performance rows"
    n_before = len(df)
    df = df[~df["_unknown"]].drop(columns="_unknown")
    df["vintage"] = year
    df["group"] = GROUP[year]
    print(f"[{year}] loans={n_before:,} kept={len(df):,} default rate={100 * df[TARGET].mean():.2f}%", flush=True)
    return df[KEYS + [TARGET] + ANALYSIS_FLAGS + FEATURES]


def main():
    table = pd.concat([build_year(y) for y in GROUP], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_parquet(OUT / "loans.parquet", index=False)
    roles = {"keys": KEYS, "target": TARGET, "analysis_flags_not_features": ANALYSIS_FLAGS,
             "numeric_features": NUMERIC, "categorical_features": CATEGORICAL,
             "missing_flags": [f"{c}_missing" for c in MISSING_FLAGS]}
    (OUT / "loans_columns.json").write_text(json.dumps(roles, indent=2), encoding="utf8")

    print(f"\nWrote {OUT / 'loans.parquet'}  shape={table.shape}")
    print(table.groupby("group")[TARGET].agg(loans="count", defaults="sum", rate_pct=lambda s: round(100 * s.mean(), 2)))
    print("\nBlank share per feature (%):")
    print((table[FEATURES].isna().mean() * 100).round(2)[lambda s: s > 0].to_string())
    print("\nModified loans (%) by group:")
    print((table.groupby("group")[ANALYSIS_FLAGS].mean() * 100).round(2))


if __name__ == "__main__":
    main()
