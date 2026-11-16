"""Column names for the Freddie Mac sample files. The files have no header row.

The names follow the order of the attributes in the Freddie Mac user guide (July 2026 glossary).
That order gives 31 origination columns and 35 performance columns, the same as the files.
I also checked the names against the values, for example loan ids in the loan id column.
If Freddie Mac changes the layout, check this list against the new guide.

NOT_AVAILABLE holds the codes the guide uses for "not available". Freddie Mac also puts them in
place of out-of-range values, for example a credit score outside 300-850 or a DTI above 65%.
"""

ORIG_COLUMNS = [
    "credit_score",                 # 0   Classic FICO
    "first_payment_date",           # 1   YYYYMM
    "first_time_homebuyer",         # 2   Y / N / 9
    "maturity_date",                # 3   YYYYMM
    "msa",                          # 4   metropolitan area (blank if none)
    "mi_percent",                   # 5   mortgage insurance percentage
    "num_units",                    # 6
    "occupancy_status",             # 7   P / I / S
    "combined_ltv",                 # 8
    "dti",                          # 9   debt-to-income ratio
    "original_upb",                 # 10  original balance
    "ltv",                          # 11  loan-to-value
    "interest_rate",                # 12
    "channel",                      # 13
    "prepayment_penalty",           # 14  Y / N
    "amortization_type",            # 15  FRM / ARM
    "state",                        # 16
    "property_type",                # 17
    "postal_code",                  # 18  first 3 digits
    "loan_id",                      # 19
    "loan_purpose",                 # 20
    "loan_term",                    # 21  months
    "num_borrowers",                # 22
    "seller_name",                  # 23
    "super_conforming",             # 24
    "pre_harp_loan_id",             # 25
    "special_eligibility_program",  # 26
    "harp_indicator",               # 27
    "property_valuation_method",    # 28
    "interest_only",                # 29
    "vantage_score_4",              # 30
]

PERF_COLUMNS = [
    "loan_id",                      # 0
    "reporting_period",             # 1   YYYYMM
    "current_upb",                  # 2   current balance
    "delinquency_status",           # 3   00, 01, ... , RA, XX
    "loan_age",                     # 4   restarts after a modification
    "remaining_months",             # 5   to legal maturity
    "defect_settlement_date",       # 6
    "modification_flag",            # 7   Y / P / blank
    "zero_balance_code",            # 8   why the loan ended
    "zero_balance_date",            # 9
    "current_interest_rate",        # 10
    "current_non_interest_upb",     # 11
    "ddlpi",                        # 12  due date of last paid installment
    "mi_recoveries",                # 13
    "net_sales_proceeds",           # 14
    "non_mi_recoveries",            # 15
    "total_expenses",               # 16
    "legal_costs",                  # 17
    "maintenance_costs",            # 18
    "taxes_insurance",              # 19
    "misc_expenses",                # 20
    "actual_loss",                  # 21
    "cumulative_modification_cost", # 22
    "interest_rate_step",           # 23
    "payment_deferral_flag",        # 24
    "estimated_ltv",                # 25  999 = not available
    "zero_balance_removal_upb",     # 26
    "delinquent_accrued_interest",  # 27
    "delinquency_due_to_disaster",  # 28
    "borrower_assistance_plan",     # 29
    "current_period_mod_cost",      # 30
    "current_interest_bearing_upb", # 31
    "mi_cancellation_indicator",    # 32
    "servicer_name",                # 33
    "bankruptcy_cramdown_costs",    # 34
]

# codes that mean "Not Available" (from the user guide)
NOT_AVAILABLE = {
    "credit_score": 9999,
    "first_time_homebuyer": "9",
    "mi_percent": 999,
    "num_units": 99,
    "combined_ltv": 999,
    "dti": 999,
    "ltv": 999,
    "num_borrowers": 99,
    "occupancy_status": "9",
    "channel": "9",
    "property_type": "99",
    "loan_purpose": "9",
    "property_valuation_method": "7",
    "vantage_score_4": 9999,
    "delinquency_status": "XX",
    "estimated_ltv": 999,
}

assert len(ORIG_COLUMNS) == 31 and len(PERF_COLUMNS) == 35
assert len(set(ORIG_COLUMNS)) == 31 and len(set(PERF_COLUMNS)) == 35, "duplicate column name"
assert all(k in ORIG_COLUMNS + PERF_COLUMNS for k in NOT_AVAILABLE), "NOT_AVAILABLE names a column that does not exist"
