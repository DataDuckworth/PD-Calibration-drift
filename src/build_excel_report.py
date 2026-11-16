"""Build an Excel workbook that summarises the analysis.

Run it from the project folder:
    python src/build_excel_report.py

It writes results/tables/pd_analysis_summary.xlsx. The numbers come from three places:
- data/processed/loans.parquet (from build_modelling_table.py): default rates, borrower profile and so on
- the saved outputs of notebooks 01b, 02 and 02b: data quality checks, rule comparison, column decisions
  (run those notebooks again first if the data or the rules change)
- the tables in results/tables from notebooks 02c, 03 and 04: features, baseline models, calibration

The workbook only holds summary numbers, no loan-level data.
"""
import io
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from columns import ORIG_COLUMNS, PERF_COLUMNS, NOT_AVAILABLE  # noqa: E402

OUT = ROOT / "results" / "tables" / "pd_analysis_summary.xlsx"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
PERF_USED = {"loan_id", "reporting_period", "current_upb", "delinquency_status", "loan_age",
             "modification_flag", "zero_balance_code"}


def notebook_table(notebook, marker, index_col=0):
    """Read the table that a notebook cell saved as HTML (the cell whose code contains marker)."""
    nb = json.load(open(ROOT / "notebooks" / f"{notebook}.ipynb", encoding="utf8"))
    for cell in nb["cells"]:
        if cell["cell_type"] == "code" and marker in "".join(cell["source"]):
            for out in cell["outputs"]:
                if out["output_type"] == "execute_result" and "text/html" in out["data"]:
                    html = "".join(out["data"]["text/html"])
                    df = pd.read_html(io.StringIO(html), index_col=index_col)[0]
                    # drop the extra header row
                    if df.columns.nlevels > 1:
                        df.columns = df.columns.get_level_values(0)
                    return df
    raise ValueError(f"no saved table found in {notebook} for marker {marker!r}")


def margin(rate_pct, n):
    # 95% sampling margin of a rate, in percentage points
    p = rate_pct / 100
    return 1.96 * np.sqrt(p * (1 - p) / n) * 100


