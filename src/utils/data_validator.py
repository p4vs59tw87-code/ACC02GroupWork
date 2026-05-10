# ============================================================
# Module: data_validator.py
# Purpose: Validate CSV structure before uploading to Coze
# Usage: python data_validator.py [path_to_csv]
# ============================================================

import sys
import pandas as pd

def validate_csv(filepath):
    """
    Check if the CSV has all required columns and reasonable values.
    """
    REQUIRED_COLUMNS = [
        'year', 'company_name', 'revenue', 'net_income',
        'free_cash_flow', 'gross_margin_pct', 'deliveries', 'asp'
    ]
    
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"❌ Cannot read file: {e}")
        return False
    
    # Check required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        print(f"❌ Missing required columns: {missing}")
        print(f"   Expected: {REQUIRED_COLUMNS}")
        return False
    
    print(f"✅ All required columns present: {list(df.columns)}")
    
    # Check for missing values
    for col in REQUIRED_COLUMNS:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            print(f"⚠️  Column '{col}' has {null_count} missing values")
    
    # Check data types and ranges
    if df['year'].min() < 2000 or df['year'].max() > 2030:
        print(f"⚠️  Years outside expected range (2000-2030): {df['year'].min()} - {df['year'].max()}")
    
    if (df['gross_margin_pct'] < -50).any() or (df['gross_margin_pct'] > 80).any():
        print("⚠️  Gross margin values outside typical range (-50% to 80%)")
    
    print(f"\n✅ Validation complete. {len(df)} records found.")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python data_validator.py path/to/your_data.csv")
        sys.exit(1)
    
    validate_csv(sys.argv[1])