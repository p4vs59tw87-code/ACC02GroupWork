"""
Smart Data Input Tool
Handles data input via CSV upload or manual entry.
Since WRDS requires Duo Mobile verification (which blocks automation), 
we provide multiple convenient input methods.
"""
import json
import re
import csv
import io
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


@dataclass
class CompanyData:
    """Standardized company financial data"""
    company_name: str
    ticker: str
    currency: str
    unit: str
    fiscal_years: List[int]
    revenue: List[Optional[float]]
    net_income: List[Optional[float]]
    operating_income: List[Optional[float]]
    gross_profit: List[Optional[float]]
    fcf: List[Optional[float]]
    total_assets: List[Optional[float]]
    total_liabilities: List[Optional[float]]
    total_debt: List[Optional[float]]
    cash: List[Optional[float]]
    equity: List[Optional[float]]
    shares_outstanding: List[Optional[float]]


@dataclass
class DataInputResult:
    """Result of data input processing"""
    success: bool
    company_data: Optional[CompanyData]
    metrics: Dict[str, Any]
    chart_data: Dict[str, List[Any]]
    message: str
    warnings: List[str]
    raw_data_preview: str


def _detect_format(data: str) -> str:
    """Detect the format of input data"""
    lines = data.strip().split('\n')
    if len(lines) < 2:
        return "empty"
    
    # Check if it's CSV format
    if ',' in lines[0] and '\t' not in lines[0]:
        return "csv"
    
    # Check if it's TSV format (from some WRDS exports)
    if '\t' in lines[0]:
        return "tsv"
    
    # Check if it's JSON format
    try:
        json.loads(data)
        return "json"
    except:
        pass
    
    # Check if it's Excel-like (semicolon separated)
    if ';' in lines[0]:
        return "semicolon"
    
    return "unknown"


def _parse_generic_csv(data: str, delimiter: str = ',') -> List[Dict[str, Any]]:
    """Parse CSV/TSV data into list of dictionaries"""
    rows = list(csv.DictReader(io.StringIO(data), delimiter=delimiter))
    return rows


def _normalize_column_name(col: str) -> str:
    """Normalize column names to standard format"""
    col_lower = col.lower().strip().replace('_', ' ')
    
    # Year columns
    if re.match(r'^\d{4}$', col):
        return 'year'
    
    # Revenue
    if any(k in col_lower for k in ['revenue', 'revt', 'sales', 'net sales', 'total revenue']):
        return 'revenue'
    
    # Net Income
    if any(k in col_lower for k in ['net income', 'ni', 'net profit', 'earnings']):
        return 'net_income'
    
    # Operating Income
    if any(k in col_lower for k in ['operating income', 'oibdp', 'operating profit', 'ebit']):
        return 'operating_income'
    
    # Gross Profit
    if any(k in col_lower for k in ['gross profit', 'gp', 'gross margin']):
        return 'gross_profit'
    
    # Free Cash Flow
    if any(k in col_lower for k in ['fcf', 'free cash', 'cash flow']):
        return 'fcf'
    
    # Total Assets
    if any(k in col_lower for k in ['total asset', 'at']):
        return 'total_assets'
    
    # Total Liabilities
    if any(k in col_lower for k in ['total liab', 'lt']):
        return 'total_liabilities'
    
    # Total Debt
    if any(k in col_lower for k in ['total debt', 'dltt', 'dlc', 'long term debt']):
        return 'total_debt'
    
    # Cash
    if any(k in col_lower for k in ['cash', 'che', 'cash equiv']):
        return 'cash'
    
    # Equity
    if any(k in col_lower for k in ['total equity', 'seq', 'shareholders', 'book value']):
        return 'equity'
    
    # Shares Outstanding
    if any(k in col_lower for k in ['shares', 'csho', 'shares out']):
        return 'shares_outstanding'
    
    # Company name
    if any(k in col_lower for k in ['company', 'conm', 'company name']):
        return 'company_name'
    
    # Ticker
    if any(k in col_lower for k in ['ticker', 'tic', 'symbol']):
        return 'ticker'
    
    return 'unknown'


