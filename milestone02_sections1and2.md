# Milestone 02 — Sections 1 & 2 documentation
## Is Pakistan's Export Sector Delivering Broad-Based Economic Benefit?

---

# Section 1: Project Alignment & Master Dataset Inventory

## 1.1 Team Metadata & Problem Summary

**Project Title:** Is Pakistan's Export Sector Delivering Broad-Based Economic Benefit, or Is Growth Concentrated and Disconnected from Jobs and Real Value?

**Team Members:**
| Name | Disciplinary Background |
|---|---|
| Ayesha Sohail | Social Development Policy (SDP) |
| Yusra Faisal | Computer Science (CS) |
| Maria Aqeel | Computer Science (CS) |

**Primary Social Research Question:**
Pakistan's exports have grown substantially in PKR terms between FY2018-19 and FY2023-24, but this growth may be misleading. The PKR depreciated sharply against the USD over this period — from approximately PKR 136/USD in FY2018-19 to PKR 283/USD in FY2023-24 — which mechanically inflates rupee-denominated export figures even when physical volumes are flat or declining. Meanwhile, Pakistan's export basket remains heavily concentrated in a narrow set of commodities (primarily textiles), and employment in export-producing sectors has not grown at the same pace as headline export numbers.

This project asks: **Is Pakistan's export growth real, broad-based, and connected to job creation — or is it concentrated in a few products, inflated by currency depreciation, and disconnected from labour market outcomes?**

**SDG Alignment:**
- **Primary:** SDG 8 — Decent Work and Economic Growth (productive employment, economic diversification)
- **Secondary:** SDG 9 — Industry, Innovation and Infrastructure (industrial diversification)
- **Secondary:** SDG 10 — Reduced Inequalities (ensuring export gains are shared across sectors and workers)

---

## 1.2 Master Dataset Overview

**Final analytical dataset:** `eda_dataset.csv`

| Property | Value |
|---|---|
| Total rows (observations) | 25,255 |
| Total columns (variables) | 22 |
| Primary observational unit | 1 row = 1 HS commodity code × 1 fiscal year |
| Fiscal years covered | FY2018-19 to FY2023-24 (6 years) |
| Unique HS product codes | 5,520 |
| Rows with lagged features | 19,735 (FY2018-19 excluded — first year, no prior) |
| Rows with employment data | 8,494 (FY2018-19 and FY2020-21 only) |

**Data sources included:**

| Source | Type | Portal |
|---|---|---|
| PBS Exports by Commodities and Countries (FY2017-18 to FY2023-24) | Government fixed-width text files + PDF reports | pbs.gov.pk |
| SBP Monthly Average Exchange Rates (2017–2026) | Government Excel file | sbp.org.pk |
| PBS Labour Force Survey Annual Reports (FY2018-19, FY2020-21, FY2024-25) | Government PDF reports, manually extracted | pbs.gov.pk |

**Column inventory:**

| Column | Type | Description |
|---|---|---|
| `hs_code` | string | 8-digit HS product code |
| `hs_chapter` | string | 2-digit HS chapter (zero-padded) |
| `commodity_raw` | string | Commodity name as printed in PBS report |
| `sector` | string | Agriculture / Manufacturing / Mining (from crosswalk) |
| `fiscal_year` | string | e.g. "2018-19" |
| `year_index` | int | Numeric year index (2018-19=0 … 2023-24=5) |
| `export_pkr_thousands` | float | Cumulative fiscal-year export value in PKR thousands |
| `avg_usd_rate` | float | Fiscal-year average PKR/USD exchange rate |
| `export_usd_thousands` | float | Export value converted to USD thousands |
| `quantity` | float | Physical export quantity (PBS unit varies by commodity) |
| `employment_share` | float | % of total employed persons in this sector (LFS; sparse) |
| `export_pkr_lag` | float | Prior year's PKR export value (same HS code) |
| `export_usd_lag` | float | Prior year's USD export value (same HS code) |
| `export_qty_lag` | float | Prior year's physical quantity (same HS code) |
| `export_pkr_growth_pct` | float | YoY PKR export growth % (EDA only) |
| `export_usd_growth_pct` | float | YoY USD export growth % (EDA only) |
| `is_zero_export` | bool | True if export value is zero that year |
| `log_export_usd` | float | log1p(export_usd_thousands) |
| `log_export_qty` | float | log1p(quantity) |
| `log_export_usd_lag` | float | log1p(export_usd_lag) |
| `log_export_qty_lag` | float | log1p(export_qty_lag) |
| `top20_flag` | int | 1 if commodity is in top 20% of USD export value that year |

