# """
# Parser for PBS/D-10 "Exports by Commodities and Countries" reports.
# Handles both plain .txt extracts and .pdf files (via pdfplumber).

# Output: one row per HS code per fiscal year, with the CUMULATIVE
# (full fiscal-year-to-date) export value in PKR thousands.
# """

# import re
# import pandas as pd

# try:
#     import pdfplumber
# except ImportError:
#     pdfplumber = None


# # A commodity line starts with a 7- or 8-digit HS code at the start of
# # the (stripped) line. Some PDFs drop the leading zero for chapters
# # 01-09 (e.g. "1051100" instead of "01051100") -- both are accepted
# # here and normalized to 8 digits below. Country sub-lines start with
# # a letter, not a digit, so this naturally excludes them.
# HS_CODE_RE = re.compile(r"^(\d{7,8})\s+(.*)$")

# # A numeric data token must be a WHOLE whitespace-separated word --
# # this is anchored (^...$) so a number embedded inside a word, like
# # the "185" in "185G" (grams), is never mistaken for a data column.
# TOKEN_RE = re.compile(r"^(--|-|\d[\d,]*)$")


# def get_text_lines(filepath: str) -> list[str]:
#     """
#     Return a flat list of text lines from a .txt or .pdf export file.

#     NOTE: for these PDFs, extract_tables() only picks up the bordered
#     header row and misses all the actual data rows below it (confirmed
#     via diagnose_pdf.py -- only the header has visible grid lines; the
#     body is plain aligned text with no rulings). Plain extract_text()
#     correctly returns clean, single-space-separated tokens per line,
#     which the whitespace-based parser below already handles.
#     """
#     if filepath.lower().endswith(".pdf"):
#         if pdfplumber is None:
#             raise RuntimeError("pdfplumber not installed")
#         lines = []
#         with pdfplumber.open(filepath) as pdf:
#             for page in pdf.pages:
#                 text = page.extract_text() or ""
#                 lines.extend(text.split("\n"))
#         return lines
#     else:
#         with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
#             return f.read().split("\n")


# def parse_commodity_line(line: str):
#     """
#     Try to parse one line as a commodity row.
#     Returns (hs_code, name_and_unit, cumulative_value_current_year) or None.
#     """
#     stripped = line.strip()
#     m = HS_CODE_RE.match(stripped)
#     if not m:
#         return None

#     hs_code, rest = m.groups()
#     hs_code = hs_code.zfill(8)  # normalize 7-digit (dropped-leading-zero) codes

#     # Split on whitespace into whole words -- this is the key fix.
#     # Commodity names like "FOWLS ... WT UPTO 185G" contain digits
#     # glued to letters; splitting on whitespace and requiring an exact
#     # (anchored) numeric match means "185G" is correctly left alone as
#     # part of the name, and only real standalone numbers/"--" count.
#     parts = rest.split()

#     first_num_idx = None
#     for i, p in enumerate(parts):
#         if TOKEN_RE.match(p):
#             first_num_idx = i
#             break

#     if first_num_idx is None:
#         return None

#     numeric_tokens = parts[first_num_idx:]
#     if len(numeric_tokens) < 4:
#         return None

#     name_and_unit = " ".join(parts[:first_num_idx])

#     def to_number(tok):
#         if tok in ("--", "-", ""):
#             return 0.0, False
#         cleaned = tok.replace(",", "").strip()
#         if not cleaned or not cleaned.isdigit():
#             return 0.0, True
#         return float(cleaned), False

#     cum_val_current, suspect = to_number(numeric_tokens[3])

#     return hs_code, name_and_unit, cum_val_current, suspect


# def parse_export_file(filepath: str, fiscal_year: str) -> pd.DataFrame:
#     """Parse one export report into a tidy commodity-level DataFrame."""
#     rows = []
#     for line in get_text_lines(filepath):
#         parsed = parse_commodity_line(line)
#         if parsed is None:
#             continue
#         hs_code, name_and_unit, cum_val, suspect = parsed