def _parse_numeric(val: Any) -> Optional[float]:
    """Parse a numeric value from various formats"""
    if val is None:
        return None
    
    if isinstance(val, (int, float)):
        return float(val)
    
    val_str = str(val).strip()
    
    # Handle empty/invalid values
    if not val_str or val_str in ['-', '.', 'N/A', 'NA', 'null', '', 'none']:
        return None
    
    # Remove currency symbols and thousands separators
    val_str = re.sub(r'[¥$€£¥,\s]', '', val_str)
    
    # Handle parentheses for negative numbers
    if val_str.startswith('(') and val_str.endswith(')'):
        val_str = '-' + val_str[1:-1]
    
    # Remove any remaining non-numeric except . and -
    val_str = re.sub(r'[^\d.\-]', '', val_str)
    
    if not val_str or val_str in ['.', '-', '']:
        return None
    
    try:
        return float(val_str)
    except ValueError:
        return None


def _detect_currency_unit(data: str) -> tuple[str, str]:
    """Detect currency and unit from data"""
    data_lower = data.lower()
    
    currency = "CNY"
    if '$' in data or 'usd' in data_lower:
        currency = "USD"
    elif '€' in data or 'eur' in data_lower:
        currency = "EUR"
    
    unit = "Million"
    if 'thousand' in data_lower or 'k' in data_lower:
        unit = "Thousand"
    elif 'billion' in data_lower or 'bn' in data_lower:
        unit = "Billion"
    
    return currency, unit