---

# Section 2: Data Ingestion, Cleaning & Structural Readiness

## 2.1 Scraping / Collection Audit

Three independent government data sources were collected, each requiring a different extraction method.

### Source 1: PBS Exports by Commodities and Countries

**What we collected:** Annual export data at the 8-digit HS code level, covering fiscal years 2017-18 through 2023-24. Two different file formats were published by PBS across this period:

- **Fixed-width `.txt` files** (FY2018-19, FY2019-20, FY2020-21): Downloaded directly from pbs.gov.pk under Trade Statistics → Foreign Trade. These are plain-text files with a fixed-width layout where each commodity line begins with an 8-digit HS code, followed by the commodity name and unit, then eight numeric columns: JUN quantity, JUN value, cumulative quantity, cumulative value (current year), and the same four columns repeated for the prior year.

- **D-10 PDF reports** (FY2021-22, FY2022-23, FY2023-24): Downloaded from pbs.gov.pk as digitally generated PDFs titled "D-10 Exports by Commodities and Countries." These required PDF text extraction using the `pdfplumber` Python library before any parsing could occur.

**Custom parser built from scratch (`parse_exports.py`):**

Because PBS does not publish these files in a machine-readable format, we built a custom Python parser to handle both file types. The core challenges encountered and resolved were:

1. **Mixed row types in a single file:** Each file contains three types of lines — commodity header rows (start with an 8-digit HS code), country sub-rows (indented, start with a country name), and repeating page headers/footers. The parser identifies commodity rows exclusively by checking whether the line starts with an 8-digit numeric sequence, discarding all other row types.

2. **Numeric tokens embedded in commodity names:** Many commodity descriptions contain numbers, such as `FOWLS (CHICKEN) WT UPTO 185G` or `GREEN TEA PACK < 3 KG`. Early parser versions incorrectly treated these embedded numbers as data columns, shifting the token window and producing wrong values (e.g., extracting 54,253 instead of the correct 6,754 for HS code 01051100). This was fixed by parsing from the right side of each line — collecting the last 8 numeric tokens — which is robust to any content in the commodity name.

3. **Unit words inside commodity names:** PBS uses unit abbreviations (KG, MT, NO, BOX, TUB, etc.) as a standard column in every row. Several commodity names contain these same words (e.g., `FUSE BOX`, `BATH TUB`, `OFF SET`), which caused the parser to absorb part of the name as the unit column. Fix: after identifying a candidate unit token, the parser checks whether at least 4 numeric tokens follow it; if not, the word is part of the name, not the unit column.

4. **Symbols in commodity names:** Characters like `<` and `>` appear in commodity names (e.g., `TILES > 0.3 BUT <`) and were being picked up as numeric tokens. The token filter was tightened to require every numeric token to begin with a digit.

5. **Leading zero loss in PDF extraction:** For HS chapters 01–09, `pdfplumber` sometimes dropped the leading zero from HS codes during text extraction (e.g., `1051100` instead of `01051100`). The parser enforces zero-padding to 8 digits on all extracted codes.

6. **Inconsistent number formatting:** Values appear with commas (e.g., `1,234,567`), dashes for zero/missing (`--`, `-`), and occasional decimal values (e.g., rubber and plastic quantities in metric tons). The number parser handles all three: dashes are converted to 0, commas are stripped, and values are cast to float.

7. **Duplicate HS codes per file:** Each file lists the same HS code once per destination country (e.g., DURUM WHEAT appears separately under Afghanistan, UAE, China, etc.). After parsing, the parser sums all rows sharing the same HS code within a fiscal year to produce one row per (HS code, fiscal year) pair. The duplicate count ranged from 777 to 1,939 codes per file.

**Final parse output:** `combined_exports.csv` — 29,498 rows, 0 suspect rows, covering 7 fiscal years (FY2017-18 used only for lag computation).

---

### Source 2: SBP Monthly Average Exchange Rates