#         # Skip the GRAND TOTAL line if it ever matches (it won't, since
#         # it has no 8-digit code) -- kept here only as a safety note.
#         rows.append(
#             {
#                 "hs_code": hs_code,
#                 "hs_chapter": hs_code[:2],
#                 "commodity_raw": name_and_unit,
#                 "fiscal_year": fiscal_year,
#                 "value_pkr_thousands": cum_val,
#                 "suspect_row": suspect,
#             }
#         )

#     df = pd.DataFrame(rows)
#     if df.empty:
#         print(
#             f"  [!!! ERROR !!!] {filepath}: parsed ZERO rows. "
#             f"This file was NOT included in your combined data. "
#             f"Check that the file path is correct and that its text "
#             f"extraction is working (see diagnose_pdf.py)."
#         )
#         return df

#     if df["suspect_row"].any():
#         n_suspect = df["suspect_row"].sum()
#         print(
#             f"  [WARNING] {filepath}: {n_suspect} row(s) had an "
#             f"unparseable value token -- set to 0.0. Check these manually."
#         )

#     # Check for the SAME hs_code appearing more than once in this file
#     # (e.g. a repeated annexure/appendix section). Summing duplicates
#     # blindly can silently produce wildly wrong totals, so instead of
#     # doing that automatically, we flag them loudly for manual review.
#     dup_counts = df.groupby("hs_code").size()
#     dupes = dup_counts[dup_counts > 1]
#     if len(dupes) > 0:
#         print(
#             f"  [INFO] {filepath}: {len(dupes)} code(s) appear more than "
#             f"once (legitimate separate line items, e.g. multiple "
#             f"no-commercial-value entries) -- summing them: "
#             f"{list(dupes.index)[:10]}{'...' if len(dupes) > 10 else ''}"
#         )
#         dup_rows = df[df["hs_code"].isin(dupes.index)].sort_values("hs_code")
#         base_name = filepath.replace("\\", "/").split("/")[-1]
#         dup_rows.to_csv(f"duplicates_{base_name}.csv", index=False)
#         print(
#             f"     -> Saved to duplicates_{base_name}.csv if you want "
#             f"to spot-check any of these."
#         )

#     # Confirmed: duplicate hs_code rows are legitimate separate entries
#     # (not a parsing bug) -- sum them into one total per code/year.
#     df = (
#         df.groupby(
#             ["hs_code", "hs_chapter", "commodity_raw", "fiscal_year"], as_index=False
#         ).agg(
#             value_pkr_thousands=("value_pkr_thousands", "sum"),
#             suspect_row=("suspect_row", "any"),
#         )
#     )
#     return df


# def build_combined_export_table(file_year_pairs: list[tuple[str, str]]) -> pd.DataFrame:
#     """
#     file_year_pairs: list of (filepath, fiscal_year) tuples, e.g.
#         [("EXPORTS-BY-COMMODITIES-AND-COUNTRIES-2018-2019-1.txt", "2018-19"),
#          ("D-10_Export-06-2023.pdf", "2022-23"), ...]
#     """
#     all_dfs = [parse_export_file(fp, fy) for fp, fy in file_year_pairs]
#     combined = pd.concat(all_dfs, ignore_index=True)
#     return combined


# if __name__ == "__main__":
#     # --- Edit this list to match your actual filenames and fiscal years ---
#     # CONFIRMED from actual file headers:
#     #   D-10_Export-06-2022.pdf -> JUN 2022 / CUM Jul 2021-Jun 2022 -> FY2021-22
#     #   D-10_Export0624.pdf     -> JUN 2024 / CUM Jul 2023-Jun 2024 -> FY2023-24
#     #   D-10_Export-06-2023.pdf -> check its own header the same way
#     #                               (open page 1, read the "CUMULATIVE FROM"
#     #                               column dates) before trusting "2022-23" below
#     files = [
#         ("EXPORTS-BY-COMMODITIES-AND-COUNTRIES-2018-2019-1.txt", "2018-19"),
#         ("EXPORTS-BY-COMMODITIES-AND-COUNTRIES-2019-2020-1.txt", "2019-20"),
#         ("EXPORT-BY-COMMODITIES-AND-COUNTRIES-2020-21-1.txt", "2020-21"),
#         ("D-10_Export-06-2022.pdf", "2021-22"),
#         ("D-10_Export-06-2023.pdf", "2022-23"),  # verify this one
#         ("D-10_Export0624.pdf", "2023-24"),
#     ]

