"""
Parser for PBS/D-10 "Exports by Commodities and Countries" reports.
Handles both plain .txt extracts and .pdf files (via pdfplumber).

Output: one row per HS code per fiscal year, with the CUMULATIVE
(full fiscal-year-to-date) export value in PKR thousands and quantity.

Core parsing strategy (v6):
  The 8 data columns are ALWAYS the last 8 numeric tokens on the line.
  Everything before the trailing numeric block is the commodity name.
  This is immune to unit words in names (FUSE BOX, BATH TUB), numbers
  in names (< 3 KG, 85.37, 650KVA), glued units (F/CKG, ROLLSKG),
  comparison operators (< >), and missing units (MACHINERY).
"""

import re
import pandas as pd

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

HS_CODE_RE = re.compile(r"^(\d{7,8})\s+(.*)$")
TOKEN_RE = re.compile(r"^(--|-|\d[\d,]*)$")


def get_text_lines(filepath: str) -> list:
    if filepath.lower().endswith(".pdf"):
        if pdfplumber is None:
            raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")
        lines = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.split("\n"))
        return lines
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().split("\n")


def to_number(tok: str):
    """
    (float, is_suspect)
    '--' / '-'  -> (0.0, False)   legitimately missing
    digits      -> (value, False)
    garbage     -> (0.0, True)
    """
    if tok in ("--", "-", ""):
        return 0.0, False
    cleaned = re.sub(r"[^\d.\-]+$", tok.replace(",", "").strip(), "")
    cleaned = tok.replace(",", "").strip()
    cleaned = re.sub(r"[^\d.\-]+$", "", cleaned)
    if not cleaned:
        return 0.0, True
    try:
        return float(cleaned), False
    except ValueError:
        return 0.0, True


def parse_commodity_line(line: str):
    """
    Returns (hs_code, name, cum_qty_current, cum_val_current,
             cum_qty_prior, cum_val_prior, suspect) or None.

    Column layout (last 8 numeric tokens on the line):
      [0] JUN_QTY  [1] JUN_VAL  [2] CUM_QTY  [3] CUM_VAL   <- current year
      [4] JUN_QTY  [5] JUN_VAL  [6] CUM_QTY  [7] CUM_VAL   <- prior year
    """
    stripped = line.strip()
    m = HS_CODE_RE.match(stripped)
    if not m:
        return None

    hs_code, rest = m.groups()
    hs_code = hs_code.zfill(8)
    parts = rest.split()
    if not parts:
        return None

    # Find the trailing block of numeric tokens
    trailing_start = len(parts)
    for i in range(len(parts) - 1, -1, -1):
        if TOKEN_RE.match(parts[i]):
            trailing_start = i
        else:
            break

    numeric_tokens = parts[trailing_start:]
    name_tokens    = parts[:trailing_start]

    if len(numeric_tokens) < 4:
        return None

    name = " ".join(name_tokens)

    cum_qty_current, sq = to_number(numeric_tokens[2])
    cum_val_current, sv = to_number(numeric_tokens[3])

    if len(numeric_tokens) >= 8:
        cum_qty_prior, _  = to_number(numeric_tokens[6])
        cum_val_prior, sp = to_number(numeric_tokens[7])
    else:
        cum_qty_prior = cum_val_prior = None
        sp = False

    return (
        hs_code, name,
        cum_qty_current, cum_val_current,
        cum_qty_prior, cum_val_prior,
        sq or sv or sp,
    )


def parse_export_file(filepath, fiscal_year, prior_fiscal_year=None):
    current_rows, prior_rows = [], []

    for line in get_text_lines(filepath):
        parsed = parse_commodity_line(line)
        if parsed is None:
            continue
        hs, name, cq, cv, pq, pv, suspect = parsed

        current_rows.append({
            "hs_code": hs, "hs_chapter": hs[:2], "commodity_raw": name,
            "fiscal_year": fiscal_year,
            "quantity": cq, "value_pkr_thousands": cv, "suspect_row": suspect,
        })
        if prior_fiscal_year is not None and pv is not None:
            prior_rows.append({
                "hs_code": hs, "hs_chapter": hs[:2], "commodity_raw": name,
                "fiscal_year": prior_fiscal_year,
                "quantity": pq, "value_pkr_thousands": pv, "suspect_row": suspect,
            })

    df = pd.DataFrame(current_rows + prior_rows)
    if df.empty:
        print(f"  [ERROR] {filepath}: zero rows parsed.")
        return df

    if df["suspect_row"].any():
        print(f"  [WARNING] {filepath}: {int(df['suspect_row'].sum())} suspect token(s)")

    dups = df.groupby(["hs_code", "fiscal_year"]).size()
    dups = dups[dups > 1]
    if len(dups):
        print(f"  [INFO] {filepath}: {len(dups)} HS code(s) appear >1 time — summing.")

    return (
        df.groupby(["hs_code","hs_chapter","commodity_raw","fiscal_year"], as_index=False)
          .agg(quantity=("quantity","sum"),
               value_pkr_thousands=("value_pkr_thousands","sum"),
               suspect_row=("suspect_row","any"))
    )


def build_combined_export_table(file_year_pairs):
    dfs = []
    for entry in file_year_pairs:
        fp, fy = entry[0], entry[1]
        pfy = entry[2] if len(entry) == 3 else None
        print(f"  Parsing {fp} ({fy}{', prior='+pfy if pfy else ''}) ...")
        dfs.append(parse_export_file(fp, fy, prior_fiscal_year=pfy))
    return pd.concat(dfs, ignore_index=True)


if __name__ == "__main__":
    files = [
        ("data/EXPORTS-BY-COMMODITIES-AND-COUNTRIES-2018-2019-1.txt", "2018-19", "2017-18"),
        ("data/EXPORTS-BY-COMMODITIES-AND-COUNTRIES-2019-2020-1.txt", "2019-20"),
        ("data/EXPORT-BY-COMMODITIES-AND-COUNTRIES-2020-21-1.txt",    "2020-21"),
        ("data/D-10_Export-06-2022.pdf", "2021-22"),
        ("data/D-10_Export-06-2023.pdf", "2022-23"),
        ("data/D-10_Export0624.pdf",     "2023-24"),
    ]

    combined = build_combined_export_table(files)

    print(f"\nTotal rows   : {len(combined):,}")
    print(f"Fiscal years : {sorted(combined['fiscal_year'].unique())}")
    print(f"Suspect rows : {int(combined['suspect_row'].sum())}")

    combined.to_csv("combined_exports.csv", index=False)
    print("Saved → combined_exports.csv")

    suspects = combined[combined["suspect_row"]].copy()
    if not suspects.empty:
        print(f"\n[AUDIT] {len(suspects)} suspect rows:")
        print(suspects[["hs_code","commodity_raw","fiscal_year",
                         "quantity","value_pkr_thousands"]].to_string())
        suspects.to_csv("suspect_rows_audit.csv", index=False)
        print("Saved → suspect_rows_audit.csv")
    else:
        print("\n[OK] Zero suspect rows.")