**What we collected:** Monthly PKR/USD average exchange rates from July 2017 to June 2024, from the State Bank of Pakistan's "Historical Exchange Rates" Excel file (`SBP Exchange Rate.xls`), downloaded from sbp.org.pk under Statistics → Exchange Rates → Bank Floating Average Exchange Rates.

**Custom parser built (`parse_sbp.py`):**

The SBP file is a multi-sheet Excel workbook with 8 rows of title/header content before the monthly data begins, multi-row column headers (one row for country names like "U.S.A.", a second for currency names), and 24+ currency columns alongside the target USD column. The parser auto-detects the USD column index by scanning header rows for any cell containing "U.S" or "DOLLAR," then reads each monthly row, mapping month names to month numbers.

**Fiscal-year alignment:** PBS export data is organised by Pakistan's fiscal year (July–June), while SBP data is calendar-month. To align them, one average PKR/USD rate per fiscal year was computed by averaging the 12 monthly rates within each July–June window (e.g., FY2018-19 = average of July 2018 through June 2019).

**Final output:** `sbp_usd_fiscal.csv` — 6 rows, one per fiscal year from FY2018-19 to FY2023-24.

---

### Source 3: PBS Labour Force Survey — Employment Shares

**What we collected:** Sector-level employment share data (percentage of total employed persons) for Agriculture, Manufacturing, and Mining, manually extracted from three PBS LFS Annual Reports:

| Source Publication | Fiscal Year | Table Used |
|---|---|---|
| LFS Annual Report 2018-19 | FY2018-19 | Distribution of Employed Persons by Major Industry Division |
| LFS Annual Report 2020-21 | FY2020-21 | Distribution of Employed Persons by Major Industry Division |
| LFS Annual Report 2024-25 | FY2024-25 | Distribution of Employed Persons by Major Industry Division |

**Why manual extraction:** The LFS reports are published as PDFs only with no machine-readable download. The relevant table spans a single page in each report, making manual transcription the most reliable approach for this small number of values (3 years × 3 sectors = 9 values).

**Coverage decision:** The LFS is not published annually — FY2018-19, FY2020-21, and FY2024-25 are the three rounds available within or adjacent to our study window. Mining & Quarrying cannot be tracked consistently across all three reports due to changing category definitions in the 2024-25 edition, so it is excluded from H3 trend analysis. The FY2024-25 values (Agriculture: 33.1%, Manufacturing: 14.8%) fall beyond the current dataset ceiling (FY2023-24) and are used for H3 trend commentary only, not as model features.

**Values merged into the dataset:**

| Fiscal Year | Agriculture | Manufacturing | Mining |
|---|---|---|---|
| 2018-19 | 39.2% | 15.0% | 0.3% |
| 2020-21 | 36.9% | 14.9% | 0.3% |

---

## 2.2 Data Alignment & Structural Organisation

The three sources were merged into a single commodity-level master dataset through the following pipeline:

**Step 1 — HS-to-Sector crosswalk (`apply_crosswalk.py`):**
Export data is classified by 8-digit HS codes, while LFS data uses broad industry divisions. A manual mapping was built using the Pakistan Customs Tariff First Schedule:

| HS Chapters | Customs Tariff Sections | Sector |
|---|---|---|
| 01–15 | I, II, III | Agriculture |
| 25–27 | V | Mining |
| 16–24, 28–97 | IV, VI–XXI | Manufacturing |
| 98–99 | — | Excluded (administrative/excise codes) |

14 rows from chapters 98/99 were excluded. The mapping was applied to the 2-digit HS chapter extracted from each code, producing a `sector` column on every row.

**Step 2 — Exchange rate merge (`build_modeling_dataset.py`):**
`sbp_usd_fiscal.csv` was joined to the export dataset on `fiscal_year` (left join). Each row's `export_pkr_thousands` was divided by `avg_usd_rate` to compute `export_usd_thousands`. The 2017-18 rows (present only for lag computation) have no corresponding exchange rate and are dropped at this stage, reducing the dataset from 29,498 to 25,255 rows.

**Step 3 — Employment share merge:**
LFS employment shares were joined on `(fiscal_year, sector)`. Only FY2018-19 and FY2020-21 rows receive a non-null `employment_share` value — expected and documented.

