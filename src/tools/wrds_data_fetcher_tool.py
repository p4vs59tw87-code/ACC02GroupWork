"""
WRDS Data Fetcher Tool
Connects to WRDS and fetches financial data for NEPV company analysis.
"""
import csv
import io
import re
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


@dataclass
class WRDSConnectionConfig:
    """WRDS connection configuration"""
    username: str
    password: Optional[str] = None
    use_ssh_key: bool = False
    ssh_key_path: Optional[str] = None
    account_type: str = "individual"  # "individual", "institutional", "academic"


@dataclass
class CompanyFinancials:
    """Container for company financial data from WRDS"""
    company_name: str
    ticker: str
    fiscal_years: List[int]
    revenue: List[Optional[float]]
    net_income: List[Optional[float]]
    operating_income: List[Optional[float]]
    gross_profit: List[Optional[float]]
    total_assets: List[Optional[float]]
    total_debt: List[Optional[float]]
    cash: List[Optional[float]]
    equity: List[Optional[float]]
    shares_outstanding: List[Optional[float]]
    fcf: List[Optional[float]]
    capex: List[Optional[float]]
    depreciation: List[Optional[float]]
    currency: str = "CNY"
    unit: str = "Million"


@dataclass  
class AnalysisResult:
    """Complete analysis result with metrics and charts"""
    company_name: str
    ticker: str
    period: str
    financials: CompanyFinancials
    metrics_summary: Dict[str, Any]
    growth_analysis: Dict[str, Any]
    margin_analysis: Dict[str, Any]
    chart_data: Dict[str, List[Any]]
    status: str
    message: str


