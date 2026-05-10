"""
WRDS CSV Parser Tool
Parses financial data exported from WRDS for NEPV company analysis.
"""
import csv
import io
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


@dataclass
class FinancialData:
    """Structured financial data container"""
    company_name: str
    fiscal_year: int
    revenue: Optional[float] = None
    revenue_growth: Optional[float] = None
    gross_profit: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_income: Optional[float] = None
    operating_margin: Optional[float] = None
    net_income: Optional[float] = None
    net_margin: Optional[float] = None
    fcf: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    net_debt: Optional[float] = None
    total_equity: Optional[float] = None
    shares_outstanding: Optional[float] = None
    capex: Optional[float] = None
    depreciation: Optional[float] = None
    working_capital_change: Optional[float] = None


@dataclass
class ParsedFinancials:
    """Complete parsed financial statement data"""
    company_name: str
    currency: str
    unit: str
    years: List[int]
    annual_data: List[FinancialData]
    summary: Dict[str, Any]
    warnings: List[str]


def _detect_currency_and_unit(header: str) -> tuple[str, str]:
    """Detect currency and unit from header string"""
    header_lower = header.lower()
    
    # Currency detection
    currency = "CNY"
    if "usd" in header_lower or "$" in header:
        currency = "USD"
    elif "eur" in header_lower or "€" in header:
        currency = "EUR"
    
    # Unit detection
    unit = "Million"
    if "billion" in header_lower or "bn" in header_lower:
        unit = "Billion"
    elif "thousand" in header_lower or "k" in header_lower:
        unit = "Thousand"
    
    return currency, unit


def _parse_numeric(value: str) -> Optional[float]:
    """Parse numeric value from string, handling various formats"""
    if not value or value.strip() == "" or value.strip() == "-" or value.strip() == "N/A":
        return None
    
    # Remove currency symbols and thousands separators
    cleaned = value.strip()
    cleaned = re.sub(r'[¥$€£,]', '', cleaned)
    
    # Handle parentheses for negative numbers
    if cleaned.startswith('(') and cleaned.endswith(')'):
        cleaned = '-' + cleaned[1:-1]
    
    try:
        return float(cleaned)
    except ValueError:
        return None


def _identify_financial_metric(label: str) -> Optional[str]:
    """Identify financial metric from column label"""
    label_lower = label.lower().strip()
    
    # Revenue metrics
    if 'revenue' in label_lower or 'sales' in label_lower or 'net sales' in label_lower:
        if 'growth' in label_lower:
            return 'revenue_growth'
        return 'revenue'
    
    # Profit margins
    if 'gross profit' in label_lower:
        if 'margin' in label_lower:
            return 'gross_margin'
        return 'gross_profit'
    
    if 'operating income' in label_lower or 'operating profit' in label_lower or 'ebit' in label_lower:
        if 'margin' in label_lower:
            return 'operating_margin'
        return 'operating_income'
    
    if 'net income' in label_lower or 'net profit' in label_lower or 'net earnings' in label_lower:
        if 'margin' in label_lower:
            return 'net_margin'
        return 'net_income'
    
    # Cash flow metrics
    if 'free cash flow' in label_lower or 'fcf' in label_lower:
        return 'fcf'
    
    if 'capex' in label_lower or 'capital expenditure' in label_lower or 'capital spending' in label_lower:
        return 'capex'
    
    if 'depreciation' in label_lower or 'd&a' in label_lower or 'dd&a' in label_lower:
        return 'depreciation'
    
    if 'working capital' in label_lower:
        return 'working_capital_change'
    
    # Balance sheet
    if 'total assets' in label_lower or 'assets' in label_lower:
        if 'net' in label_lower:
            return 'net_debt'
        return 'total_assets'
    
    if 'total liabilities' in label_lower or 'liabilities' in label_lower:
        return 'total_liabilities'
    
    if 'total equity' in label_lower or 'shareholders' in label_lower or 'equity' in label_lower:
        return 'total_equity'
    
    if 'shares outstanding' in label_lower or 'shares' in label_lower:
        return 'shares_outstanding'
    
    if 'net debt' in label_lower:
        return 'net_debt'
    
    return None


