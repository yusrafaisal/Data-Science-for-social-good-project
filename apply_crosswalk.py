"""
Apply the HS Chapter -> Sector crosswalk to combined_exports.csv.

Sector mapping (per your Customs Tariff Sections):
  Agriculture      = Sections I, II, III   -> Chapters 01-15
  Mining/Quarrying = Section V              -> Chapters 25-27
  Manufacturing    = Section IV + VI-XXI    -> Chapters 16-24, 28-97
  Excluded         = Chapters 98, 99 (excise/admin codes, not real goods)
"""

import pandas as pd


def chapter_to_sector(chapter_str: str) -> str:
    """chapter_str is a 2-digit string like '01', '27', '96'."""
    ch = int(chapter_str)

    if 1 <= ch <= 15:
        return "Agriculture"
    elif 25 <= ch <= 27:
        return "Mining"
    elif (16 <= ch <= 24) or (28 <= ch <= 97):
        return "Manufacturing"
    elif ch in (98, 99):
        return "Exclude"
    else:
        return "Unknown"  # shouldn't happen, but flagged if it does


def main():
    df = pd.read_csv("combined_exports.csv", dtype={"hs_chapter": str})

    # hs_chapter should already be a zero-padded 2-digit string
    # (e.g. "01", "27") from the export parser -- but enforce it here
    # too, in case the CSV round-trip dropped a leading zero.
    df["hs_chapter"] = df["hs_chapter"].astype(str).str.zfill(2)

    df["sector"] = df["hs_chapter"].apply(chapter_to_sector)

    unknown = df[df["sector"] == "Unknown"]
    if len(unknown) > 0:
        print(f"[WARNING] {len(unknown)} rows had an unrecognized chapter:")
        print(unknown[["hs_code", "hs_chapter", "commodity_raw"]].drop_duplicates())

    excluded = df[df["sector"] == "Exclude"]
    print(f"Excluding {len(excluded)} rows from chapters 98/99 (non-goods codes)")

    df_final = df[df["sector"] != "Exclude"].copy()

    # Quick sanity summary: value and quantity by sector, per fiscal year
    summary = (
        df_final.groupby(["fiscal_year", "sector"])["value_pkr_thousands"]
        .sum()
        .unstack(fill_value=0)
    )
    print("\nExport value (PKR thousands) by sector and fiscal year:")
    print(summary)

    qty_summary = (
        df_final.groupby(["fiscal_year", "sector"])["quantity"]
        .sum()
        .unstack(fill_value=0)
    )
    print("\nExport quantity by sector and fiscal year:")
    print(qty_summary)

    df_final.to_csv("combined_exports_with_sector.csv", index=False)
    print("\nSaved to combined_exports_with_sector.csv")


if __name__ == "__main__":
    main()