def _parse_csv_data(csv_content: str) -> CompanyFinancials:
    """Parse CSV data in various WRDS export formats"""
    
    lines = csv_content.strip().split('\n')
    if len(lines) < 2:
        raise ValueError("CSV must contain header and data rows")
    
    reader = csv.reader(io.StringIO(csv_content))
    rows = list(reader)
    headers = [h.strip().lower() for h in rows[0]]
    
    # Detect format and extract data
    company_name = "Unknown"
    ticker = "UNK"
    fiscal_years = []
    
    # Arrays for each metric
    revenue, net_income, operating_income, gross_profit = [], [], [], []
    total_assets, total_debt, cash, equity = [], [], [], []
    shares_outstanding, fcf, capex, depreciation = [], [], [], []
    
    currency = "CNY"
    unit = "Million"
    
    # Map column names to data arrays
    column_map = {}
    for idx, header in enumerate(headers):
        header_lower = header.lower()
        
        # Extract company name and ticker
        if 'company' in header_lower or 'conm' in header_lower:
            column_map['company'] = idx
        elif 'ticker' in header_lower or 'tic' in header_lower:
            column_map['ticker'] = idx
        elif 'year' in header_lower or 'fyear' in header_lower or header in ['2020', '2021', '2022', '2023', '2024']:
            column_map['year'] = idx
        elif 'revenue' in header_lower or 'sale' in header_lower or 'atp' in header_lower:
            column_map['revenue'] = idx
        elif 'net income' in header_lower or 'ni' in header_lower or 'oiadp' in header_lower:
            column_map['net_income'] = idx
        elif 'operating' in header_lower and 'income' in header_lower:
            column_map['operating_income'] = idx
        elif 'gross' in header_lower and 'profit' in header_lower:
            column_map['gross_profit'] = idx
        elif 'total assets' in header_lower or 'at' in header_lower:
            column_map['total_assets'] = idx
        elif 'total debt' in header_lower or 'dltt' in header_lower or 'dlc' in header_lower:
            column_map['total_debt'] = idx
        elif 'cash' in header_lower or 'che' in header_lower:
            column_map['cash'] = idx
        elif 'equity' in header_lower or 'seq' in header_lower:
            column_map['equity'] = idx
        elif 'shares' in header_lower or 'csho' in header_lower:
            column_map['shares'] = idx
        elif 'fcf' in header_lower or 'free cash' in header_lower:
            column_map['fcf'] = idx
        elif 'capex' in header_lower or 'capital ex' in header_lower:
            column_map['capex'] = idx
        elif 'depreciation' in header_lower or 'dp' in header_lower or 'dpc' in header_lower:
            column_map['depreciation'] = idx
    
    # Parse data rows
    year_col = column_map.get('year')
    
    for row in rows[1:]:
        if len(row) < 2 or not any(row):
            continue
        
        # Extract company name
        if 'company' in column_map:
            company_name = row[column_map['company']].strip()
        
        # Extract ticker
        if 'ticker' in column_map:
            ticker = row[column_map['ticker']].strip()
        
        # Extract fiscal year
        if year_col is not None and year_col < len(row):
            year_str = row[year_col].strip()
            if re.match(r'^\d{4}$', year_str):
                fiscal_years.append(int(year_str))
            else:
                fiscal_years.append(fiscal_years[-1] + 1 if fiscal_years else 2020)
        else:
            fiscal_years.append(fiscal_years[-1] + 1 if fiscal_years else 2020)
        
        # Extract metrics
        def get_value(key):
            if key in column_map:
                idx = column_map[key]
                if idx < len(row):
                    val_str = row[idx].strip()
                    if val_str and val_str not in ['.', '-', 'N/A', '']:
                        try:
                            return float(re.sub(r'[¥$€£,()]', '', val_str))
                        except ValueError:
                            return None
            return None
        
        revenue.append(get_value('revenue'))
        net_income.append(get_value('net_income'))
        operating_income.append(get_value('operating_income'))
        gross_profit.append(get_value('gross_profit'))
        total_assets.append(get_value('total_assets'))
        total_debt.append(get_value('total_debt'))
        cash.append(get_value('cash'))
        equity.append(get_value('equity'))
        shares_outstanding.append(get_value('shares'))
        fcf.append(get_value('fcf'))
        capex.append(get_value('capex'))
        depreciation.append(get_value('depreciation'))
    
    # Detect currency and unit from data
    if any('$' in str(row) for row in rows[1:5] if len(row) > 0):
        currency = "USD"
        unit = "Million"
    elif any('¥' in str(row) for row in rows[1:5] if len(row) > 0):
        currency = "CNY"
        unit = "Million"
    
    return CompanyFinancials(
        company_name=company_name,
        ticker=ticker,
        fiscal_years=fiscal_years,
        revenue=revenue,
        net_income=net_income,
        operating_income=operating_income,
        gross_profit=gross_profit,
        total_assets=total_assets,
        total_debt=total_debt,
        cash=cash,
        equity=equity,
        shares_outstanding=shares_outstanding,
        fcf=fcf,
        capex=capex,
        depreciation=depreciation,
        currency=currency,
        unit=unit
    )


