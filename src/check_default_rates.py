"""Default rate for each loan year, using my draft default rule.

The rule: a loan defaults if, in its first 24 months, it is 90 or more days late, the lender takes
the property (RA), or it ends with zero balance code 03 or 09. A loan that is paid off early (01)
without being 90 days late is not a default.

Months are counted from the month of the first payment, not with the loan age column, because loan
age restarts after a modification. compare_default_rules.py shows how much that matters.

Columns are counted from 0, as in the code.
  performance file: 0 loan id, 1 month, 3 delinquency status, 7 modification flag, 8 zero balance code
  origination file: 1 first payment date, 19 loan id

Run it from the project folder:
    python src/check_default_rates.py          all years
    python src/check_default_rates.py 2007     one year
"""
import sys
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
WINDOW = 24  # months, counted from the first payment month


def to_idx(yyyymm):
    # turn YYYYMM into a month number, so months can be subtracted
    p = pd.to_numeric(yyyymm, errors="coerce")
    return (p // 100) * 12 + (p % 100)


def loan_outcomes(year):
    """One row per loan with its default flags. This is the only place the default rule is applied."""
    # first payment date and loan id from the origination file
    o = pd.read_csv(RAW / f"sample_orig_{year}.txt", sep="|", header=None, dtype=str,
                    keep_default_na=False, usecols=[1, 19])
    orig_ids = o[19]
    # loan id -> first payment month
    fp_idx = pd.Series(to_idx(o[1]).to_numpy(), index=orig_ids.to_numpy())

    parts = []
    # the performance file is big, so read it in chunks
    for ch in pd.read_csv(RAW / f"sample_perf_{year}.txt", sep="|", header=None, dtype=str,
                          keep_default_na=False, usecols=[0, 1, 3, 7, 8], chunksize=1_000_000):
        ch.columns = ["id", "period", "dq", "mod", "zb"]
        # months since the first payment, by the calendar (not the loan age column, which restarts after a modification)
        cal = to_idx(ch["period"]) - ch["id"].map(fp_idx) + 1
        dq = pd.to_numeric(ch["dq"], errors="coerce")  # 'RA' and 'XX' become NaN
        zb = ch["zb"].fillna("").str.strip()
        in_window = cal <= WINDOW
        # late = 90 or more days late, or the lender took the property
        late = (dq >= 3) | (ch["dq"] == "RA")
        # default = late, or ended with code 03 or 09, inside the 24 months
        # dB also counts code 02, to see if that makes a difference
        # then one row per loan: True if any month shows it
        parts.append(pd.DataFrame({
            "id": ch["id"],
            "dA": (late | zb.isin(["03", "09"])) & in_window,
            "dB": (late | zb.isin(["02", "03", "09"])) & in_window,
            "cal": cal, "ended": zb != "",
            "modified": ch["mod"].str.strip() != "",
            # modified inside the 24 months?
            "mod_in_window": (ch["mod"].str.strip() != "") & in_window,
        }).groupby("id").max())
    # a loan can be split over several chunks, so combine again
    loans = pd.concat(parts).groupby(level=0).max()
    # every loan must be in the origination file, otherwise its months are unknown
    assert loans["cal"].notna().all(), "some performance loans have no first payment date in the origination file"
    # unknown outcome: no default, still active, and seen for less than 24 months (it could still default later)
    loans["unknown"] = (~loans["dA"]) & (~loans["ended"]) & (loans["cal"] < WINDOW)
    return loans, orig_ids


def vintage_summary(year):
    loans, orig_ids = loan_outcomes(year)
    unknown = loans["unknown"]
    kept = loans[~unknown]
    return {
        "vintage": year,
        "orig_loans": orig_ids.nunique(),
        "orig_ids_in_perf_%": round(100 * orig_ids.isin(loans.index).mean(), 2),
        "outcome_unknown_dropped": int(unknown.sum()),
        "kept": len(kept),
        "defaults": int(kept["dA"].sum()),
        "default_rate_%": round(float(100 * kept["dA"].mean()), 2),
        "default_rate_with_code02_%": round(float(100 * kept["dB"].mean()), 2),
        "modified_loans_%": round(float(100 * kept["modified"].mean()), 2),
    }


if __name__ == "__main__":
    years = [int(a) for a in sys.argv[1:]] or list(range(2002, 2008))
    rows = []
    for y in years:
        rows.append(vintage_summary(y))
        print(rows[-1], flush=True)
    print()
    print(pd.DataFrame(rows).to_string(index=False))
