"""
Automated WRDS Data Fetcher Tool
Directly connects to WRDS and fetches financial data for NEPV analysis.
No manual steps required - the Agent does everything automatically.
"""
import json
import warnings
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context

# Suppress wrds connection warnings
warnings.filterwarnings('ignore')


@dataclass
class WRDSFinancialData:
    """Container for WRDS-fetched financial data"""
    company_name: str
    ticker: str
    gvkey: str
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
    capex: List[Optional[float]]
    depreciation: List[Optional[float]]
    fcf: List[Optional[float]]
    currency: str = "CNY"
    source: str = "WRDS Compustat"


@dataclass
class FetchResult:
    """Result of WRDS data fetch operation"""
    success: bool
    data: Optional[WRDSFinancialData]
    metrics: Dict[str, Any]
    chart_data: Dict[str, List[Any]]
    message: str
    error: Optional[str] = None


def _connect_and_fetch_wrds(
    username: str,
    password: str,
    ticker: str,
    start_year: int = 2019,
    end_year: int = 2024
) -> FetchResult:
    """
    Connect to WRDS and fetch financial data for the specified company.
    Uses the wrds Python package for direct database access.
    """
    try:
        import wrds
    except ImportError:
        return FetchResult(
            success=False,
            data=None,
            metrics={},
            chart_data={},
            message="WRDS package not installed",
            error="Please install wrds: pip install wrds"
        )
    
    try:
        # Connect to WRDS
        db = wrds.Connection(wrds_username=username, wrds_password=password)
        
        # Query Compustat Fundamentals Annual
        # This is the standard WRDS query for US/China listed companies
        query = f"""
        SELECT 
            gvkey, fyear, tic, conm,
            -- Income Statement
            revt,    -- Revenue (Total)
            ni,      -- Net Income
            oibdp,   -- Operating Income Before Depreciation
            gp,      -- Gross Profit
            
            -- Balance Sheet
            at,      -- Total Assets
            lt,      -- Total Liabilities
            dltt,    -- Total Long-Term Debt
            dlc,     -- Total Current Debt
            che,     -- Cash and Short-Term Investments
            seq,     -- Total Stockholders' Equity
            csho,    -- Common Shares Outstanding
            
            -- Cash Flow
            capx,    -- Capital Expenditures
            dp,      -- Depreciation and Amortization
            ocf      -- Operating Cash Flow
        FROM comp.funda
        WHERE tic = '{ticker.upper()}'
          AND fyear >= {start_year}
          AND fyear <= {end_year}
          AND consol = 'C'
          AND popsrc = 'I'
          AND datadate IS NOT NULL
        ORDER BY fyear
        """
        
        df = db.raw_sql(query)
        db.close()
        
        if df is None or len(df) == 0:
            return FetchResult(
                success=False,
                data=None,
                metrics={},
                chart_data={},
                message=f"No data found for ticker: {ticker}",
                error="Company may not be in Compustat database or ticker is incorrect"
            )
        
        # Parse results
        company_name = df['conm'].iloc[0] if 'conm' in df.columns else ticker.upper()
        gvkey = str(df['gvkey'].iloc[0]) if 'gvkey' in df.columns else ""
        
        fiscal_years = df['fyear'].tolist() if 'fyear' in df.columns else []
        revenue = df['revt'].tolist() if 'revt' in df.columns else []
        net_income = df['ni'].tolist() if 'ni' in df.columns else []
        operating_income = df['oibdp'].tolist() if 'oibdp' in df.columns else []
        gross_profit = df['gp'].tolist() if 'gp' in df.columns else []
        total_assets = df['at'].tolist() if 'at' in df.columns else []
        total_liabilities = df['lt'].tolist() if 'lt' in df.columns else []
        total_debt = []
        for i in range(len(df)):
            dltt = df['dltt'].iloc[i] if 'dltt' in df.columns and pd.notna(df['dltt'].iloc[i]) else 0
            dlc = df['dlc'].iloc[i] if 'dlc' in df.columns and pd.notna(df['dlc'].iloc[i]) else 0
            total_debt.append(float(dltt + dlc))
        cash = df['che'].tolist() if 'che' in df.columns else []
        equity = df['seq'].tolist() if 'seq' in df.columns else []
        shares_outstanding = df['csho'].tolist() if 'csho' in df.columns else []
        capex = df['capx'].tolist() if 'capx' in df.columns else []
        depreciation = df['dp'].tolist() if 'dp' in df.columns else []
        
        # Calculate FCF (Operating Cash Flow - CapEx approximation)
        fcf = []
        for i in range(len(df)):
            if 'ocf' in df.columns and pd.notna(df['ocf'].iloc[i]):
                cap = capex[i] if i < len(capex) and capex[i] else 0
                fcf.append(float(df['ocf'].iloc[i]) - float(cap))
            else:
                fcf.append(None)
        
        # Create data object
        financial_data = WRDSFinancialData(
            company_name=company_name,
            ticker=ticker.upper(),
            gvkey=gvkey,
            fiscal_years=fiscal_years,
            revenue=[float(r) if r is not None else None for r in revenue],
            net_income=[float(n) if n is not None else None for n in net_income],
            operating_income=[float(o) if o is not None else None for o in operating_income],
            gross_profit=[float(g) if g is not None else None for g in gross_profit],
            total_assets=[float(a) if a is not None else None for a in total_assets],
            total_debt=[float(d) if d is not None else None for d in total_debt],
            cash=[float(c) if c is not None else None for c in cash],
            equity=[float(e) if e is not None else None for e in equity],
            shares_outstanding=[float(s) if s is not None else None for s in shares_outstanding],
            capex=[float(c) if c is not None else None for c in capex],
            depreciation=[float(d) if d is not None else None for d in depreciation],
            fcf=[float(f) if f is not None else None for f in fcf],
            currency="CNY",
            source="WRDS Compustat"
        )
        
        # Calculate metrics
        metrics = _calculate_metrics(financial_data)
        
        # Prepare chart data
        chart_data = _prepare_chart_data(financial_data, metrics)
        
        return FetchResult(
            success=True,
            data=financial_data,
            metrics=metrics,
            chart_data=chart_data,
            message=f"Successfully fetched {len(fiscal_years)} years of data for {company_name}"
        )
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle specific WRDS errors
        if "authentication" in error_msg.lower() or "login" in error_msg.lower():
            return FetchResult(
                success=False,
                data=None,
                metrics={},
                chart_data={},
                message="WRDS authentication failed",
                error="Invalid username or password. Please check your WRDS credentials."
            )
        elif "connection" in error_msg.lower():
            return FetchResult(
                success=False,
                data=None,
                metrics={},
                chart_data={},
                message="Could not connect to WRDS",
                error="Network error or WRDS server unavailable. Please try again later."
            )
        else:
            return FetchResult(
                success=False,
                data=None,
                metrics={},
                chart_data={},
                message=f"Error fetching data: {error_msg}",
                error=error_msg
            )