#     combined = build_combined_export_table(files)
#     print(combined.head(20))
#     print(f"\nTotal rows: {len(combined)}")
#     combined.to_csv("combined_exports.csv", index=False)
#     print("Saved to combined_exports.csv")

"""
Parser for PBS/D-10 "Exports by Commodities and Countries" reports.
Handles both plain .txt extracts and .pdf files (via pdfplumber).

Output: one row per HS code per fiscal year, with the CUMULATIVE
(full fiscal-year-to-date) export value in PKR thousands.
"""

import re
import pandas as pd

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# A commodity line starts with a 7- or 8-digit HS code at the start of
# the (stripped) line. Some PDFs drop the leading zero for chapters
# 01-09 (e.g. "1051100" instead of "01051100") -- both are accepted
# here and normalized to 8 digits below. Country sub-lines start with
# a letter, not a digit, so this naturally excludes them.
HS_CODE_RE = re.compile(r"^(\d{7,8})\s+(.*)$")

# A numeric data token must be a WHOLE whitespace-separated word --
# this is anchored (^...$) so a number embedded inside a word, like
# the "185" in "185G" (grams), is never mistaken for a data column.
TOKEN_RE = re.compile(r"^(--|-|\d[\d,]*)$")


def get_text_lines(filepath: str) -> list:
    """
    Return a flat list of text lines from a .txt or .pdf export file.
    """
    if filepath.lower().endswith(".pdf"):
        if pdfplumber is None:
            raise RuntimeError("pdfplumber not installed")
        lines = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.split("\n"))
        return lines
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().split("\n")


def parse_commodity_line(line: str):
    """
    Try to parse one line as a commodity row.
    Returns (hs_code, name_and_unit, cum_val_current, cum_val_prior, suspect)
    or None if the line is not a commodity row.

    Each report has 8 numeric tokens per commodity line:
      JUN_QTY, JUN_VAL, CUM_QTY, CUM_VAL  (current year)
      JUN_QTY, JUN_VAL, CUM_QTY, CUM_VAL  (prior year)
    We want token[3] (current year cumulative value) and
    token[7] (prior year cumulative value).
    """
    stripped = line.strip()
    m = HS_CODE_RE.match(stripped)
    if not m:
        return None

    hs_code, rest = m.groups()
    hs_code = hs_code.zfill(8)

    parts = rest.split()

    first_num_idx = None
    for i, p in enumerate(parts):
        if TOKEN_RE.match(p):
            first_num_idx = i
            break

    if first_num_idx is None:
        return None

    numeric_tokens = parts[first_num_idx:]
    if len(numeric_tokens) < 4:
        return None

    name_and_unit = " ".join(parts[:first_num_idx])

    def to_number(tok):
        if tok in ("--", "-", ""):
            return 0.0, False
        cleaned = tok.replace(",", "").strip()
        if not cleaned or not cleaned.isdigit():
            return 0.0, True
        return float(cleaned), False

    cum_val_current, suspect_current = to_number(numeric_tokens[3])

    if len(numeric_tokens) >= 8:
        cum_val_prior, suspect_prior = to_number(numeric_tokens[7])
    else:
        cum_val_prior, suspect_prior = None, False

    suspect = suspect_current or suspect_prior

    return hs_code, name_and_unit, cum_val_current, cum_val_prior, suspect


