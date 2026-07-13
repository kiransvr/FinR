#!/usr/bin/env python
"""
Quick fix: Copy current Loan Accounts data to scored_accounts.csv
to restore correct Account No values in the dashboard.
"""
import pandas as pd
from pathlib import Path

raw_csv = Path("data/raw/Loan Accounts-Active.csv")
output_csv = Path("outputs/scored_accounts.csv")

if raw_csv.exists():
    df = pd.read_csv(raw_csv)
    print(f"✓ Loaded {len(df)} accounts from {raw_csv}")
    print(f"✓ First AccountNo: {df['AccountNo'].iloc[0] if 'AccountNo' in df.columns else 'NOT FOUND'}")
    
    # Save to outputs
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"✓ Saved to {output_csv}")
    print(f"✓ Verified: First 3 AccountNo values: {df['AccountNo'].head(3).tolist()}")
else:
    print(f"✗ File not found: {raw_csv}")
