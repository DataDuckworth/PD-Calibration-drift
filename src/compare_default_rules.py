"""Compare two ways of counting the 24 months: the loan age column (rule A) and calendar months (rule C).

Loan age restarts after a modification. With rule A, a default long after the loan started can
still count as "inside 24 months". Rule C counts months from the first payment month, so it does
not have this problem. The default event is the same in both: 90 or more days late, RA, or zero
balance code 03 or 09.

Columns are counted from 0, as in the code.
  performance file: 0 loan id, 1 month, 3 delinquency status, 4 loan age, 7 modification flag, 8 zero balance code
  origination file: 1 first payment date, 19 loan id

Run it from the project folder:
    python src/compare_default_rules.py          all years
    python src/compare_default_rules.py 2007     one year
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_default_rates import to_idx, RAW, WINDOW  # noqa: E402


def compare_year(year):
    # first payment month for each loan, needed for rule C
    o = pd.read_csv(RAW / f"sample_orig_{year}.txt", sep="|", header=None, dtype=str,
                    keep_default_na=False, usecols=[1, 19])
    fp_idx = pd.Series(to_idx(o[1]).to_numpy(), index=o[19].to_numpy())

    parts = []
    # the performance file is big, so read it in chunks
    for ch in pd.read_csv(RAW / f"sample_perf_{year}.txt", sep="|", header=None, dtype=str,
                          keep_default_na=False, usecols=[0, 1, 3, 4, 7, 8], chunksize=1_000_000):
        ch.columns = ["id", "period", "dq", "age", "mod", "zb"]
        # two ways to measure the time since the loan started
        age = pd.to_numeric(ch["age"], errors="coerce")             # rule A: the loan age column (restarts after a modification)
        cal = to_idx(ch["period"]) - ch["id"].map(fp_idx) + 1       # rule C: calendar months since the first payment
        dq = pd.to_numeric(ch["dq"], errors="coerce")
        # same default event, only the window is different
        event = (dq >= 3) | (ch["dq"] == "RA") | ch["zb"].isin(["03", "09"])
        ended = ch["zb"].str.strip() != ""
        # per loan: default under A, default under C, modified or not
        parts.append(pd.DataFrame({
            "id": ch["id"],
            "defA": event & (age <= WINDOW),
            "defC": event & (cal <= WINDOW),
            "modified": ch["mod"].str.strip() != "",
            "ended": ended,
            "ageA": age, "calC": cal,
        }).groupby("id").agg(defA=("defA", "max"), defC=("defC", "max"), modified=("modified", "max"),
                             ended=("ended", "max"), ageA=("ageA", "max"), calC=("calC", "max")))
    g = pd.concat(parts).groupby(level=0).max()
    assert g["calC"].notna().all(), "some performance loans have no first payment date in the origination file"

    unknownA = (~g["defA"]) & (~g["ended"]) & (g["ageA"] < WINDOW)
    unknownC = (~g["defC"]) & (~g["ended"]) & (g["calC"] < WINDOW)
    a, c = g[~unknownA], g[~unknownC]
    differ = g["defA"] != g["defC"]
    mod = g["modified"]
    return {
        "vintage": year,
        "rate_A_age_%": round(float(100 * a["defA"].mean()), 2),
        "rate_C_calendar_%": round(float(100 * c["defC"].mean()), 2),
        "loans_where_rules_differ": int(differ.sum()),
        "...of which modified": int((differ & mod).sum()),
        "modified_loans_%": round(float(100 * mod.mean()), 2),
        "rate_C_modified_loans_%": round(float(100 * g.loc[mod, "defC"].mean()), 1) if mod.any() else None,
        "rate_C_unmodified_loans_%": round(float(100 * g.loc[~mod, "defC"].mean()), 2),
        "unknown_A": int(unknownA.sum()), "unknown_C": int(unknownC.sum()),
    }


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or list(range(2002, 2008))
    rows = []
    for y in years:
        rows.append(compare_year(y))
        print(rows[-1], flush=True)
    print()
    print(pd.DataFrame(rows).to_string(index=False))
