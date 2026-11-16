# PD Calibration Drift :

Do loan default predictions stay accurate when the economy changes? A small study using Freddie Mac mortgage data.

## The problem, in simple words :

Banks use a model to guess how likely each loan is to default (not be repaid). This guess is called the **Probability of Default (PD)**. The bank uses it to decide how much money to set aside for losses.

Here is a simple example. The numbers are made up, to explain the idea.

- In 2004 the bank builds a model. It says a certain type of loan has a **2%** chance of default.
- That is right at the time: out of 100 such loans, about 2 default.
- In 2007 house prices fall and many people lose their jobs. Now **8** out of 100 of the **same type of loan** default.
- The model still says 2%. It still puts risky loans above safe ones, so it looks fine on the usual ranking score.
- But the **numbers are wrong**, so the bank sets aside far too little money.

Ranking borrowers well is not the same as giving correct probabilities. Checking that the probabilities match reality is called **calibration**.

## Research question :

> If I train a default model on calm years and test it on stressed years, does its calibration get worse even when its ranking stays good? Does re-calibrating the model fix it?

## What I did :

| Step | What | Where |
|---|---|---|
| 1 | Looked at the data: 6 loan years (2002-2007), 50,000 loans each | notebook 01 |
| 2 | Checked its quality: blanks, hidden codes, duplicates, dates, ranges, links between the two files | notebook 01b |
| 3 | Defined a default: 90+ days late, the lender took the property, or a short sale / property sale, within 24 months of the first payment | notebook 02 |
| 4 | Built one table with one row per loan | notebook 02b |
| 5 | Chose features, using the training years only, with statistical tests | notebook 02c |
| 6 | Trained two models on 2002-2004 (logistic regression and gradient boosting) and tested them on 2005, 2006 and 2007 | notebook 03 |
| 7 | Measured calibration and tried to fix it with recalibration | notebook 04 |

The calm years 2002-2004 are used for training. 2005 is a middle year. 2006 and 2007 are the stressed years. The test years were never used to tune anything.

## Results :

**Default rate by loan year** (draft rule):

| Year | 2002 | 2003 | 2004 | 2005 | 2006 | 2007 |
|---|---|---|---|---|---|---|
| Default rate | 0.87% | 0.43% | 0.79% | 1.05% | 1.94% | 4.90% |

**Logistic regression, trained on 2002-2004:**

| Test set | Ranking (AUC) | Predicted default rate | Actual default rate | Predicted / actual |
|---|---|---|---|---|
| Hold-out from the training years | 0.85 | 0.70% | 0.70% | 1.00 |
| 2005 | 0.81 | 0.78% | 1.05% | 0.74 |
| 2006 | 0.79 | 0.82% | 1.94% | 0.42 |
| 2007 | 0.77 | 0.88% | 4.90% | 0.18 |

Gradient boosting gives the same picture (predicted / actual of 0.69, 0.47 and 0.21 for 2005, 2006 and 2007).

What the calibration analysis shows:

- **Ranking stays decent, the probabilities do not.** The models still put risky loans above safe ones in the crash years. But the predicted default rate hardly moves (0.78% to 0.88%) while the real one goes from 1.05% to 4.90%.
- **It is not only a level shift.** The calibration slope falls from about 0.94 to 0.71 (logistic) and 0.63 (boosting), so the predictions are also too spread out. In 2007 the safest tenth of loans was predicted at 0.04% and defaulted at 0.44%.
- **Recalibration fitted on the calm years does almost nothing** out of time (predicted / actual stays at 0.76, 0.43 and 0.18 with Platt scaling). In the calm years the model was already calibrated, so there is nothing to learn.
- **A correction using an old default rate does not help either.** Using the rate from two years earlier gives 0.41, 0.41 and 0.21.
- **If the true default rate were known,** a simple shift would fix most of the problem and cut the 2007 log loss from 0.2235 to 0.1759. But the true rate is the thing you are trying to forecast, so this shows an upper limit and is not a usable method.

What this suggests: the failure is mostly a change in the overall default rate that the borrower's features do not show. That fits a change in the economy and not a change in who borrowed. It is consistent with that explanation, and I have not proved it.

## Limits :

- One dataset and one crisis, so I cannot say this happens every time.
- The default rule is a draft. How to treat modified loans (they default far more often) is still open.
- Each year is a sample of 50,000 loans. The calm years have only about 1,050 defaults in total, which is not many for a flexible model.
- Loans from the same year share the same economy, so the intervals in the notebooks are a little too narrow.
- A few of the comparisons (for example with and without `state`) were looked at on the test years, so they are observations and not choices.
- Not done yet: whether uncertainty from Bayesian or ensemble models can warn about the shift. That part of the original idea is still open.

## Project layout :

```
PD-Calibration-drift/
├── data/
│   ├── raw/          Freddie Mac files (not in git)
│   └── processed/    tables and predictions made by the scripts and notebooks (not in git)
├── docs/             user guide and papers (not in git)
├── notebooks/        01, 01b, 02, 02b, 02c, 03, 04 (see "What I did")
├── src/              the scripts
└── results/
    ├── figures/      charts
    └── tables/       result tables and the Excel summary
```

The scripts in `src/`:

| Script | What it does |
|---|---|
| `columns.py` | Column names for the two file types, and the "Not Available" codes |
| `check_default_rates.py` | The default rule, and the default rate by year |
| `compare_default_rules.py` | Compares counting 24 months by loan age and by calendar months |
| `build_modelling_table.py` | Builds the table with one row per loan |
| `features.py` | Extra features, and helpers to check features (information value, stability) |
| `build_excel_report.py` | Builds `results/tables/pd_analysis_summary.xlsx` |

## How to run it :

1. Install Python 3.12, then in the project folder: `python -m venv .venv`, activate it, and `pip install -r requirements.txt`.
2. Download the data (see below) into `data/raw/`.
3. `python src/build_modelling_table.py`
4. Run the notebooks `02c`, then `03`, then `04`, in that order. Each one saves what the next one needs.
5. `python src/build_excel_report.py` (uses the saved outputs of notebooks 01b, 02 and 02b, so run those once first).

## Data :

The data are not included, and Freddie Mac does not allow sharing them.

1. Register and download the sample files from the [Freddie Mac Single-Family Loan-Level Dataset](https://freddiemac.com/research/datasets/sf-loanlevel-dataset) for 2002-2007.
2. Put the unzipped files in `data/raw/`.
3. Use the [user guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf) to check column names and codes.

Choose the Single-Family dataset, not the Credit Risk Transfer files. Those have a different layout and start much later.

## Most usefull research papers :

None of these is about credit, so they help me ask the question and do not answer it. I read them from the links, and the PDFs are not stored here.

- [Guo et al. 2017](https://arxiv.org/abs/1706.04599): what "calibrated" means, and how a simple fix works. It assumes the training and test data look alike, which is the thing I want to break.
- [Ovadia et al. 2019](https://arxiv.org/abs/1906.02530): how uncertainty and calibration behave when data shift. They report that post-hoc calibration did not hold up under shift.
- [Lakshminarayanan et al. 2017](https://arxiv.org/abs/1612.01474): a simple ensemble of models can give good uncertainty, so I should not assume fancier Bayesian methods are better.
- [Kull et al. 2017](https://proceedings.mlr.press/v54/kull17a.html): beta calibration, a possible alternative to Platt scaling.

Whether this exact question has already been studied on credit data is something I still have to check in a proper literature review.

## License :

MIT. See [LICENSE](LICENSE).