def _calculate_metrics(financials: CompanyFinancials) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Calculate financial metrics from raw data"""
    
    metrics = {}
    growth = {}
    margins = {}
    
    n = len(financials.fiscal_years)
    
    # Revenue metrics
    if financials.revenue and any(financials.revenue):
        rev_values = [r for r in financials.revenue if r is not None]
        if len(rev_values) >= 2:
            cagr = ((rev_values[-1] / rev_values[0]) ** (1 / (n - 1)) - 1) * 100 if n > 1 else 0
            metrics['revenue_cagr'] = round(cagr, 2)
            metrics['revenue_5y_sum'] = round(sum(rev_values), 2)
        
        # YoY growth
        growth['revenue_yoy'] = []
        for i in range(1, n):
            if financials.revenue[i] and financials.revenue[i-1] and financials.revenue[i-1] != 0:
                growth_rate = (financials.revenue[i] - financials.revenue[i-1]) / financials.revenue[i-1] * 100
                growth['revenue_yoy'].append({
                    'year': financials.fiscal_years[i],
                    'growth': round(growth_rate, 2)
                })
    
    # Profit margins
    if financials.revenue and financials.gross_profit:
        margins['gross_margin'] = []
        for i in range(n):
            if financials.revenue[i] and financials.revenue[i] != 0 and financials.gross_profit[i]:
                margin = financials.gross_profit[i] / financials.revenue[i] * 100
                margins['gross_margin'].append({
                    'year': financials.fiscal_years[i],
                    'margin': round(margin, 2)
                })
    
    if financials.revenue and financials.operating_income:
        margins['operating_margin'] = []
        for i in range(n):
            if financials.revenue[i] and financials.revenue[i] != 0 and financials.operating_income[i]:
                margin = financials.operating_income[i] / financials.revenue[i] * 100
                margins['operating_margin'].append({
                    'year': financials.fiscal_years[i],
                    'margin': round(margin, 2)
                })
    
    if financials.revenue and financials.net_income:
        margins['net_margin'] = []
        for i in range(n):
            if financials.revenue[i] and financials.revenue[i] != 0 and financials.net_income[i]:
                margin = financials.net_income[i] / financials.revenue[i] * 100
                margins['net_margin'].append({
                    'year': financials.fiscal_years[i],
                    'margin': round(margin, 2)
                })
    
    # Latest values
    if financials.revenue:
        metrics['latest_revenue'] = financials.revenue[-1]
    if financials.net_income:
        metrics['latest_net_income'] = financials.net_income[-1]
    if financials.fcf:
        metrics['latest_fcf'] = financials.fcf[-1]
    if financials.equity:
        metrics['latest_equity'] = financials.equity[-1]
    if financials.total_assets and financials.total_debt and financials.cash:
        net_debt = financials.total_debt[-1] - financials.cash[-1] if financials.total_debt[-1] and financials.cash[-1] else None
        metrics['latest_net_debt'] = net_debt
    if financials.shares_outstanding:
        metrics['latest_shares'] = financials.shares_outstanding[-1]
    
    # Calculate FCF if not provided
    if not financials.fcf and financials.operating_income:
        calculated_fcf = []
        for i in range(n):
            op_inc = financials.operating_income[i] or 0
            cap = financials.capex[i] if financials.capex[i] else 0
            dep = financials.depreciation[i] if financials.depreciation[i] else 0
            # Simplified FCF: Net Income approximation
            calculated_fcf.append(op_inc - cap)
        financials.fcf = calculated_fcf
    
    # Summary stats
    if margins.get('net_margin'):
        margins['avg_net_margin'] = round(sum(m['margin'] for m in margins['net_margin']) / len(margins['net_margin']), 2)
    if margins.get('gross_margin'):
        margins['avg_gross_margin'] = round(sum(m['margin'] for m in margins['gross_margin']) / len(margins['gross_margin']), 2)
    
    return metrics, growth, margins


def _prepare_chart_data(financials: CompanyFinancials, metrics: Dict, growth: Dict, margins: Dict) -> Dict[str, List]:
    """Prepare data for chart visualization"""
    
    years = financials.fiscal_years
    
    chart_data = {
        'timeline': years,
        'revenue': financials.revenue,
        'net_income': financials.net_income,
        'fcf': financials.fcf if financials.fcf else [],
        'gross_margin': [m['margin'] for m in margins.get('gross_margin', [])],
        'operating_margin': [m['margin'] for m in margins.get('operating_margin', [])],
        'net_margin': [m['margin'] for m in margins.get('net_margin', [])],
        'revenue_growth': [g['growth'] for g in growth.get('revenue_yoy', [])],
    }
    
    return chart_data


def _generate_wrds_query_script(ticker: str, company_name: str, start_year: int = 2019, end_year: int = 2024) -> str:
    """Generate WRDS SAS/R/Python query script for the user to execute on WRDS"""
    
    script = f"""
================================================================================
WRDS DATA QUERY SCRIPT FOR NEPV ANALYSIS: {company_name} ({ticker})
================================================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OPTION 1: SAS Script for WRDS Cloud (Recommended)
--------------------------------------------------------------------------------
Copy and paste this SAS code into WRDS SAS OnDemand:

