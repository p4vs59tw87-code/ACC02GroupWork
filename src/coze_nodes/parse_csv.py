# ============================================================
# Node Name: parse_financial_csv
# Coze Code Node
# 
# Input: uploaded_file (Coze file object from user upload)
# Output: financial_records (JSON string), company_names (str), metadata
# ============================================================

import pandas as pd
import io
import json

def main(uploaded_file):
    """
    Parse a CSV file uploaded by the user.
    Expected columns: year, company_name, revenue, net_income, 
                      free_cash_flow, gross_margin_pct, deliveries, asp
    """
    
    # ----------------------------- FILE READING ---------------------------------
    if hasattr(uploaded_file, 'content'):
        content = uploaded_file.content
    elif isinstance(uploaded_file, bytes):
        content = uploaded_file
    else:
        try:
            with open(uploaded_file, 'rb') as f:
                content = f.read()
        except Exception as e:
            return {
                "error": f"Cannot read file: {str(e)}",
                "financial_records": "[]",
                "company_names": "",
                "record_count": 0
            }
    
    # ----------------------------- CSV PARSING ---------------------------------
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        return {
            "error": f"CSV parsing failed: {str(e)}",
            "financial_records": "[]",
            "company_names": "",
            "record_count": 0
        }
    
    # ----------------------------- COLUMN NORMALIZATION ------------------------
    # Expected columns and their possible aliases
    column_mapping = {
        'year': ['year', 'fyear', 'Year'],
        'company_name': ['company_name', 'CompanyName', 'name', 'Name'],
        'revenue': ['revenue', 'sale', 'Revenue', 'Sales'],
        'net_income': ['net_income', 'ni', 'NetIncome', 'NI'],
        'free_cash_flow': ['free_cash_flow', 'fcf', 'FCF', 'FreeCashFlow'],
        'gross_margin_pct': ['gross_margin_pct', 'gross_margin', 'GrossMargin', 'GrossMarginPct'],
        'deliveries': ['deliveries', 'Deliveries', 'sales_volume'],
        'asp': ['asp', 'ASP', 'avg_selling_price', 'AvgSellingPrice']
    }
    
    normalized = {}
    for target, aliases in column_mapping.items():
        found = None
        for col in aliases:
            if col in df.columns:
                found = col
                break
        if found:
            normalized[target] = df[found]
        else:
            normalized[target] = pd.Series([None] * len(df))
    
    # Create normalized DataFrame
    df_norm = pd.DataFrame(normalized)
    
    # Drop rows with missing essential fields
    df_norm = df_norm.dropna(subset=['year', 'company_name', 'revenue'])
    
    if df_norm.empty:
        return {
            "error": "No valid data rows. Ensure CSV has required columns: year, company_name, revenue",
            "financial_records": "[]",
            "company_names": "",
            "record_count": 0
        }
    
    # Convert year to integer if possible
    df_norm['year'] = df_norm['year'].astype(int)
    
    # ----------------------------- PREPARE OUTPUT ------------------------------
    records = df_norm.to_dict(orient='records')
    companies = sorted(df_norm['company_name'].unique())
    years = sorted(df_norm['year'].unique())
    
    return {
        "error": "",
        "financial_records": json.dumps(records),
        "company_names": ", ".join(companies),
        "years_min": min(years) if years else None,
        "years_max": max(years) if years else None,
        "record_count": len(records)
    }