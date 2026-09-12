"""
Build the final commodity-level modeling dataset.

Input files:
    combined_exports_with_sector.csv   -- commodity × fiscal_year rows
    sbp_usd_fiscal.csv                 -- fiscal_year → avg_usd_rate

Output:
    modeling_dataset.csv               -- one row per (hs_code, fiscal_year)
                                          ready for EDA and model training

Columns in output:
    hs_code                 -- 8-digit HS code
    hs_chapter              -- 2-digit chapter
    commodity_raw           -- commodity name (cleaned)
    sector                  -- Agriculture / Mining / Manufacturing
    fiscal_year             -- e.g. '2018-19'
    export_pkr_thousands    -- cumulative export value in PKR thousands
    avg_usd_rate            -- fiscal-year average PKR per USD
    export_usd_thousands    -- export value in USD thousands (PKR / rate)
    employment_share        -- sector-level % of employed persons (LFS)
                              (only populated for 2018-19 and 2020-21)
    export_pkr_lag          -- previous fiscal year's PKR value (same code)
    export_usd_lag          -- previous fiscal year's USD value (same code)
    export_pkr_growth_pct   -- YoY PKR growth %
    export_usd_growth_pct   -- YoY USD growth %
    year_index              -- numeric year index (2018-19=0 ... 2023-24=5)
"""

import pandas as pd
import numpy as np


# ── 1. Load base export data ─────────────────────────────────────────────────
print("Loading export data...")
exports = pd.read_csv(
    "combined_exports_with_sector.csv",
    dtype={"hs_code": str, "hs_chapter": str},
)

# Rename to consistent name used throughout this script
exports = exports.rename(columns={"value_pkr_thousands": "export_pkr_thousands"})

# Drop suspect rows where value is flagged as unparseable
exports = exports[exports["suspect_row"] == False].copy()

# Drop rows with zero value -- a commodity with zero exports in a year
# is a valid observation for concentration analysis but adds noise for
# regression modeling. Keep them for now but flag them.
exports["is_zero_export"] = exports["export_pkr_thousands"] == 0

print(f"  Loaded {len(exports):,} rows across "
      f"{exports['fiscal_year'].nunique()} fiscal years")
print(f"  Unique HS codes: {exports['hs_code'].nunique():,}")
print(f"  Zero-value rows: {exports['is_zero_export'].sum():,} "
      f"({exports['is_zero_export'].mean()*100:.1f}%)")

# ── 2. Merge exchange rates ───────────────────────────────────────────────────
print("\nMerging exchange rates...")
fx = pd.read_csv("sbp_usd_fiscal.csv")
df = exports.merge(fx, on="fiscal_year", how="left")

missing_rate = df["avg_usd_rate"].isna().sum()
if missing_rate > 0:
    print(f"  [WARNING] {missing_rate} rows have no exchange rate -- dropped")
    df = df[df["avg_usd_rate"].notna()].copy()

df["export_usd_thousands"] = (
    df["export_pkr_thousands"] / df["avg_usd_rate"]
)

# ── 3. Add employment share (sector-level, LFS data points only) ─────────────
print("Adding employment shares...")
employment = pd.DataFrame([
    {"fiscal_year": "2018-19", "sector": "Agriculture",   "employment_share": 38.1},
    {"fiscal_year": "2018-19", "sector": "Manufacturing", "employment_share": 15.1},
    {"fiscal_year": "2018-19", "sector": "Mining",        "employment_share": 0.3},
    {"fiscal_year": "2020-21", "sector": "Agriculture",   "employment_share": 36.9},
    {"fiscal_year": "2020-21", "sector": "Manufacturing", "employment_share": 14.9},
    {"fiscal_year": "2020-21", "sector": "Mining",        "employment_share": 0.3},
])
df = df.merge(employment, on=["fiscal_year", "sector"], how="left")

# ── 4. Add year index (numeric, for trend features) ──────────────────────────
year_order = {
    "2018-19": 0, "2019-20": 1, "2020-21": 2,
    "2021-22": 3, "2022-23": 4, "2023-24": 5,
}
df["year_index"] = df["fiscal_year"].map(year_order)

# ── 5. Compute lagged values and growth rates per commodity ──────────────────
print("Computing lagged values and growth rates...")
df = df.sort_values(["hs_code", "year_index"]).reset_index(drop=True)

df["export_pkr_lag"] = df.groupby("hs_code")["export_pkr_thousands"].shift(1)
df["export_usd_lag"] = df.groupby("hs_code")["export_usd_thousands"].shift(1)

# Growth rate: only meaningful when lag > 0 (avoid division by zero)
def safe_growth(current, lag):
    result = np.where(
        (lag > 0) & (lag.notna()),
        (current - lag) / lag * 100,
        np.nan,
    )
    return result

df["export_pkr_growth_pct"] = safe_growth(
    df["export_pkr_thousands"], df["export_pkr_lag"]
)
df["export_usd_growth_pct"] = safe_growth(
    df["export_usd_thousands"], df["export_usd_lag"]
)

# ── 6. Clean up and select final columns ────────────────────────────────────
final_cols = [
    "hs_code", "hs_chapter", "commodity_raw", "sector", "fiscal_year",
    "year_index", "export_pkr_thousands", "avg_usd_rate",
    "export_usd_thousands", "employment_share",
    "export_pkr_lag", "export_usd_lag",
    "export_pkr_growth_pct", "export_usd_growth_pct",
    "is_zero_export",
]
df_final = df[final_cols].copy()

# ── 7. Print summary ─────────────────────────────────────────────────────────
print("\n── Final modeling dataset summary ──────────────────────────────")
print(f"Total rows         : {len(df_final):,}")
print(f"Fiscal years       : {sorted(df_final['fiscal_year'].unique())}")
print(f"Unique HS codes    : {df_final['hs_code'].nunique():,}")
print(f"Rows with lag data : {df_final['export_usd_lag'].notna().sum():,}")
print(f"Rows with LFS data : {df_final['employment_share'].notna().sum():,}")
print(f"\nSector distribution:")
print(df_final["sector"].value_counts())
print(f"\nNon-zero export rows per fiscal year:")
print(
    df_final[~df_final["is_zero_export"]]
    .groupby("fiscal_year")["hs_code"].count()
)
print(f"\nSample USD export values (first 5 rows):")
print(
    df_final[["hs_code","commodity_raw","fiscal_year",
              "export_usd_thousands","export_usd_growth_pct"]]
    .head()
    .to_string(index=False)
)

df_final.to_csv("modeling_dataset.csv", index=False)
print("\nSaved to modeling_dataset.csv")