def _calculate_metrics(data: WRDSFinancialData) -> Dict[str, Any]:
    """Calculate financial metrics from raw data"""
    metrics = {}
    
    n = len(data.fiscal_years)
    
    # Revenue CAGR
    if n >= 2:
        rev_values = [r for r in data.revenue if r is not None and r > 0]
        if len(rev_values) >= 2:
            cagr = ((rev_values[-1] / rev_values[0]) ** (1 / (n - 1)) - 1) * 100
            metrics['revenue_cagr'] = round(cagr, 2)
            metrics['revenue_growth_years'] = n - 1
    
    # Latest values
    if data.revenue and data.revenue[-1]:
        metrics['latest_revenue'] = round(data.revenue[-1], 2)
    if data.net_income and data.net_income[-1]:
        metrics['latest_net_income'] = round(data.net_income[-1], 2)
    if data.fcf and data.fcf[-1]:
        metrics['latest_fcf'] = round(data.fcf[-1], 2)
    if data.equity and data.equity[-1]:
        metrics['latest_equity'] = round(data.equity[-1], 2)
    if data.total_assets and data.total_assets[-1]:
        metrics['latest_assets'] = round(data.total_assets[-1], 2)
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


def _prepare_chart_data(data: WRDSFinancialData, metrics: Dict) -> Dict[str, List]:
    """Prepare chart data for visualization"""
    # YoY revenue growth
    revenue_growth = []
    for i in range(1, len(data.revenue)):
        if data.revenue[i] and data.revenue[i-1] and data.revenue[i-1] > 0:
            growth = (data.revenue[i] - data.revenue[i-1]) / data.revenue[i-1] * 100
            revenue_growth.append(round(growth, 2))
    
    # Margin percentages
    gross_margin_pct = []
    operating_margin_pct = []
    net_margin_pct = []
    
    for i in range(len(data.fiscal_years)):
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
        'timeline': data.fiscal_years,
        'revenue': data.revenue,
        'net_income': data.net_income,
        'fcf': data.fcf,
        'gross_margin': gross_margin_pct,
        'operating_margin': operating_margin_pct,
        'net_margin': net_margin_pct,
        'revenue_growth': revenue_growth,
    }