def _parse_data_input(data: str) -> DataInputResult:
    """Parse various formats of input data"""
    warnings = []
    
    # Detect format
    fmt = _detect_format(data)
    
    if fmt == "empty":
        return DataInputResult(
            success=False,
            company_data=None,
            metrics={},
            chart_data={},
            message="No data provided",
            warnings=["Please provide financial data"]
        )
    
    if fmt == "unknown":
        return DataInputResult(
            success=False,
            company_data=None,
            metrics={},
            chart_data={},
            message="Unknown data format",
            warnings=["Could not detect data format. Please use CSV, TSV, or JSON format."]
        )
    
    # Parse based on format
    try:
        if fmt == "json":
            raw_data = json.loads(data)
            if isinstance(raw_data, list):
                rows = raw_data
            else:
                rows = [raw_data]
        else:
            delimiter = ',' if fmt == 'csv' else ('\t' if fmt == 'tsv' else ';')
            rows = _parse_generic_csv(data, delimiter)
    except Exception as e:
        return DataInputResult(
            success=False,
            company_data=None,
            metrics={},
            chart_data={},
            message=f"Failed to parse data: {str(e)}",
            warnings=[str(e)]
        )
    
    if not rows:
        return DataInputResult(
            success=False,
            company_data=None,
            metrics={},
            chart_data={},
            message="No data rows found",
            warnings=["Data appears to be empty"]
        )
    
    # Get column headers
    headers = list(rows[0].keys())
    normalized_headers = {col: _normalize_column_name(col) for col in headers}
    
    # Detect currency and unit
    currency, unit = _detect_currency_unit(data)
    
    # Extract company info
    company_name = ""
    ticker = ""
    
    for col, norm in normalized_headers.items():
        if norm == 'company_name' and col in rows[0]:
            company_name = str(rows[0][col]).strip()
        if norm == 'ticker' and col in rows[0]:
            ticker = str(rows[0][col]).strip().upper()
    
    if not company_name:
        company_name = "Unknown Company"
    if not ticker:
        ticker = "N/A"
    
    # Extract year-indexed data
    year_data: Dict[int, Dict[str, Optional[float]]] = {}
    all_years = set()
    
    for row in rows:
        year = None
        
        # Find year column
        for col, val in row.items():
            if re.match(r'^\d{4}$', str(val).strip()):
                year = int(str(val).strip())
                break
        
        if year is None:
            # Try to find year column by header name
            for col, norm in normalized_headers.items():
                if norm == 'year' and col in row:
                    year = _parse_numeric(row[col])
                    if year:
                        year = int(year)
                    break
        
        if year is None:
            # Skip rows without year
            continue
        
        all_years.add(year)
        
        if year not in year_data:
            year_data[year] = {
                'revenue': None,
                'net_income': None,
                'operating_income': None,
                'gross_profit': None,
                'fcf': None,
                'total_assets': None,
                'total_liabilities': None,
                'total_debt': None,
                'cash': None,
                'equity': None,
                'shares_outstanding': None,
            }
        
        # Extract metrics for this year
        for col, val in row.items():
            norm = normalized_headers.get(col, 'unknown')
            if norm in year_data[year]:
                parsed_val = _parse_numeric(val)
                if parsed_val is not None:
                    year_data[year][norm] = parsed_val
        
        # Also try to extract company info from row
        for col, norm in normalized_headers.items():
            if norm in ['company_name', 'ticker']:
                if not locals().get(norm.replace('_', '')):
                    val = row.get(col, '').strip()
                    if val:
                        if norm == 'company_name':
                            company_name = val
                        elif norm == 'ticker':
                            ticker = val.upper()
    
    # Convert to lists
    years = sorted(all_years)
    n = len(years)
    
    if n == 0:
        return DataInputResult(
            success=False,
            company_data=None,
            metrics={},
            chart_data={},
            message="No valid year data found",
            warnings=["Could not find any years in the data"]
        )
    
    # Build arrays
    revenue = [year_data.get(y, {}).get('revenue') for y in years]
    net_income = [year_data.get(y, {}).get('net_income') for y in years]
    operating_income = [year_data.get(y, {}).get('operating_income') for y in years]
    gross_profit = [year_data.get(y, {}).get('gross_profit') for y in years]
    fcf = [year_data.get(y, {}).get('fcf') for y in years]
    total_assets = [year_data.get(y, {}).get('total_assets') for y in years]
    total_liabilities = [year_data.get(y, {}).get('total_liabilities') for y in years]
    total_debt = [year_data.get(y, {}).get('total_debt') for y in years]
    cash = [year_data.get(y, {}).get('cash') for y in years]
    equity = [year_data.get(y, {}).get('equity') for y in years]
    shares_outstanding = [year_data.get(y, {}).get('shares_outstanding') for y in years]
    
    # Calculate missing FCF if possible
    for i in range(n):
        if fcf[i] is None and operating_income[i] is not None:
            fcf[i] = operating_income[i] * 0.8  # Estimate FCF as 80% of operating income
    
    # Create company data object
    company_data = CompanyData(
        company_name=company_name,
        ticker=ticker,
        currency=currency,
        unit=unit,
        fiscal_years=years,
        revenue=revenue,
        net_income=net_income,
        operating_income=operating_income,
        gross_profit=gross_profit,
        fcf=fcf,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_debt=total_debt,
        cash=cash,
        equity=equity,
        shares_outstanding=shares_outstanding
    )
    
    # Calculate metrics
    metrics = _calculate_metrics(company_data)
    
    # Prepare chart data
    chart_data = _prepare_chart_data(company_data, metrics)
    
    # Generate preview
    preview = _generate_preview(company_data, metrics)
    
    return DataInputResult(
        success=True,
        company_data=company_data,
        metrics=metrics,
        chart_data=chart_data,
        message=f"Successfully parsed data for {company_name} ({ticker})",
        warnings=warnings,
        raw_data_preview=preview
    )


