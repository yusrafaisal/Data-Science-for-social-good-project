import pandas as pd
import numpy as np

df = pd.read_csv("modeling_dataset.csv", dtype={"hs_code": str, "hs_chapter": str})

# 1. Log transforms
df["log_export_usd"] = np.log1p(df["export_usd_thousands"])
df["log_export_qty"] = np.log1p(df["quantity"])
df["log_export_usd_lag"] = np.log1p(df["export_usd_lag"].fillna(0))
df["log_export_qty_lag"] = np.log1p(df["export_qty_lag"].fillna(0))

# 2. Top-20% flag (within each fiscal year)
threshold = df.groupby("fiscal_year")["export_usd_thousands"].transform(
    lambda x: x.quantile(0.80)
)
df["top20_flag"] = (df["export_usd_thousands"] >= threshold).astype(int)

df.to_csv("eda_dataset.csv", index=False)
print(f"Saved eda_dataset.csv — {len(df):,} rows, {df.columns.tolist()}")