def _format_fetch_result(result: FetchResult) -> str:
    """Format the fetch result for display"""
    output = []
    output.append("=" * 70)
    output.append("WRDS DATA FETCH COMPLETE")
    output.append("=" * 70)
    
    if not result.success:
        output.append(f"\n❌ {result.message}")
        output.append(f"\nError: {result.error}")
        output.append("\n" + "=" * 70)
        return "\n".join(output)
    
    data = result.data
    metrics = result.metrics
    
    output.append(f"\n✅ {result.message}")
    output.append(f"Source: {data.source}")
    
    # Summary
    output.append("\n" + "-" * 70)
    output.append("FINANCIAL SUMMARY")
    output.append("-" * 70)
    output.append(f"\nCompany:    {data.company_name}")
    output.append(f"Ticker:     {data.ticker}")
    output.append(f"Period:     {data.fiscal_years[0]} - {data.fiscal_years[-1]} ({len(data.fiscal_years)} years)")
    output.append(f"Currency:   {data.currency} Million")
    
    # Key metrics
    output.append("\n" + "-" * 70)
    output.append("KEY METRICS")
    output.append("-" * 70)
    
    if metrics.get('revenue_cagr'):
        output.append(f"\nRevenue CAGR (5Y):       {metrics['revenue_cagr']:.1f}%")
    if metrics.get('latest_revenue'):
        output.append(f"Latest Revenue:          {metrics['latest_revenue']:,.2f} M")
    if metrics.get('latest_net_income'):
        output.append(f"Latest Net Income:       {metrics['latest_net_income']:,.2f} M")
    if metrics.get('latest_fcf'):
        output.append(f"Latest FCF:             {metrics['latest_fcf']:,.2f} M")
    if metrics.get('avg_gross_margin'):
        output.append(f"Avg Gross Margin:        {metrics['avg_gross_margin']:.1f}%")
    if metrics.get('avg_operating_margin'):
        output.append(f"Avg Operating Margin:    {metrics['avg_operating_margin']:.1f}%")
    if metrics.get('avg_net_margin'):
        output.append(f"Avg Net Margin:          {metrics['avg_net_margin']:.1f}%")
    if metrics.get('latest_net_debt'):
        output.append(f"Latest Net Debt:         {metrics['latest_net_debt']:,.2f} M")
    if metrics.get('latest_shares'):
        output.append(f"Latest Shares Out:       {metrics['latest_shares']:,.2f} M")
    
    # Historical table
    output.append("\n" + "-" * 70)
    output.append("HISTORICAL DATA")
    output.append("-" * 70)
    output.append(f"\n{'Year':<6} {'Revenue':>12} {'Net Inc':>12} {'FCF':>12} {'Net Mgn':>10}")
    output.append("-" * 55)
    
    for i, year in enumerate(data.fiscal_years):
        rev = f"{data.revenue[i]:>12,.0f}" if data.revenue[i] else f"{'N/A':>12}"
        ni = f"{data.net_income[i]:>12,.0f}" if data.net_income[i] else f"{'N/A':>12}"
        fcf_val = f"{data.fcf[i]:>12,.0f}" if i < len(data.fcf) and data.fcf[i] else f"{'N/A':>12}"
        nm = f"{metrics.get('net_margin', {}).get(i, 'N/A') if isinstance(metrics.get('net_margin'), list) else 'N/A':>10}"
        
        # Calculate net margin for this year
        if data.revenue[i] and data.net_income[i] and data.revenue[i] > 0:
            nm_val = data.net_income[i] / data.revenue[i] * 100
            nm = f"{nm_val:>10.1f}%"
        else:
            nm = f"{'N/A':>10}"
        
        output.append(f"{year:<6} {rev} {ni} {fcf_val} {nm}")
    
    # Chart data ready
    output.append("\n" + "-" * 70)
    output.append("VISUALIZATION DATA READY")
    output.append("-" * 70)
    output.append("\nChart data has been prepared for visualization:")
    output.append("  • Revenue & Net Income Trend")
    output.append("  • Free Cash Flow Analysis")
    output.append("  • Margin Analysis (Gross, Operating, Net)")
    output.append("  • Year-over-Year Growth Rates")
    
    output.append("\n" + "=" * 70)
    output.append("READY FOR: Visualization → DCF Valuation → Report Generation")
    output.append("=" * 70)
    
    return "\n".join(output)