def _calculate_metrics(data: CompanyData) -> Dict[str, Any]:
    """Calculate financial metrics"""
    metrics = {}
    n = len(data.fiscal_years)
    
    # Revenue CAGR
    rev_values = [r for r in data.revenue if r is not None and r > 0]
    if len(rev_values) >= 2:
        cagr = ((rev_values[-1] / rev_values[0]) ** (1 / (n - 1)) - 1) * 100
        metrics['revenue_cagr'] = round(cagr, 2)
    
    # Latest values
    if data.revenue and data.revenue[-1]:
        metrics['latest_revenue'] = round(data.revenue[-1], 2)
    if data.net_income and data.net_income[-1]:
        metrics['latest_net_income'] = round(data.net_income[-1], 2)
    if data.fcf and data.fcf[-1]:
        metrics['latest_fcf'] = round(data.fcf[-1], 2)
    if data.equity and data.equity[-1]:
        metrics['latest_equity'] = round(data.equity[-1], 2)
    if data.total_debt and data.total_debt[-1]:
        metrics['latest_debt'] = round(data.total_debt[-1], 2)
    if data.cash and data.cash[-1]:
        metrics['latest_cash'] = round(data.cash[-1], 2)
    if data.total_debt and data.cash:
        net_debt = (data.total_debt[-1] or 0) - (data.cash[-1] or 0)
        metrics['latest_net_debt'] = round(net_debt, 2)
    if data.shares_outstanding and data.shares_outstanding[-1]:
        metrics['latest_shares'] = round(data.shares_outstanding[-1], 2)
    
    # Margins
    margins = {'gross_margin': [], 'operating_margin': [], 'net_margin': []}
    for i in range(n):
        rev = data.revenue[i] if i < len(data.revenue) else None
        if rev and rev > 0:
            if data.gross_profit and i < len(data.gross_profit) and data.gross_profit[i]:
                margins['gross_margin'].append(data.gross_profit[i] / rev * 100)
            if data.operating_income and i < len(data.operating_income) and data.operating_income[i]:
                margins['operating_margin'].append(data.operating_income[i] / rev * 100)
            if data.net_income and i < len(data.net_income) and data.net_income[i]:
                margins['net_margin'].append(data.net_income[i] / rev * 100)
    
    for key, vals in margins.items():
        if vals:
            metrics[f'avg_{key}'] = round(sum(vals) / len(vals), 2)
            metrics[f'latest_{key}'] = round(vals[-1], 2)
    
    return metrics


def _prepare_chart_data(data: CompanyData, metrics: Dict) -> Dict[str, List]:
    """Prepare chart data"""
    years = data.fiscal_years
    n = len(years)
    
    # YoY growth
    revenue_growth = []
    for i in range(1, n):
        if data.revenue[i] and data.revenue[i-1] and data.revenue[i-1] > 0:
            growth = (data.revenue[i] - data.revenue[i-1]) / data.revenue[i-1] * 100
            revenue_growth.append(round(growth, 2))
    
    # Margin percentages
    gross_margin_pct = []
    operating_margin_pct = []
    net_margin_pct = []
    
    for i in range(n):
        rev = data.revenue[i] if i < len(data.revenue) else None
        if rev and rev > 0:
            if data.gross_profit and i < len(data.gross_profit) and data.gross_profit[i]:
                gross_margin_pct.append(round(data.gross_profit[i] / rev * 100, 2))
            else:
                gross_margin_pct.append(0)
            
            if data.operating_income and i < len(data.operating_income) and data.operating_income[i]:
                operating_margin_pct.append(round(data.operating_income[i] / rev * 100, 2))
            else:
                operating_margin_pct.append(0)
            
            if data.net_income and i < len(data.net_income) and data.net_income[i]:
                net_margin_pct.append(round(data.net_income[i] / rev * 100, 2))
            else:
                net_margin_pct.append(0)
    
    return {
        'timeline': years,
        'revenue': data.revenue,
        'net_income': data.net_income,
        'fcf': data.fcf,
        'gross_margin': gross_margin_pct,
        'operating_margin': operating_margin_pct,
        'net_margin': net_margin_pct,
        'revenue_growth': revenue_growth,
    }