def build_sheets():
    t = pd.read_parquet(ROOT / "data" / "processed" / "loans.parquet")
    tables = ROOT / "results" / "tables"
    sheets = {}

    # default rate by year
    g = t.groupby(["group", "vintage"]).agg(
        loans=("loan_id", "count"), defaults=("default_24m", "sum"),
        modified_in_window=("modified_in_window", "sum"), modified_ever=("modified_ever", "sum")).reset_index()
    g["default_rate_%"] = (100 * g["defaults"] / g["loans"]).round(2)
    g["margin_95%_(+/-)"] = [round(margin(r, n), 2) for r, n in zip(g["default_rate_%"], g["loans"])]
    g["modified_ever_%"] = (100 * g["modified_ever"] / g["loans"]).round(2)
    g = g.sort_values("vintage")
    sheets["Default rate by year"] = g[["vintage", "group", "loans", "defaults", "default_rate_%", "margin_95%_(+/-)",
                                        "modified_in_window", "modified_ever", "modified_ever_%"]]

    # train / transition / test groups
    s = t.groupby("group").agg(loans=("loan_id", "count"), defaults=("default_24m", "sum")).reindex(
        ["train", "transition", "test"])
    s["default_rate_%"] = (100 * s["defaults"] / s["loans"]).round(2)
    yrs = t.groupby("group")["vintage"].agg(lambda v: str(v.min()) if v.min() == v.max() else f"{v.min()}-{v.max()}")
    s.insert(0, "years", yrs.reindex(s.index))
    sheets["Groups"] = s.reset_index()

    # old rule against new rule (saved by notebook 02)
    cmp_ = notebook_table("02_default_definition", "comparison = pd.DataFrame(cmp_rows)")
    sheets["Rule comparison"] = cmp_.rename_axis("vintage").reset_index()

    # borrower profile by year (middle values, after the "Not Available" codes became blanks)
    prof = t.groupby("vintage")[["credit_score", "ltv", "combined_ltv", "dti", "interest_rate", "original_upb"]].median().round(2)
    prof["first_time_buyer_%"] = (100 * t.groupby("vintage")["first_time_homebuyer"].apply(lambda s: (s == "Y").mean())).round(2)
    prof["investor_%"] = (100 * t.groupby("vintage")["occupancy_status"].apply(lambda s: (s == "I").mean())).round(2)
    sheets["Borrower profile"] = prof.reset_index()

    # features of defaulted and non-defaulted loans (training years only)
    tr = t[t["group"] == "train"]
    feats = tr.groupby("default_24m")[["credit_score", "ltv", "combined_ltv", "dti", "interest_rate", "original_upb"]].median().round(1)
    feats.index = ["did not default", "defaulted"]
    sheets["Features by outcome"] = feats.rename_axis("training years 2002-2004 (medians)").reset_index()

    # feature selection (notebook 02c), baseline models (03), calibration and recalibration (04)
    sheets["Feature selection"] = pd.read_csv(tables / "feature_summary.csv")
    base = pd.read_csv(tables / "baseline_metrics.csv")
    keep_cols = ["model", "test set", "loans", "defaults", "actual %", "predicted %", "predicted / actual",
                 "ratio low", "ratio high", "AUC", "AUC low", "AUC high", "Brier", "Brier skill", "log loss"]
    sheets["Baseline models"] = base[keep_cols].round(4)
    cal_cols = ["model", "set", "actual %", "predicted %", "predicted / actual", "level shift", "slope",
                "slope low", "slope high", "reliability", "resolution", "ECE %", "binomial test p", "log loss"]
    sheets["Calibration"] = pd.read_csv(tables / "calibration_metrics.csv")[cal_cols].round(4)
    sheets["Recalibration"] = pd.read_csv(tables / "recalibration_results.csv").round(4)

    # the "Not Available" codes and how many loans have them
    rows = []
    for col, code in NOT_AVAILABLE.items():
        if col in t.columns:
            rows.append({"column": col, "code_meaning_not_available": code,
                         "blank_after_cleaning": int(t[col].isna().sum()),
                         "share_of_loans_%": round(100 * t[col].isna().mean(), 2)})
    sheets["Not Available codes"] = pd.DataFrame(rows)

    # data quality checks (saved by notebook 01b)
    sheets["Quality checks"] = notebook_table("01b_data_quality_checks", "summary = pd.DataFrame(checks)").reset_index(drop=True)
    perf = notebook_table("01b_data_quality_checks", "perf_res.T").rename_axis("check").reset_index()
    sheets["Performance checks by year"] = perf
    sheets["Origination column profile"] = notebook_table("01b_data_quality_checks", "profile = pd.DataFrame").rename_axis("position").reset_index()

    # column lists
    plan = notebook_table("02b_modelling_table", "plan = pd.DataFrame(decision").rename_axis("column")
    plan = plan.reindex(ORIG_COLUMNS).reset_index()      # in file order
    plan.insert(0, "position", range(len(plan)))
    # these two columns come from the 2005 file only
    plan = plan.rename(columns={"distinct values": "distinct values (2005 file)", "blank %": "blank % (2005 file)"})
    sheets["Origination columns"] = plan
    perf_cols = pd.DataFrame({"position": range(len(PERF_COLUMNS)), "column": PERF_COLUMNS})
    perf_cols["used_in_this_analysis"] = np.where(perf_cols["column"].isin(PERF_USED), "yes", "no")
    sheets["Performance columns"] = perf_cols
    return sheets


