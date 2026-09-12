"""
Parse SBP "Monthly Average Exchange Rates" Excel file.
Extracts PKR/USD monthly average rates and computes one
fiscal-year average (July-June) per year, to align with
the PBS export data's fiscal-year structure.

Output: sbp_usd_fiscal.csv with columns:
    fiscal_year | avg_usd_rate
"""

import pandas as pd


def find_usd_column(df: pd.DataFrame) -> str:
    """
    Find the column name for U.S. Dollar in the SBP spreadsheet.
    The header row labels it as 'U.S.A.' or 'U.S. Dollar' or similar.
    """
    for col in df.columns:
        col_str = str(col).strip().upper()
        if "U.S" in col_str or "USA" in col_str or "DOLLAR" in col_str:
            return col
    raise ValueError(
        f"Could not find USD column. Available columns: {list(df.columns)}"
    )


def parse_sbp_exchange_rates(filepath: str) -> pd.DataFrame:
    """
    Read the SBP monthly exchange rate Excel file and return a
    clean DataFrame with columns: year, month_num, usd_rate.
    """
    # The SBP file has multi-row headers and historical range rows
    # at the top. We skip the first 8 rows (title, section headers,
    # country/currency rows) and read from the actual monthly data.
    # Adjust skiprows if your file starts differently.
    df_raw = pd.read_excel(
        filepath,
        sheet_name="Monthly Avg. Ex. Rates in PKR",
        skiprows=8,
        header=None,
    )

    # Column 0 = Month name (e.g. "March", "April") or historical label
    # Column 1 = Year (e.g. 2018, 2019) or NaN for historical ranges
    # Remaining columns = currency rates in the order shown in the header

    # Read the header rows first to find the USD column index dynamically.
    # Row 8 (index 7) has country names like "U.S.A.", row 9 has currency
    # names like "U.S. Dollar" -- we check both to find the right column.
    df_header = pd.read_excel(
        filepath,
        sheet_name="Monthly Avg. Ex. Rates in PKR",
        skiprows=7,
        nrows=2,
        header=None,
    )

    USD_COL_IDX = None
    for row_idx in range(len(df_header)):
        for col_idx in range(len(df_header.columns)):
            val = str(df_header.iloc[row_idx, col_idx]).strip().upper()
            if "U.S" in val or "USA" in val or "DOLLAR" in val:
                USD_COL_IDX = col_idx
                print(f"Found USD column at index {col_idx} "
                      f"(header value: '{df_header.iloc[row_idx, col_idx]}')")
                break
        if USD_COL_IDX is not None:
            break

    if USD_COL_IDX is None:
        raise ValueError(
            "Could not auto-detect USD column. "
            "Check the sheet name and header row layout."
        )

    rows = []
    MONTH_MAP = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }

    for _, row in df_raw.iterrows():
        month_raw = str(row.iloc[0]).strip().lower()
        year_raw  = row.iloc[1]
        usd_raw   = row.iloc[USD_COL_IDX] if USD_COL_IDX < len(row) else None

        # Skip rows that aren't proper monthly data:
        # - historical range rows have text like "aug 1947 to jun 1949"
        # - blank/header rows have month_raw = "nan" or non-month words
        if month_raw not in MONTH_MAP:
            continue

        try:
            year = int(float(str(year_raw)))
            usd  = float(str(usd_raw).replace(",", ""))
            if usd <= 0:
                continue
        except (ValueError, TypeError):
            continue

        rows.append({
            "year":      year,
            "month_num": MONTH_MAP[month_raw],
            "usd_rate":  usd,
        })

    df = pd.DataFrame(rows)
    print(f"Parsed {len(df)} monthly rows spanning "
          f"{df['year'].min()} to {df['year'].max()}")
    return df


def assign_fiscal_year(year: int, month: int) -> str:
    """
    Pakistan fiscal year runs July-June.
    July 2018 - June 2019 -> '2018-19'
    """
    if month >= 7:
        return f"{year}-{str(year + 1)[-2:]}"
    else:
        return f"{year - 1}-{str(year)[-2:]}"


def compute_fiscal_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Average the 12 monthly USD rates within each fiscal year."""
    df = df.copy()
    df["fiscal_year"] = df.apply(
        lambda r: assign_fiscal_year(int(r["year"]), int(r["month_num"])),
        axis=1,
    )

    summary = (
        df.groupby("fiscal_year")
        .agg(
            avg_usd_rate=("usd_rate", "mean"),
            month_count=("usd_rate", "count"),
        )
        .reset_index()
    )

    # Flag any fiscal year that doesn't have all 12 months
    incomplete = summary[summary["month_count"] < 12]
    if len(incomplete) > 0:
        print(
            "[WARNING] Some fiscal years have fewer than 12 monthly "
            "observations -- averages will be based on available months only:"
        )
        print(incomplete[["fiscal_year", "month_count"]])

    return summary


def main():
    filepath = "SBP Exchange rate.xls"

    monthly = parse_sbp_exchange_rates(filepath)
    fiscal  = compute_fiscal_averages(monthly)

    # Filter to just the years relevant to your project
    target_years = ["2018-19","2019-20","2020-21","2021-22","2022-23","2023-24"]
    fiscal_project = fiscal[fiscal["fiscal_year"].isin(target_years)].copy()

    print("\nFiscal-year average PKR/USD rates:")
    print(fiscal_project[["fiscal_year","avg_usd_rate","month_count"]].to_string(index=False))

    fiscal_project[["fiscal_year","avg_usd_rate"]].to_csv(
        "sbp_usd_fiscal.csv", index=False
    )
    print("\nSaved to sbp_usd_fiscal.csv")


if __name__ == "__main__":
    main()