def _generate_preview(data: CompanyData, metrics: Dict) -> str:
    """Generate data preview string"""
    lines = []
    lines.append("\n" + "=" * 70)
    lines.append("DATA PREVIEW")
    lines.append("=" * 70)
    lines.append(f"\n{'Year':<6} {'Revenue':>12} {'Net Inc':>12} {'FCF':>12} {'Net Mgn':>10}")
    lines.append("-" * 55)
    
    for i, year in enumerate(data.fiscal_years):
        rev = f"{data.revenue[i]:>12,.0f}" if data.revenue[i] else f"{'N/A':>12}"
        ni = f"{data.net_income[i]:>12,.0f}" if data.net_income[i] else f"{'N/A':>12}"
        fcf_val = f"{data.fcf[i]:>12,.0f}" if i < len(data.fcf) and data.fcf[i] else f"{'N/A':>12}"
        
        # Calculate net margin
        if data.revenue[i] and data.net_income[i] and data.revenue[i] > 0:
            nm = f"{data.net_income[i] / data.revenue[i] * 100:>9.1f}%"
        else:
            nm = f"{'N/A':>10}"
        
        lines.append(f"{year:<6} {rev} {ni} {fcf_val} {nm}")
    
    return "\n".join(lines)


@tool
def input_financial_data(
    data_input: str,
    company_name: str = "",
    ticker: str = "",
    data_source: str = "manual"
) -> str:
    """
    Parse financial data from various formats and prepare for analysis.
    
    **IMPORTANT**: This tool handles data input when WRDS automation is not available.
    It accepts data in multiple formats and automatically parses it.
    
    Args:
        data_input: Financial data in CSV, TSV, or JSON format.
            - CSV: Comma-separated values
            - TSV: Tab-separated values (common in WRDS exports)
            - JSON: Array of objects
            
            Example CSV format:
            Year,Revenue,NetIncome,FCF,GrossProfit
            2020,156598,4233,8563,27878
            2021,216142,2720,4521,28098
            
            Example JSON format:
            [{"year":2020,"revenue":156598,"net_income":4233},...]
            
        company_name: Name of the company (optional, extracted from data if not provided)
        ticker: Stock ticker symbol (optional)
        data_source: Source of data ("wrds", "bloomberg", "manual", "other")
    
    Returns:
        Parsed financial data with metrics and chart data ready for visualization
    
    Example:
        input_financial_data(
            data_input="Year,Revenue,NetIncome,FCF\\n2020,156598,4233,8563\\n2021,216142,2720,4521",
            company_name="BYD Company Limited",
            ticker="BYD",
            data_source="wrds"
        )
    """
    ctx = request_context.get() or new_context(method="input_financial_data")
    
    if not data_input or not data_input.strip():
        return """ERROR: No data provided.

Please provide financial data in one of these formats:

CSV FORMAT (comma-separated):
Year,Revenue,NetIncome,FCF,GrossProfit
2020,156598,4233,8563,27878
2021,216142,2720,4521,28098
2022,424061,16622,18294,72091

TSV FORMAT (tab-separated - common in WRDS exports):
Year	Revenue	NetIncome	FCF	GrossProfit
2020	156598	4233	8563	27878
2021	216142	2720	4521	28098

JSON FORMAT:
[{"year":2020,"revenue":156598,"net_income":4233,"fcf":8563},...]

WRDS EXPORT TIP:
When exporting from WRDS, choose "Tab-Separated" or "CSV" format.
The tool will automatically detect the format.
"""
    
    # Parse the input data
    result = _parse_data_input(data_input)
    
    # Override company info if provided
    if company_name:
        result.company_data.company_name = company_name
    if ticker:
        result.company_data.ticker = ticker.upper()
    
    # Build output
    output = []
    output.append("=" * 70)
    output.append("FINANCIAL DATA PARSED SUCCESSFULLY")
    output.append("=" * 70)
    
    if not result.success:
        output.append(f"\n❌ {result.message}")
        if result.warnings:
            output.append("\nWarnings:")
            for w in result.warnings:
                output.append(f"  - {w}")
        return "\n".join(output)
    
    data = result.company_data
    metrics = result.metrics
    
    output.append(f"\n✅ {result.message}")
    output.append(f"Data Source: {data_source.upper()}")
    output.append(f"Period: {data.fiscal_years[0]} - {data.fiscal_years[-1]} ({len(data.fiscal_years)} years)")
    output.append(f"Currency: {data.currency}")
    output.append(f"Unit: {data.unit}")
    
    # Key metrics
    output.append("\n" + "-" * 70)
    output.append("KEY METRICS SUMMARY")
    output.append("-" * 70)
    
    if metrics.get('revenue_cagr'):
        output.append(f"\n📈 Revenue CAGR (5Y):       {metrics['revenue_cagr']:.1f}%")
    if metrics.get('latest_revenue'):
        output.append(f"💰 Latest Revenue:          {metrics['latest_revenue']:,.2f} M {data.currency}")
    if metrics.get('latest_net_income'):
        output.append(f"📊 Latest Net Income:       {metrics['latest_net_income']:,.2f} M")
    if metrics.get('latest_fcf'):
        output.append(f"💵 Latest FCF:             {metrics['latest_fcf']:,.2f} M")
    if metrics.get('avg_gross_margin'):
        output.append(f"📉 Avg Gross Margin:        {metrics['avg_gross_margin']:.1f}%")
    if metrics.get('avg_operating_margin'):
        output.append(f"📉 Avg Operating Margin:   {metrics['avg_operating_margin']:.1f}%")
    if metrics.get('avg_net_margin'):
        output.append(f"📉 Avg Net Margin:         {metrics['avg_net_margin']:.1f}%")
    if metrics.get('latest_net_debt'):
        output.append(f"🏦 Latest Net Debt:        {metrics['latest_net_debt']:,.2f} M")
    if metrics.get('latest_shares'):
        output.append(f"📋 Shares Outstanding:    {metrics['latest_shares']:,.2f} M")
    
    # Data preview
    output.append(result.raw_data_preview)
    
    # Ready for next steps
    output.append("\n" + "-" * 70)
    output.append("READY FOR NEXT STEPS")
    output.append("-" * 70)
    output.append("\n1️⃣  Generate visualizations → Use generate_visualization")
    output.append("2️⃣  Calculate DCF valuation → Use calculate_dcf")
    output.append("3️⃣  Generate full report → Use generate_report")
    
    # Add internal data for next tools
    chart_json = json.dumps(result.chart_data)
    metrics_json = json.dumps(metrics)
    
    output.append(f"\n[INTERNAL DATA - for subsequent tools]")
    output.append(f"CHART_DATA_JSON:{chart_json}")
    output.append(f"METRICS_JSON:{metrics_json}")
    output.append(f"COMPANY_NAME:{data.company_name}")
    output.append(f"TICKER:{data.ticker}")
    
    output.append("\n" + "=" * 70)
    
    return "\n".join(output)


