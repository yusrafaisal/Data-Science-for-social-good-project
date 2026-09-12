"""
Final merge: combines all three data sources into one analysis-ready table.

Produces two output files:

1. analysis_sector_year.csv  -- sector-level, all 6 fiscal years
   Columns: fiscal_year, sector, export_pkr_thousands,
            avg_usd_rate, export_usd_thousands

2. analysis_with_employment.csv -- sector-level, years where LFS overlaps
   Adds: employment_share (%) from PBS Employment Trends reports
   Coverage: 2018-19 and 2020-21 (confirmed LFS data points in window)
"""

import pandas as pd

# ── 1. Load export data (with sector column) ────────────────────────────────
exports = pd.read_csv("combined_exports_with_sector.csv")

# Aggregate to sector-year level (sum all commodity values within each bucket)
sector_year = (
    exports.groupby(["fiscal_year", "sector"], as_index=False)
    ["value_pkr_thousands"].sum()
    .rename(columns={"value_pkr_thousands": "export_pkr_thousands"})
)

# ── 2. Load exchange rates ───────────────────────────────────────────────────
fx = pd.read_csv("sbp_usd_fiscal.csv")

# ── 3. Merge exports + exchange rates ───────────────────────────────────────
merged = sector_year.merge(fx, on="fiscal_year", how="left")

missing_fx = merged[merged["avg_usd_rate"].isna()]
if len(missing_fx) > 0:
    print(f"[WARNING] {len(missing_fx)} rows have no exchange rate match:")
    print(missing_fx[["fiscal_year", "sector"]])

# Convert PKR to USD
merged["export_usd_thousands"] = (
    merged["export_pkr_thousands"] / merged["avg_usd_rate"]
)

print("Export values in PKR and USD by sector and fiscal year:")
print(
    merged.pivot_table(
        index="fiscal_year",
        columns="sector",
        values="export_usd_thousands",
        aggfunc="sum",
    ).round(0)
)

merged.to_csv("analysis_sector_year.csv", index=False)
print("\nSaved to analysis_sector_year.csv")

# ── 4. Employment data (manually entered from PBS Employment Trends PDFs) ───
# Source: Table 4.6 and 4.7 from Pakistan Employment Trends 2025 report
# and Table A5 from Pakistan Employment Trends 2018 report.
# These are % share of total employed persons aged 10+ years.
# Only years confirmed present in your LFS data within the project window:
#   FY2018-19 and FY2020-21

employment = pd.DataFrame([
    # FY2018-19 (from Employment Trends 2025, Table 4.6 / 4.7)
    {"fiscal_year": "2018-19", "sector": "Agriculture",    "employment_share": 38.1},
    {"fiscal_year": "2018-19", "sector": "Manufacturing",  "employment_share": 15.1},
    {"fiscal_year": "2018-19", "sector": "Mining",         "employment_share": 0.3},

    # FY2020-21 (from LFS Annual Report 2020-21, Table 15)
    {"fiscal_year": "2020-21", "sector": "Agriculture",    "employment_share": 36.9},
    {"fiscal_year": "2020-21", "sector": "Manufacturing",  "employment_share": 14.9},
    {"fiscal_year": "2020-21", "sector": "Mining",         "employment_share": 0.3},
])

# ── 5. Merge employment into sector-year table ──────────────────────────────
final = merged.merge(employment, on=["fiscal_year", "sector"], how="left")

# Compute year-on-year USD export growth rate per sector
final = final.sort_values(["sector", "fiscal_year"])
final["export_usd_growth_pct"] = (
    final.groupby("sector")["export_usd_thousands"]
    .pct_change() * 100
)

# Compute PKR growth rate too (for the real-vs-nominal comparison)
final["export_pkr_growth_pct"] = (
    final.groupby("sector")["export_pkr_thousands"]
    .pct_change() * 100
)

final.to_csv("analysis_with_employment.csv", index=False)
print("Saved to analysis_with_employment.csv")

# ── 6. Quick summary for the employment-linkage sub-question ────────────────
emp_rows = final[final["employment_share"].notna()].copy()
if len(emp_rows) > 0:
    print("\nEmployment linkage snapshot (years with LFS data):")
    print(
        emp_rows[
            ["fiscal_year", "sector",
             "export_usd_thousands", "export_usd_growth_pct",
             "employment_share"]
        ].to_string(index=False)
    )