**Step 4 — Lagged features:**
Rows were sorted by `(hs_code, year_index)`. For each HS code, the previous year's values were computed using `.shift(1)` within each group:
- `export_pkr_lag` — prior year PKR value
- `export_usd_lag` — prior year USD value
- `export_qty_lag` — prior year physical quantity

FY2018-19 rows receive null lag values by construction and are excluded from any analysis requiring prior-year features.

---

## 2.3 Cleaning & Missing Data Strategy

### Missing Value Summary

| Column | Missing Count | Missing % | Reason | Strategy |
|---|---|---|---|---|
| `export_pkr_lag` | 5,520 | 21.8% | FY2018-19 is first year — no prior year exists | Expected by design. Rows with null lags excluded from analyses requiring prior-year values. No imputation. |
| `export_usd_lag` | 5,520 | 21.8% | Same as above | Same as above. |
| `export_qty_lag` | 5,520 | 21.8% | Same as above | Same as above. |
| `export_pkr_growth_pct` | 5,520 | 21.8% | Derived from lag; undefined when lag is null | Retained for descriptive EDA only. Not used as a predictor feature (collinearity with lag values). Not imputed. |
| `export_usd_growth_pct` | 5,520 | 21.8% | Same as above | Same as above. |
| `employment_share` | 16,761 | 66.4% | LFS only published for FY2018-19 and FY2020-21 | Expected by design. Used only for H3 trend analysis. Not imputed — imputation would fabricate figures for years where no survey was conducted. |

**No imputation was performed.** All missing values are structurally justified: they arise from (a) the first-year lag window, (b) infrequent LFS publication, or (c) derived columns excluded from predictive analysis. Imputing employment shares for non-survey years would misrepresent actual labour market measurement.

**Zero-export rows:** 4,035 rows (13.7%) have `export_pkr_thousands = 0`, flagged in `is_zero_export`. These are valid observations — a commodity being exported in some years but not others is a real economic phenomenon. They are retained in the full dataset for concentration analysis (H1) but will be excluded from the H2 quantity regression.

### Potential Selection Bias
The use of only two LFS snapshots within the modeling window introduces temporal selection bias in H3: employment trends are measured at points that may not represent the full 2018–2024 period. We acknowledge this explicitly and restrict H3 conclusions to trend direction rather than point-in-time causal claims.

---

## 2.4 Transformations for EDA

Two transformations were applied to `modeling_dataset.csv` via `prepare_eda.py` to produce the EDA-ready dataset `eda_dataset.csv` (25,255 rows, 22 columns).

### Log Transformation
Export value and quantity columns are heavily right-skewed: Pakistan's exports are dominated by a small number of large textile HS codes, with the vast majority of codes having very small values. Log-transforming compresses the scale so that distributions, correlation matrices, and scatter plots are not dominated by outliers.

```python
df["log_export_usd"]     = np.log1p(df["export_usd_thousands"])
df["log_export_qty"]     = np.log1p(df["quantity"])
df["log_export_usd_lag"] = np.log1p(df["export_usd_lag"].fillna(0))
df["log_export_qty_lag"] = np.log1p(df["export_qty_lag"].fillna(0))
```

`log1p` (i.e., log(1 + x)) is used rather than `log` to safely handle zero-export rows (log(0) is undefined; log1p(0) = 0). Null lag values for FY2018-19 are filled with 0 before transformation.

### Growth Rate Exclusion from Predictive Features
`export_pkr_growth_pct` and `export_usd_growth_pct` are retained for descriptive EDA only. They will not be used as model features because both are derived directly from lagged values (growth = (current − lag) / lag × 100), and including both the growth rate and the lag value as predictors would introduce multicollinearity.

### H1 Concentration Flag
A binary column `top20_flag` was added to support H1 exploratory analysis — marking whether a commodity falls in the top 20% of USD export value within its fiscal year:

```python
threshold = df.groupby("fiscal_year")["export_usd_thousands"].transform(
    lambda x: x.quantile(0.80)
)
df["top20_flag"] = (df["export_usd_thousands"] >= threshold).astype(int)
```

### Final EDA Dataset Summary

| Property | Value |
|---|---|
| File | `eda_dataset.csv` |
| Total rows | 25,255 |
| Total columns | 22 |
| Added columns vs. base dataset | `log_export_usd`, `log_export_qty`, `log_export_usd_lag`, `log_export_qty_lag`, `top20_flag` |