def _extract_company_name(first_row: List[str]) -> str:
    """Extract company name from the first row/column"""
    if not first_row:
        return "Unknown Company"
    
    # Join all cells in first row and extract meaningful name
    combined = ' '.join(str(cell).strip() for cell in first_row if cell.strip())
    
    # Try to extract company identifier
    patterns = [
        r'([A-Z][A-Za-z\s&]+(?:Inc\.?|Corp\.?|Ltd\.?|Limited|Co\.?|Company|Group|Holdings|Automotive|EV))',
        r'(BYD|NIO|Li Auto|Xpeng|Geely|GAC|BAIC|Changan)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return match.group(1).strip()
    
    return combined[:50] if combined else "Unknown Company"


def _parse_wrds_csv(content: str) -> ParsedFinancials:
    """Parse WRDS CSV content and extract financial data"""
    
    lines = content.strip().split('\n')
    if len(lines) < 2:
        raise ValueError("CSV file must contain at least a header row and one data row")
    
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    
    # Detect currency and unit from header
    header = ','.join(rows[0]) if rows else ""
    currency, unit = _detect_currency_and_unit(header)
    
    # Extract company name
    company_name = _extract_company_name(rows[0]) if rows else "Unknown"
    
    # Parse header to identify columns
    headers = rows[0]
    metric_map: Dict[int, str] = {}  # column_index -> metric_name
    year_columns: Dict[int, int] = {}  # column_index -> year
    
    for idx, col in enumerate(headers):
        col_stripped = col.strip()
        
        # Check if this is a year column (numeric values like 2020, 2021, etc.)
        if re.match(r'^\d{4}$', col_stripped):
            year_columns[idx] = int(col_stripped)
            continue
        
        # Check if this is a metric column
        metric = _identify_financial_metric(col_stripped)
        if metric:
            metric_map[idx] = metric
    
    # Parse data rows
    annual_data: List[FinancialData] = []
    warnings: List[str] = []
    
    for row_idx, row in enumerate(rows[1:], start=2):
        if len(row) < 2 or not any(row):
            continue
        
        # Find the year for this row
        row_year = None
        for col_idx, year in year_columns.items():
            if col_idx < len(row):
                val = _parse_numeric(row[col_idx])
                if val is not None:
                    row_year = year
                    break
        
        if row_year is None:
            # Try to find year in first column
            for col_idx, col in enumerate(row[:min(3, len(row))]):
                if re.match(r'^\d{4}$', col.strip()):
                    row_year = int(col.strip())
                    break
        
        if row_year is None:
            # Infer year from row position (assuming sequential years starting from earliest)
            if not year_columns:
                continue
            sorted_years = sorted(year_columns.values())
            if sorted_years:
                row_year = sorted_years[0] + (row_idx - 2)
        
        # Create FinancialData object for this row
        data = FinancialData(company_name=company_name, fiscal_year=row_year or 0)
        
        # Extract metrics from this row
        for col_idx, metric in metric_map.items():
            if col_idx < len(row):
                value = _parse_numeric(row[col_idx])
                if value is not None and hasattr(data, metric):
                    setattr(data, metric, value)
        
        # Only add rows with meaningful data
        if any([data.revenue, data.net_income, data.fcf, data.total_assets]):
            annual_data.append(data)
    
    # Calculate margins and growth rates if not provided
    for i, data in enumerate(annual_data):
        if data.revenue:
            if data.gross_profit and not data.gross_margin:
                data.gross_margin = round(data.gross_profit / data.revenue * 100, 2)
            if data.operating_income and not data.operating_margin:
                data.operating_margin = round(data.operating_income / data.revenue * 100, 2)
            if data.net_income and not data.net_margin:
                data.net_margin = round(data.net_income / data.revenue * 100, 2)
        
        # Calculate YoY revenue growth
        if data.revenue and i > 0:
            prev_data = annual_data[i - 1]
            if prev_data.revenue and prev_data.revenue > 0:
                data.revenue_growth = round((data.revenue - prev_data.revenue) / prev_data.revenue * 100, 2)
        
        # Calculate FCF if not provided but components available
        if data.fcf is None and data.operating_income is not None and data.capex is not None:
            # Simplified FCF = Operating Income - Capex (ignoring tax and working capital for simplicity)
            data.fcf = data.operating_income - data.capex
    
    # Generate summary
    years = sorted([d.fiscal_year for d in annual_data if d.fiscal_year])
    summary = {
        'total_years': len(years),
        'year_range': f"{min(years)}-{max(years)}" if years else "N/A",
        'revenue_cagr': None,
        'latest_revenue': None,
        'latest_net_income': None,
        'latest_fcf': None,
        'latest_net_margin': None,
        'avg_gross_margin': None,
        'avg_operating_margin': None,
    }
    
    if len(annual_data) >= 2 and annual_data[0].revenue and annual_data[-1].revenue:
        years_count = annual_data[-1].fiscal_year - annual_data[0].fiscal_year
        if years_count > 0:
            summary['revenue_cagr'] = round(
                ((annual_data[-1].revenue / annual_data[0].revenue) ** (1 / years_count) - 1) * 100, 2
            )
    
    if annual_data:
        summary['latest_revenue'] = annual_data[-1].revenue
        summary['latest_net_income'] = annual_data[-1].net_income
        summary['latest_fcf'] = annual_data[-1].fcf
        summary['latest_net_margin'] = annual_data[-1].net_margin
        
        margins = [d.gross_margin for d in annual_data if d.gross_margin is not None]
        if margins:
            summary['avg_gross_margin'] = round(sum(margins) / len(margins), 2)
        
        op_margins = [d.operating_margin for d in annual_data if d.operating_margin is not None]
        if op_margins:
            summary['avg_operating_margin'] = round(sum(op_margins) / len(op_margins), 2)
    
    # Check for missing data warnings
    if not any(d.revenue for d in annual_data):
        warnings.append("No revenue data found in CSV")
    if not any(d.net_income for d in annual_data):
        warnings.append("No net income data found in CSV")
    if not any(d.fcf for d in annual_data):
        warnings.append("No FCF data found - DCF will use operating cash flow or estimates")
    
    return ParsedFinancials(
        company_name=company_name,
        currency=currency,
        unit=unit,
        years=years,
        annual_data=annual_data,
        summary=summary,
        warnings=warnings
    )


def _format_financials_report(parsed: ParsedFinancials) -> str:
    """Format parsed financials into a readable report"""
    
    report = []
    report.append("=" * 60)
    report.append("WRDS FINANCIAL DATA ANALYSIS REPORT")
    report.append("=" * 60)
    report.append(f"\nCompany: {parsed.company_name}")
    report.append(f"Currency: {parsed.currency}")
    report.append(f"Unit: {parsed.unit}")
    report.append(f"Period: {parsed.summary['year_range']} ({parsed.summary['total_years']} years)")
    
    report.append("\n" + "-" * 60)
    report.append("HISTORICAL SUMMARY")
    report.append("-" * 60)
    
    report.append(f"\n{'Year':<8} {'Revenue':>15} {'Growth':>10} {'Gross%':>10} {'Op%':>10} {'Net%':>10} {'FCF':>15}")
    report.append("-" * 78)
    
    for data in parsed.annual_data:
        year = str(data.fiscal_year)
        rev = f"{data.revenue:,.2f}" if data.revenue else "N/A"
        growth = f"{data.revenue_growth:.1f}%" if data.revenue_growth else "-"
        gross = f"{data.gross_margin:.1f}%" if data.gross_margin else "-"
        op = f"{data.operating_margin:.1f}%" if data.operating_margin else "-"
        net = f"{data.net_margin:.1f}%" if data.net_margin else "-"
        fcf = f"{data.fcf:,.2f}" if data.fcf else "-"
        
        report.append(f"{year:<8} {rev:>15} {growth:>10} {gross:>10} {op:>10} {net:>10} {fcf:>15}")
    
    report.append("-" * 78)
    
    # Key metrics summary
    report.append("\n" + "-" * 60)
    report.append("KEY METRICS SUMMARY")
    report.append("-" * 60)
    
    s = parsed.summary
    report.append(f"\nLatest Revenue:        {s['latest_revenue']:,.2f} {parsed.currency} {parsed.unit}")
    report.append(f"Revenue CAGR:          {s['revenue_cagr']:.2f}%" if s['revenue_cagr'] else "Revenue CAGR:          N/A")
    report.append(f"Latest Net Income:     {s['latest_net_income']:,.2f}" if s['latest_net_income'] else "Latest Net Income:     N/A")
    report.append(f"Latest FCF:            {s['latest_fcf']:,.2f}" if s['latest_fcf'] else "Latest FCF:            N/A")
    report.append(f"Latest Net Margin:     {s['latest_net_margin']:.2f}%" if s['latest_net_margin'] else "Latest Net Margin:     N/A")
    report.append(f"Average Gross Margin:  {s['avg_gross_margin']:.2f}%" if s['avg_gross_margin'] else "Average Gross Margin:  N/A")
    report.append(f"Average Op. Margin:    {s['avg_operating_margin']:.2f}%" if s['avg_operating_margin'] else "Average Op. Margin:    N/A")
    
    # Warnings
    if parsed.warnings:
        report.append("\n" + "-" * 60)
        report.append("DATA QUALITY WARNINGS")
        report.append("-" * 60)
        for warning in parsed.warnings:
            report.append(f"⚠ {warning}")
    
    report.append("\n" + "=" * 60)
    report.append("END OF ANALYSIS")
    report.append("=" * 60)
    
    return "\n".join(report)


@tool
def parse_wrds_csv(csv_content: str) -> str:
    """
    Parse a WRDS-exported CSV file containing financial data for NEPV company analysis.
    
    This tool extracts and analyzes historical financial data including:
    - Revenue and growth rates
    - Profit margins (gross, operating, net)
    - Free cash flow (FCF)
    - Key balance sheet items
    
    Args:
        csv_content: The raw CSV content as a string (from WRDS export)
    
    Returns:
        A formatted analysis report with historical summary and key metrics
    
    Example:
        User can paste WRDS CSV content directly, and this tool will:
        1. Detect company name and currency
        2. Parse financial metrics across multiple years
        3. Calculate margins and growth rates
        4. Generate a structured analysis report
    """
    ctx = request_context.get() or new_context(method="parse_wrds_csv")
    
    try:
        parsed = _parse_wrds_csv(csv_content)
        report = _format_financials_report(parsed)
        
        # Return both the formatted report and the raw data structure for further use
        return report
        
    except Exception as e:
        return f"Error parsing CSV: {str(e)}\n\nPlease ensure the CSV follows WRDS export format with year columns and metric labels."