@tool
def generate_data_template(
    template_type: str = "csv",
    include_sample: str = "yes"
) -> str:
    """
    Generate a data input template with sample data for easy filling.
    
    Args:
        template_type: Format of template - "csv", "tsv", or "json"
        include_sample: Whether to include sample BYD data - "yes" or "no"
    
    Returns:
        A template file that users can fill in with their data
    """
    ctx = request_context.get() or new_context(method="generate_data_template")
    
    if template_type.lower() == "json":
        template = '''[
  {
    "year": 2020,
    "revenue": 156598,
    "net_income": 4233,
    "operating_income": 5485,
    "gross_profit": 27878,
    "fcf": 8563,
    "total_assets": 268822,
    "total_debt": 45678,
    "cash": 144456,
    "equity": 192755,
    "shares_outstanding": 2728
  },
  {
    "year": 2021,
    "revenue": 216142,
    "net_income": 2720,
    "operating_income": 3200,
    "gross_profit": 28098,
    "fcf": 4521,
    "total_assets": 295778,
    "total_debt": 52000,
    "cash": 158789,
    "equity": 194224,
    "shares_outstanding": 2876
  },
  {
    "year": 2022,
    "revenue": 424061,
    "net_income": 16622,
    "operating_income": 20800,
    "gross_profit": 72091,
    "fcf": 18294,
    "total_assets": 493838,
    "total_debt": 78000,
    "cash": 234331,
    "equity": 318743,
    "shares_outstanding": 2911
  },
  {
    "year": 2023,
    "revenue": 602335,
    "net_income": 28038,
    "operating_income": 32000,
    "gross_profit": 120467,
    "fcf": 32450,
    "total_assets": 689891,
    "total_debt": 89000,
    "cash": 389361,
    "equity": 511660,
    "shares_outstanding": 2956
  },
  {
    "year": 2024,
    "revenue": 760307,
    "net_income": 29041,
    "operating_income": 36000,
    "gross_profit": 159664,
    "fcf": 35218,
    "total_assets": 800000,
    "total_debt": 95000,
    "cash": 420000,
    "equity": 550000,
    "shares_outstanding": 2987
  }
]'''
    elif template_type.lower() == "tsv":
        template = """year\trevenue\tnet_income\toperating_income\tgross_profit\tfcf\ttotal_assets\ttotal_debt\tcash\tequity\tshares_outstanding
2020\t156598\t4233\t5485\t27878\t8563\t268822\t45678\t144456\t192755\t2728
2021\t216142\t2720\t3200\t28098\t4521\t295778\t52000\t158789\t194224\t2876
2022\t424061\t16622\t20800\t72091\t18294\t493838\t78000\t234331\t318743\t2911
2023\t602335\t28038\t32000\t120467\t32450\t689891\t89000\t389361\t511660\t2956
2024\t760307\t29041\t36000\t159664\t35218\t800000\t95000\t420000\t550000\t2987"""
    else:
        # CSV format
        template = """year,revenue,net_income,operating_income,gross_profit,fcf,total_assets,total_debt,cash,equity,shares_outstanding
2020,156598,4233,5485,27878,8563,268822,45678,144456,192755,2728
2021,216142,2720,3200,28098,4521,295778,52000,158789,194224,2876
2022,424061,16622,20800,72091,18294,493838,78000,234331,318743,2911
2023,602335,28038,32000,120467,32450,689891,89000,389361,511660,2956
2024,760307,29041,36000,159664,35218,800000,95000,420000,550000,2987"""
    
    if include_sample.lower() != "yes":
        # Remove sample data
        if template_type.lower() == "json":
            template = template.replace('"year": 2020,', '"year": YEAR,')
        else:
            lines = template.split('\n')
            template = lines[0] + '\nYEAR,VALUE1,VALUE2,...'
    
    output = []
    output.append("=" * 70)
    output.append("DATA INPUT TEMPLATE")
    output.append("=" * 70)
    output.append(f"\nFormat: {template_type.upper()}")
    output.append(f"\nAll values are in Million CNY")
    output.append("\n" + "-" * 70)
    output.append("\nTEMPLATE:")
    output.append("-" * 70)
    output.append(f"\n{template}")
    output.append("\n" + "-" * 70)
    output.append("\nINSTRUCTIONS:")
    output.append("-" * 70)
    output.append("""
1. Replace the sample data with your company's actual figures
2. Keep the column headers as they are (or use your own if preferred)
3. Units: All values should be in Millions (M)
4. Years: Use 4-digit fiscal years (e.g., 2020, 2021, 2022)
5. Missing values: Leave blank or use "N/A"

After filling in your data, paste the complete content back to me,
and I will automatically:
  ✅ Parse and validate your data
  ✅ Calculate financial metrics
  ✅ Generate visualizations
  ✅ Perform DCF valuation
  ✅ Create comprehensive reports
""")
    output.append("=" * 70)
    
    return "\n".join(output)