def readme_sheet():
    lines = [
        ("PD calibration drift: analysis summary", True),
        (f"Made on {date.today().isoformat()} from the Freddie Mac Single-Family Loan-Level sample files, loan years 2002-2007 (50,000 loans per year).", False),
        ("", False),
        ("Read this first", True),
        ("- This is an exploratory first pass: one dataset and one crisis. It is not a final result.", False),
        ("- The models were trained on 2002-2004 only and tested on 2005, 2006 and 2007. The test years were never used to tune anything.", False),
        ("- The default rule is a draft: default = 90+ days late, the lender took the property, or a short sale / property sale (zero balance code 03 or 09) within 24 calendar months of the first payment.", False),
        ("- Modified loans are kept and flagged. The flags are for analysis only, because a modification happens after the loan starts.", False),
        ("- Each year is a sample of 50,000 loans, so it may not represent all Freddie Mac loans of that year.", False),
        ("- No loan-level data is included. The Freddie Mac terms do not allow sharing the data.", False),
        ("", False),
        ("Sheets", True),
        ("Default rate by year: loans, defaults, default rate with a 95% sampling margin, and modified loans. The margin only covers sampling noise; it ignores that loans of one year share the same economy.", False),
        ("Groups: training (2002-2004), transition (2005) and test (2006-2007).", False),
        ("Rule comparison: rate_A uses the loan age column (the old rule). It overstates defaults for modified loans because loan age restarts after a modification. rate_C is the calendar rule used everywhere else.", False),
        ("Borrower profile: median credit score, loan-to-value, debt-to-income, rate and balance by year.", False),
        ("Features by outcome: medians for defaulted and non-defaulted loans in the training years.", False),
        ("Feature selection: information value, tests, stability and the decision for every candidate feature (notebook 02c).", False),
        ("Baseline models: AUC, predicted against actual default rate, Brier score and log loss for six models on each test set, with 95% intervals (notebook 03). The intervals ignore that loans of one year share an economy, so they are a little too narrow.", False),
        ("Calibration: how far the predicted default rate is from the actual one, the calibration slope, and the Brier score split into reliability and resolution (notebook 04).", False),
        ("Recalibration: what Platt scaling, isotonic regression and a base-rate correction do. The two 'oracle' methods use the test year's own outcomes, so they show an upper limit and are not a usable method (notebook 04).", False),
        ("Not Available codes: the codes defined in the user guide and how many loans have them.", False),
        ("Quality checks / Performance checks by year / Origination column profile: results of notebook 01b.", False),
        ("Origination columns / Performance columns: column names (from the user guide's order) and how each is used.", False),
    ]
    return pd.DataFrame(lines, columns=["text", "bold"])


def style_sheet(ws):
    for cell in ws[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    for i, col in enumerate(ws.columns, start=1):
        width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 70)


def main():
    sheets = build_sheets()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        readme = readme_sheet()
        readme[["text"]].to_excel(xw, sheet_name="Read me", index=False, header=False)
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)

        ws = xw.sheets["Read me"]
        ws.column_dimensions["A"].width = 130
        for row, bold in zip(ws.iter_rows(min_row=1, max_row=len(readme)), readme["bold"]):
            row[0].font = Font(bold=bool(bold), size=14 if row[0].row == 1 else 11)
            row[0].alignment = Alignment(wrap_text=True, vertical="top")

        for name in sheets:
            style_sheet(xw.sheets[name[:31]])

        # bar chart of the default rate by year
        ws = xw.sheets["Default rate by year"]
        chart = BarChart()
        chart.type, chart.title = "col", "Default within 24 months, by loan year (%)"
        chart.y_axis.title, chart.x_axis.title = "default rate (%)", "year the loan started"
        chart.add_data(Reference(ws, min_col=5, min_row=1, max_row=ws.max_row), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=ws.max_row))
        chart.legend = None
        chart.height, chart.width = 8, 16
        ws.add_chart(chart, "K2")
    print("Wrote", OUT)
    for name, df in sheets.items():
        print(f"  {name:30s} {df.shape[0]:>3} rows x {df.shape[1]:>2} columns")


if __name__ == "__main__":
    main()