```sas
/* Connect to Compustat Fundamentals Annual */
proc sql;
    connect to oracle as wrds (&ora_conn);
    
    /* Revenue, Net Income, Operating Income */
    select gvkey, fyear, at, revt, ni, oibpdp, gp
    into :gvkey, :fyear, :at, :revt, :ni, :oibpdp, :gp
    from comp.funda
    where tic = "{ticker}"
      and fyear between {start_year} and {end_year}
      and consol = 'C'
      and popsrc = 'I'
    order by fyear;
    
    disconnect from wrds;
quit;

/* Get balance sheet data */
proc sql;
    connect to oracle as wrds (&ora_conn);
    
    select gvkey, fyear, act, lct, dltt, dlc, che, seq, csho
    into :act, :lct, :dltt, :dlc, :che, :seq, :csho
    from comp.funda
    where tic = "{ticker}"
      and fyear between {start_year} and {end_year}
    order by fyear;
    
    disconnect from wrds;
quit;
```

OPTION 2: Python Script for WRDS API (wrds package)
--------------------------------------------------------------------------------
```python
import wrds
import pandas as pd

# Connect to WRDS
db = wrds.Connection()

# Query fundamentals
query = f\"\"\"
SELECT fyear, tic, conm, at, revt, ni, oibpdp, gp,
       dltt, dlc, che, seq, csho
FROM comp.funda
WHERE tic = '{ticker}'
  AND fyear BETWEEN {start_year} AND {end_year}
  AND consol = 'C'
  AND popsrc = 'I'
ORDER BY fyear
\"\"\"

df = db.raw_sql(query)

# Save to CSV
df.to_csv('{ticker}_financials.csv', index=False)

db.close()
```

OPTION 3: Manual Export via WRDS Web Interface
--------------------------------------------------------------------------------
1. Go to: https://wrds-www.wharton.upenn.edu/
2. Navigate to: Compustat > North America > Fundamentals Annual
3. Apply filters:
   - Ticker: {ticker}
   - Fiscal Year: {start_year}-{end_year}
   - Data items: at, revt, ni, oibpdp, gp, dltt, dlc, che, seq, csho
4. Export as CSV