def parse_export_file(
    filepath: str,
    fiscal_year: str,
    prior_fiscal_year: str = None,
) -> pd.DataFrame:
    """
    Parse one export report into a tidy commodity-level DataFrame.

    If prior_fiscal_year is provided, also extracts the prior-year
    cumulative column from the same file and appends those rows too.
    This lets you get 2017-18 lag data from the 2018-19 file without
    needing a separate download.
    """
    current_rows = []
    prior_rows = []

    for line in get_text_lines(filepath):
        parsed = parse_commodity_line(line)
        if parsed is None:
            continue
        hs_code, name_and_unit, cum_val_current, cum_val_prior, suspect = parsed

        current_rows.append({
            "hs_code": hs_code,
            "hs_chapter": hs_code[:2],
            "commodity_raw": name_and_unit,
            "fiscal_year": fiscal_year,
            "value_pkr_thousands": cum_val_current,
            "suspect_row": suspect,
        })

        if prior_fiscal_year is not None and cum_val_prior is not None:
            prior_rows.append({
                "hs_code": hs_code,
                "hs_chapter": hs_code[:2],
                "commodity_raw": name_and_unit,
                "fiscal_year": prior_fiscal_year,
                "value_pkr_thousands": cum_val_prior,
                "suspect_row": suspect,
            })

    all_rows = current_rows + prior_rows
    df = pd.DataFrame(all_rows)

    if df.empty:
        print(
            f"  [!!! ERROR !!!] {filepath}: parsed ZERO rows. "
            f"Check file path and extraction."
        )
        return df

    if df["suspect_row"].any():
        n = df["suspect_row"].sum()
        print(f"  [WARNING] {filepath}: {n} unparseable token(s) set to 0.0")

    dup_counts = df.groupby(["hs_code", "fiscal_year"]).size()
    dupes = dup_counts[dup_counts > 1]
    if len(dupes) > 0:
        print(
            f"  [INFO] {filepath}: {len(dupes)} code(s) appear more than "
            f"once -- summing."
        )

    df = (
        df.groupby(
            ["hs_code", "hs_chapter", "commodity_raw", "fiscal_year"],
            as_index=False,
        ).agg(
            value_pkr_thousands=("value_pkr_thousands", "sum"),
            suspect_row=("suspect_row", "any"),
        )
    )
    return df


def build_combined_export_table(file_year_pairs: list) -> pd.DataFrame:
    """
    file_year_pairs: list of (filepath, fiscal_year) or
                     (filepath, fiscal_year, prior_fiscal_year) tuples.
    """
    all_dfs = []
    for entry in file_year_pairs:
        if len(entry) == 3:
            fp, fy, pfy = entry
            all_dfs.append(parse_export_file(fp, fy, prior_fiscal_year=pfy))
        else:
            fp, fy = entry
            all_dfs.append(parse_export_file(fp, fy))
    combined = pd.concat(all_dfs, ignore_index=True)
    return combined


if __name__ == "__main__":
    files = [
        # Extract 2018-19 AND pull prior-year block as 2017-18
        ("EXPORTS-BY-COMMODITIES-AND-COUNTRIES-2018-2019-1.txt", "2018-19", "2017-18"),
        ("EXPORTS-BY-COMMODITIES-AND-COUNTRIES-2019-2020-1.txt", "2019-20"),
        ("EXPORT-BY-COMMODITIES-AND-COUNTRIES-2020-21-1.txt",    "2020-21"),
        ("D-10_Export-06-2022.pdf", "2021-22"),
        ("D-10_Export-06-2023.pdf", "2022-23"),
        ("D-10_Export0624.pdf",     "2023-24"),
    ]

    combined = build_combined_export_table(files)
    print(combined.head(20))
    print(f"\nTotal rows     : {len(combined):,}")
    print(f"Fiscal years   : {sorted(combined['fiscal_year'].unique())}")
    combined.to_csv("combined_exports.csv", index=False)
    print("Saved to combined_exports.csv")