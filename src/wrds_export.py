# ============================================================
# Script: wrds_export.py
# Purpose: Export financial data from WRDS Compustat for EV companies
# Output: CSV file compatible with the Coze valuation agent
# Dependencies: wrds, pandas
# 
# Usage: 
#   1. Configure WRDS connection on your machine
#   2. Update the 'companies' list and operating data dictionary
#   3. Run: python wrds_export.py
#   4. Upload the generated CSV to the Coze agent
# ============================================================

import wrds
import pandas as pd

# ----------------------------- CONFIGURATION ---------------------------------
# Users should modify this section based on their target companies

COMPANIES = [
    {'name': 'BYD', 'ticker': '002594', 'exchg': 'CHN', 'gvkey_override': 158050},
    {'name': 'Li Auto', 'ticker': 'LI', 'exchg': 'USA', 'gvkey_override': None},
    {'name': 'XPeng', 'ticker': 'XPEV', 'exchg': 'USA', 'gvkey_override': None},
    {'name': 'NIO', 'ticker': 'NIO', 'exchg': 'USA', 'gvkey_override': None},
]

OUTPUT_CSV = "ev_financial_data.csv"

# Years to extract (adjust as needed)
START_YEAR = 2020
END_YEAR = 2025

# Compustat fields to extract
COMPUSTAT_FIELDS = [
    'gvkey', 'datadate', 'fyear', 'sale', 'ni', 'oancf', 'capx',
    'at', 'lt', 'gp', 'xrd', 'ceq', 'csho'
]

# ----------------------------- HELPER FUNCTIONS ------------------------------

def add_operating_metrics(df):
    """
    Add deliveries (units) and ASP (average selling price in thousand CNY).
    Users MUST update this dictionary with real data from annual reports.
    
    Structure: {('CompanyName', year): (deliveries, asp)}
    """
    operating_data = {
        # BYD
        ('BYD', 2020): (400000, 150),
        ('BYD', 2021): (600000, 160),
        ('BYD', 2022): (1860000, 170),
        ('BYD', 2023): (3020000, 180),
        ('BYD', 2024): (3760000, 185),
        ('BYD', 2025): (4200000, 190),
        # Li Auto
        ('Li Auto', 2021): (90400, 250),
        ('Li Auto', 2022): (133200, 260),
        ('Li Auto', 2023): (376000, 280),
        ('Li Auto', 2024): (500000, 275),
        ('Li Auto', 2025): (520000, 270),
        # XPeng
        ('XPeng', 2021): (98100, 210),
        ('XPeng', 2022): (120800, 220),
        ('XPeng', 2023): (141600, 230),
        ('XPeng', 2024): (168000, 225),
        ('XPeng', 2025): (190000, 220),
        # NIO
        ('NIO', 2020): (43700, 350),
        ('NIO', 2021): (91400, 360),
        ('NIO', 2022): (122500, 370),
        ('NIO', 2023): (160000, 380),
        ('NIO', 2024): (200000, 375),
        ('NIO', 2025): (220000, 370),
    }
    
    deliveries_list = []
    asp_list = []
    for _, row in df.iterrows():
        key = (row['company_name'], row['year'])
        deliveries, asp = operating_data.get(key, (None, None))
        deliveries_list.append(deliveries)
        asp_list.append(asp)
    
    df['deliveries'] = deliveries_list
    df['asp'] = asp_list
    return df


def build_query(comp):
    """Build SQL query for a given company"""
    if comp['gvkey_override']:
        return f"""
        SELECT {', '.join(COMPUSTAT_FIELDS)}
        FROM comp.funda
        WHERE gvkey = {comp['gvkey_override']}
          AND fyear BETWEEN {START_YEAR} AND {END_YEAR}
          AND indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
        ORDER BY fyear
        """
    else:
        return f"""
        SELECT {', '.join(COMPUSTAT_FIELDS)}
        FROM comp.funda
        WHERE ticker = '{comp['ticker']}' AND exchg = '{comp['exchg']}'
          AND fyear BETWEEN {START_YEAR} AND {END_YEAR}
          AND indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
        ORDER BY fyear
        """


def compute_ratios(df):
    """Compute key financial ratios"""
    df['free_cash_flow'] = df['oancf'] - df['capx']
    df['gross_margin_pct'] = df['gp'] / df['sale'] * 100
    df['roe_pct'] = df['ni'] / df['ceq'] * 100
    df['leverage_pct'] = df['lt'] / df['at'] * 100
    return df


def rename_columns(df):
    """Rename to standard names expected by the agent"""
    rename_map = {
        'fyear': 'year',
        'sale': 'revenue',
        'ni': 'net_income',
        'fcf': 'free_cash_flow',  # computed, not original
        'gross_margin': 'gross_margin_pct',  # computed, not original
        'roe': 'roe_pct',
        'leverage': 'leverage_pct'
    }
    # Only rename columns that exist
    for old, new in rename_map.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)
    return df


# ----------------------------- MAIN EXECUTION ---------------------------------

def main():
    print("Connecting to WRDS...")
    db = wrds.Connection()
    
    all_data = []
    
    for comp in COMPANIES:
        print(f"Processing: {comp['name']}")
        query = build_query(comp)
        
        try:
            df = db.raw_sql(query)
            if df.empty:
                print(f"  Warning: No data for {comp['name']}, skipped")
                continue
            df['company_name'] = comp['name']
            all_data.append(df)
            print(f"  Retrieved {len(df)} rows")
        except Exception as e:
            print(f"  Query failed for {comp['name']}: {e}")
    
    if not all_data:
        print("No data retrieved. Please check company identifiers or WRDS connection.")
        db.close()
        return
    
    # Combine all companies
    combined = pd.concat(all_data, ignore_index=True)
    
    # Compute ratios
    combined = compute_ratios(combined)
    
    # Rename columns
    combined = rename_columns(combined)
    
    # Add operating metrics (manual)
    combined = add_operating_metrics(combined)
    
    # Keep only the columns the agent expects
    final_columns = ['year', 'company_name', 'revenue', 'net_income', 
                     'free_cash_flow', 'gross_margin_pct', 'deliveries', 'asp']
    combined = combined[final_columns].copy()
    
    # Drop rows with missing essential data
    combined = combined.dropna(subset=['revenue', 'net_income'], how='any')
    
    # Save to CSV
    combined.to_csv(OUTPUT_CSV, index=False)
    print(f"\nData saved to: {OUTPUT_CSV}")
    print(f"Total records: {len(combined)}")
    print("\nNow upload this CSV file to the Coze valuation agent.")
    
    db.close()


if __name__ == "__main__":
    main()