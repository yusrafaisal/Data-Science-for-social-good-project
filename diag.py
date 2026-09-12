"""
Diagnostic: figure out why HS chapters 01-09 are missing from the
2022-23 file's parsed output, even though they exist in the source PDF.
"""

import pdfplumber
from parse_exports import parse_commodity_line

filepath = "D-10_Export-06-2023.pdf"

with pdfplumber.open(filepath) as pdf:
    print(f"Total pages: {len(pdf.pages)}")

    # Check the first 3 pages specifically, since that's where
    # chapters 01-02 should live based on the screenshot.
    for page_num in range(3):
        page = pdf.pages[page_num]
        text = page.extract_text() or ""
        lines = text.split("\n")

        print(f"\n--- PAGE {page_num + 1} ---")
        print(f"Raw line count: {len(lines)}")

        parsed_count = 0
        for line in lines:
            result = parse_commodity_line(line)
            if result is not None:
                parsed_count += 1
        print(f"Lines that parsed as commodity rows: {parsed_count}")

        # Show the first 15 raw lines so we can see exactly what
        # extract_text() produced for this page, unfiltered.
        print("First 15 raw lines:")
        for l in lines[:15]:
            print(repr(l))