# Need pandas for data manipulation
import pandas as pd


@tool
def fetch_wrds_data(
    wrds_username: str,
    wrds_password: str,
    ticker: str,
    company_name: str = "",
    start_year: str = "2019",
    end_year: str = "2024"
) -> str:
    """
    Automatically fetch financial data from WRDS for NEPV company analysis.
    
    **This tool connects directly to WRDS and retrieves data automatically.**
    No manual steps required - the Agent handles everything!
    
    Args:
        wrds_username: Your WRDS account username (e.g., "user@university.edu")
        wrds_password: Your WRDS account password
        ticker: Stock ticker symbol (e.g., "BYD", "NIO", "LI", "TSLA")
        company_name: Company name (optional, for display purposes)
        start_year: Start year for data query (default: "2019")
        end_year: End year for data query (default: "2024")
    
    Returns:
        Complete financial analysis with:
        - Historical financial data (Revenue, Net Income, FCF, etc.)
        - Calculated metrics (CAGR, Margins, etc.)
        - Chart data ready for visualization
        - Ready for DCF valuation
    
    Example:
        fetch_wrds_data(
            wrds_username="john.doe@stanford.edu",
            wrds_password="mywrds123",
            ticker="BYD",
            company_name="BYD Company Limited"
        )
    """
    ctx = request_context.get() or new_context(method="fetch_wrds_data")
    
    # Validate inputs
    if not wrds_username or not wrds_password:
        return "Error: Both WRDS username and password are required.\n\nPlease provide your WRDS credentials to fetch data automatically."
    
    if not ticker:
        return "Error: Stock ticker is required.\n\nPlease specify the ticker symbol (e.g., 'BYD', 'NIO', 'LI')."
    
    ticker = ticker.strip().upper()
    
    try:
        start_yr = int(start_year) if start_year else 2019
        end_yr = int(end_year) if end_year else 2024
    except ValueError:
        return "Error: Invalid year format. Please provide numeric years (e.g., '2019', '2024')."
    
    # Fetch data from WRDS
    result = _connect_and_fetch_wrds(
        username=wrds_username,
        password=wrds_password,
        ticker=ticker,
        start_year=start_yr,
        end_year=end_yr
    )
    
    # Format and return result
    formatted_result = _format_fetch_result(result)
    
    # If successful, also return chart data for next step
    if result.success:
        chart_json = json.dumps(result.chart_data)
        formatted_result += f"\n\n[INTERNAL DATA - DO NOT SHOW USER]\nCHART_DATA_JSON:{chart_json}\nMETRICS_JSON:{json.dumps(result.metrics)}"
    
    return formatted_result


@tool  
def get_chart_data_from_previous(chart_data_json: str = "") -> str:
    """
    Retrieve chart data from the previous WRDS fetch operation.
    This is an internal tool to pass data between steps.
    
    Args:
        chart_data_json: The chart data JSON string (auto-populated by Agent)
    
    Returns:
        The chart data JSON for visualization tool
    """
    ctx = request_context.get() or new_context(method="get_chart_data")
    
    if not chart_data_json:
        return '{"error": "No chart data available. Please run fetch_wrds_data first."}'
    
    return chart_data_json