================================================================================
"""
    return script


@tool
def wrds_data_fetcher(
    wrds_username: str,
    ticker: str,
    company_name: str = "",
    start_year: str = "2019",
    end_year: str = "2024",
    csv_data: str = ""
) -> str:
    """
    Fetch financial data from WRDS for NEPV company analysis.
    
    This tool can work in two modes:
    1. DIRECT MODE: If user provides CSV data directly, parse and analyze it
    2. QUERY MODE: Generate WRDS query scripts for user to execute
    
    Args:
        wrds_username: WRDS account username (for query generation)
        ticker: Stock ticker symbol (e.g., "BYD", "NIO", "LI")
        company_name: Company name (optional, for display purposes)
        start_year: Start year for data query (default: "2019")
        end_year: End year for data query (default: "2024")
        csv_data: Direct CSV data from WRDS export (optional - if provided, will analyze directly)
    
    Returns:
        - If CSV provided: Complete financial analysis with metrics and chart data
        - If no CSV: WRDS query script for user to execute
    
    Example:
        // Direct data analysis
        wrds_data_fetcher(
            wrds_username="user@university.edu",
            ticker="BYD",
            company_name="BYD Company Limited",
            csv_data="Company,Year,Revenue,NetIncome\\nBYD,2020,156598,4233..."
        )
        
        // Generate query script
        wrds_data_fetcher(
            wrds_username="user@university.edu",
            ticker="BYD",
            company_name="BYD Company Limited"
        )
    """
    ctx = request_context.get() or new_context(method="wrds_data_fetcher")
    
    try:
        ticker = ticker.upper().strip()
        
        # Mode 1: Direct CSV data provided - analyze immediately
        if csv_data and csv_data.strip():
            financials = _parse_csv_data(csv_data)
            metrics, growth, margins = _calculate_metrics(financials)
            chart_data = _prepare_chart_data(financials, metrics, growth, margins)
            
            # Generate analysis report
            report = []
            report.append("=" * 70)
            report.append("WRDS FINANCIAL DATA ANALYSIS")
            report.append(f"Company: {financials.company_name} ({ticker})")
            report.append("=" * 70)
            
            report.append(f"\nData Period: {financials.fiscal_years[0]} - {financials.fiscal_years[-1]}")
            report.append(f"Currency: {financials.currency}")
            report.append(f"Unit: {financials.unit}")
            
            # Summary metrics
            report.append("\n" + "-" * 70)
            report.append("KEY METRICS SUMMARY")
            report.append("-" * 70)
            
            if metrics.get('revenue_cagr'):
                report.append(f"\nRevenue CAGR (5Y):     {metrics['revenue_cagr']:.1f}%")
            if metrics.get('latest_revenue'):
                report.append(f"Latest Revenue:        {metrics['latest_revenue']:,.2f} {financials.currency}")
            if metrics.get('latest_net_income'):
                report.append(f"Latest Net Income:     {metrics['latest_net_income']:,.2f}")
            if metrics.get('latest_fcf'):
                report.append(f"Latest FCF:            {metrics['latest_fcf']:,.2f}")
            if metrics.get('avg_gross_margin'):
                report.append(f"Avg Gross Margin:      {metrics['avg_gross_margin']:.1f}%")
            if metrics.get('avg_net_margin'):
                report.append(f"Avg Net Margin:        {margins['avg_net_margin']:.1f}%")
            if metrics.get('latest_net_debt'):
                report.append(f"Latest Net Debt:       {metrics['latest_net_debt']:,.2f}")
            if metrics.get('latest_shares'):
                report.append(f"Latest Shares:         {metrics['latest_shares']:,.2f}M")
            
            # Chart data for visualization
            report.append("\n" + "-" * 70)
            report.append("CHART DATA (JSON Format for Visualization)")
            report.append("-" * 70)
            report.append(f"\n{chart_data}")
            
            # Historical data table
            report.append("\n" + "-" * 70)
            report.append("HISTORICAL FINANCIAL DATA")
            report.append("-" * 70)
            report.append(f"\n{'Year':<8} {'Revenue':>15} {'Net Income':>12} {'FCF':>12} {'Net Margin':>12}")
            report.append("-" * 60)
            
            for i, year in enumerate(financials.fiscal_years):
                rev = f"{financials.revenue[i]:,.0f}" if financials.revenue[i] else "N/A"
                ni = f"{financials.net_income[i]:,.0f}" if financials.net_income[i] else "N/A"
                fcf_val = f"{financials.fcf[i]:,.0f}" if i < len(financials.fcf) and financials.fcf[i] else "N/A"
                nm = f"{margins['net_margin'][i]['margin']:.1f}%" if i < len(margins.get('net_margin', [])) else "N/A"
                report.append(f"{year:<8} {rev:>15} {ni:>12} {fcf_val:>12} {nm:>12}")
            
            report.append("\n" + "=" * 70)
            report.append("STATUS: Data analysis complete. Ready for DCF valuation.")
            report.append("=" * 70)
            
            return "\n".join(report)
        
        # Mode 2: Generate query script for user to execute on WRDS
        else:
            script = _generate_wrds_query_script(
                ticker=ticker,
                company_name=company_name or ticker,
                start_year=int(start_year),
                end_year=int(end_year)
            )
            
            response = []
            response.append("=" * 70)
            response.append("WRDS DATA QUERY INSTRUCTIONS")
            response.append("=" * 70)
            response.append(f"""
To fetch financial data for {company_name or ticker} ({ticker}), please:

STEP 1: Execute the following script on WRDS (choose one method)

{script}

STEP 2: After obtaining the CSV data, paste it back to me with:
- The CSV content
- The company ticker: {ticker}

I will then:
1. Parse and analyze the financial data
2. Generate visualizations
3. Calculate DCF valuation based on your assumptions
4. Produce a complete research report
""")
            response.append("=" * 70)
            
            return "\n".join(response)
    
    except Exception as e:
        return f"Error processing data: {str(e)}\n\nPlease check the data format and try again."
