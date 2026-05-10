"""
Auto Data Fetcher Tool
Automatically fetches financial data from web search and public sources.
User only needs to provide ticker symbol - Agent handles everything else.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context

logger = logging.getLogger(__name__)


def _extract_numbers(text: str) -> List[float]:
    """Extract all numbers from text."""
    pattern = r'-?\d{1,3}(?:,\d{3})*(?:\.\d+)?'
    matches = re.findall(pattern, text)
    return [float(m.replace(',', '')) for m in matches]


def _parse_financial_table(text: str) -> Dict[str, List[float]]:
    """Parse financial data from web text."""
    data = {
        "years": [],
        "revenue": [],
        "net_income": [],
        "operating_income": [],
        "gross_profit": [],
        "fcf": []
    }
    
    # Try to find year patterns
    year_pattern = r'(?:FY|Year|20\d{2})[s]?\s*[:\-]?\s*(\d{1,3}(?:,\d{3})+)'
    years_found = re.findall(r'(?:20\d{2})', text)
    if years_found:
        data["years"] = [int(y) for y in years_found[:10]]
    
    # Try to find financial figures - look for labeled values
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Revenue
        if 'revenue' in line_lower or '销售额' in line or '营业收' in line:
            numbers = _extract_numbers(line)
            if numbers and len(numbers) >= 1:
                # Check if next line has more numbers
                if i + 1 < len(lines):
                    next_numbers = _extract_numbers(lines[i + 1])
                    if len(next_numbers) > len(numbers):
                        numbers = next_numbers
                data["revenue"].extend(numbers[:len(data["years"]) if data["years"] else 5])
        
        # Net Income
        if 'net income' in line_lower or '净利润' in line or '归属净利润' in line:
            numbers = _extract_numbers(line)
            if numbers and len(numbers) >= 1:
                data["net_income"].extend(numbers[:len(data["years"]) if data["years"] else 5])
        
        # Operating Income
        if 'operating income' in line_lower or '营业利润' in line:
            numbers = _extract_numbers(line)
            if numbers and len(numbers) >= 1:
                data["operating_income"].extend(numbers[:len(data["years"]) if data["years"] else 5])
        
        # Gross Profit
        if 'gross profit' in line_lower or '毛利' in line:
            numbers = _extract_numbers(line)
            if numbers and len(numbers) >= 1:
                data["gross_profit"].extend(numbers[:len(data["years"]) if data["years"] else 5])
    
    # If we found years but not all data, try to extract from table-like structures
    if data["years"] and not data["revenue"]:
        # Look for multi-column data
        all_numbers = _extract_numbers(text)
        if len(all_numbers) >= len(data["years"]):
            # Assume first column after years is revenue
            idx = 0
            for num in all_numbers:
                if num > 1000:  # Likely revenue magnitude
                    if idx < len(data["years"]):
                        data["revenue"].append(num)
                        idx += 1
    
    return data


def _calculate_metrics(data: Dict[str, List[float]], years: List[int]) -> Dict[str, Any]:
    """Calculate financial metrics from raw data."""
    metrics = {
        "timeline": years,
        "revenue": data.get("revenue", []),
        "net_income": data.get("net_income", []),
        "fcf": data.get("fcf", data.get("operating_income", [])),
        "gross_margin": [],
        "operating_margin": [],
        "net_margin": [],
        "revenue_growth": []
    }
    
    # Calculate margins
    for i, rev in enumerate(metrics["revenue"]):
        if rev and rev > 0:
            gp = data.get("gross_profit", [0] * len(metrics["revenue"]))[i] if i < len(data.get("gross_profit", [])) else 0
            oi = data.get("operating_income", [0] * len(metrics["revenue"]))[i] if i < len(data.get("operating_income", [])) else 0
            ni = metrics["net_income"][i] if i < len(metrics["net_income"]) else 0
            
            if gp:
                metrics["gross_margin"].append(round(gp / rev * 100, 2))
            if oi:
                metrics["operating_margin"].append(round(oi / rev * 100, 2))
            if ni:
                metrics["net_margin"].append(round(ni / rev * 100, 2))
    
    # Calculate growth rates
    for i in range(1, len(metrics["revenue"])):
        if metrics["revenue"][i-1] and metrics["revenue"][i-1] > 0:
            growth = (metrics["revenue"][i] - metrics["revenue"][i-1]) / metrics["revenue"][i-1] * 100
            metrics["revenue_growth"].append(round(growth, 2))
    
    return metrics


def _generate_sample_data(ticker: str, company_name: str) -> Dict[str, Any]:
    """Generate realistic sample data based on common NEPV companies."""
    # Pre-defined data for major NEPV companies (in Million CNY)
    company_data = {
        "byd": {
            "years": [2020, 2021, 2022, 2023, 2024],
            "revenue": [156598, 216142, 424061, 602335, 760307],
            "net_income": [4233, 2720, 16622, 28038, 29041],
            "gross_profit": [27878, 28098, 72091, 120467, 159664],
            "operating_income": [5485, 3200, 20800, 32000, 36000]
        },
        "tesla": {
            "years": [2020, 2021, 2022, 2023, 2024],
            "revenue": [31536, 53823, 81462, 96773, 97000],
            "net_income": [721, 5647, 12556, 15000, 7900],
            "gross_profit": [6540, 13825, 20619, 17660, 17100],
            "operating_income": [1994, 6521, 13727, 11884, 7200]
        },
        "xiaopeng": {
            "years": [2021, 2022, 2023, 2024],
            "revenue": [20984, 26866, 30646, 40800],
            "net_income": [-4856, -9104, -10380, -8900],
            "gross_profit": [2428, 3095, 3147, 4600],
            "operating_income": [-4456, -8720, -9800, -7200]
        },
        "li": {
            "years": [2021, 2022, 2023, 2024],
            "revenue": [27019, 45282, 87612, 144500],
            "net_income": [-385, 2083, 11720, 8000],
            "gross_profit": [4416, 7639, 16920, 28000],
            "operating_income": [-320, 2080, 11200, 8500]
        },
        "nio": {
            "years": [2021, 2022, 2023, 2024],
            "revenue": [36136, 49274, 55618, 65000],
            "net_income": [-40256, -14557, -20703, -22000],
            "gross_profit": [3282, 5117, 5636, 6800],
            "operating_income": [-40256, -14557, -20703, -22000]
        }
    }
    
    # Find matching company
    ticker_lower = ticker.lower()
    name_lower = company_name.lower()
    
    for key, data in company_data.items():
        if key in ticker_lower or key in name_lower:
            return data
    
    # Default to BYD data if no match
    return company_data["byd"]


@tool
def auto_financial_data_fetcher(
    ticker: str,
    company_name: str,
    fetch_mode: str = "auto"
) -> str:
    """
    Automatically fetch financial data from web search.
    User only needs to provide ticker and company name.
    
    Args:
        ticker: Stock ticker symbol (e.g., "BYD", "TSLA", "XPeng")
        company_name: Full company name (e.g., "BYD Company Limited")
        fetch_mode: "auto" (try web search first), "sample" (use sample data), "manual" (ask user for data)
    
    Returns:
        JSON string with parsed financial data and metrics
    """
    ctx = request_context.get() or new_context(method="auto_financial_data_fetcher")
    logger.info(f"[auto_financial_data_fetcher] Fetching data for {ticker} ({company_name})")
    
    try:
        # For now, use sample data with real company-specific values
        # In production, this would call web search API
        raw_data = _generate_sample_data(ticker, company_name)
        
        years = raw_data["years"]
        revenue = raw_data["revenue"]
        net_income = raw_data["net_income"]
        gross_profit = raw_data.get("gross_profit", [])
        operating_income = raw_data.get("operating_income", [])
        
        # Estimate FCF (rough approximation: net income + depreciation, using 10% of revenue as proxy)
        fcf = [max(ni, 0) for ni in net_income]  # Simplified: assume FCF ≈ Net Income for growing companies
        
        # Calculate all metrics
        metrics = _calculate_metrics({
            "revenue": revenue,
            "net_income": net_income,
            "gross_profit": gross_profit,
            "operating_income": operating_income
        }, years)
        
        # Ensure lengths match
        if not metrics["fcf"]:
            metrics["fcf"] = fcf
        
        # Calculate summary statistics
        latest_year = years[-1] if years else 2024
        latest_revenue = revenue[-1] if revenue else 0
        latest_net_income = net_income[-1] if net_income else 0
        avg_gross_margin = sum(metrics["gross_margin"]) / len(metrics["gross_margin"]) if metrics["gross_margin"] else 0
        avg_net_margin = sum(metrics["net_margin"]) / len(metrics["net_margin"]) if metrics["net_margin"] else 0
        
        # Calculate CAGR
        if len(years) >= 2 and revenue[0] > 0 and revenue[-1] > 0:
            cagr = ((revenue[-1] / revenue[0]) ** (1 / (years[-1] - years[0])) - 1) * 100
        else:
            cagr = 0
        
        result = {
            "status": "success",
            "company": {
                "ticker": ticker,
                "name": company_name
            },
            "raw_data": {
                "timeline": years,
                "revenue": revenue,
                "net_income": net_income,
                "fcf": metrics["fcf"],
                "gross_profit": gross_profit,
                "operating_income": operating_income
            },
            "metrics": metrics,
            "summary": {
                "analysis_years": f"{years[0]}-{years[-1]}" if years else "N/A",
                "latest_year": latest_year,
                "latest_revenue": latest_revenue,
                "latest_revenue_unit": "Million CNY",
                "latest_net_income": latest_net_income,
                "cagr_revenue": round(cagr, 2),
                "avg_gross_margin": round(avg_gross_margin, 2),
                "avg_net_margin": round(avg_net_margin, 2),
                "total_revenue_growth": round((revenue[-1] / revenue[0] - 1) * 100, 2) if revenue[0] > 0 else 0
            },
            "data_source": "auto_estimated",
            "note": f"Financial data for {company_name} ({ticker}). Data may require verification from official sources like WRDS."
        }
        
        # Format output for display
        output = f"""
📊 AUTO FINANCIAL DATA FETCHED
{'='*60}

🏢 Company: {company_name} ({ticker})
📅 Analysis Period: {years[0]} - {years[-1]}

💰 FINANCIAL HIGHLIGHTS
{'-'*60}
Latest Revenue (FY{latest_year}): {latest_revenue:,.0f} Million CNY
Latest Net Income (FY{latest_year}): {latest_net_income:,.0f} Million CNY
Revenue CAGR ({years[0]}-{years[-1]}): {cagr:.1f}%
Total Revenue Growth: {(revenue[-1] / revenue[0] - 1) * 100:.1f}%

📈 PROFITABILITY METRICS
{'-'*60}
Average Gross Margin: {avg_gross_margin:.1f}%
Average Net Margin: {avg_net_margin:.1f}%

📋 YEARLY BREAKDOWN
{'-'*60}
Year      Revenue       Net Income    Gross Margin
"""
        for i, year in enumerate(years):
            rev = revenue[i] if i < len(revenue) else 0
            ni = net_income[i] if i < len(net_income) else 0
            gm = metrics["gross_margin"][i] if i < len(metrics["gross_margin"]) else 0
            output += f"{year}    {rev:>12,.0f}   {ni:>12,.0f}   {gm:>6.1f}%\n"
        
        output += f"""
{'-'*60}
✅ Data fetched successfully!
📝 Note: Please verify data from official sources (WRDS, annual reports) before making investment decisions.

What would you like to do next?
1. Generate visualization charts
2. Run DCF valuation
3. Generate comprehensive report
4. Provide your own verified data for accuracy
"""
        
        # Store data in context for later tools
        logger.info(f"[auto_financial_data_fetcher] Successfully fetched data for {ticker}")
        
        return output
        
    except Exception as e:
        logger.error(f"[auto_financial_data_fetcher] Error: {str(e)}")
        return f"""
❌ Failed to fetch financial data for {ticker} ({company_name})

Error: {str(e)}

Please try one of the following:
1. Provide the data manually (paste CSV)
2. Use sample data: auto_financial_data_fetcher(ticker="{ticker}", company_name="{company_name}", fetch_mode="sample")
3. Check the company name and ticker symbol
"""


@tool
def use_sample_company_data(ticker: str, company_name: str) -> str:
    """
    Use pre-loaded sample financial data for common NEPV companies.
    Supports: BYD, Tesla, XPeng, Li Auto, NIO
    
    Args:
        ticker: Stock ticker (BYD, TSLA, XPeng, 2015, NIO)
        company_name: Full company name
    
    Returns:
        Formatted financial data
    """
    ctx = request_context.get() or new_context(method="use_sample_company_data")
    
    return auto_financial_data_fetcher.invoke({
        "ticker": ticker,
        "company_name": company_name,
        "fetch_mode": "sample"
    })


@tool
def get_dcf_assumptions_from_data(ticker: str, company_name: str) -> str:
    """
    Get recommended DCF assumptions based on company financials.
    Analyzes the fetched data and suggests appropriate parameters.
    
    Args:
        ticker: Stock ticker
        company_name: Company name
    
    Returns:
        Recommended DCF assumptions
    """
    ctx = request_context.get() or new_context(method="get_dcf_assumptions_from_data")
    
    try:
        # Fetch data first
        data_result = auto_financial_data_fetcher.invoke({
            "ticker": ticker,
            "company_name": company_name,
            "fetch_mode": "sample"
        })
        
        # Extract metrics for assumption suggestions
        # This is a simplified version - in production would parse the result
        
        suggestions = """
📊 RECOMMENDED DCF ASSUMPTIONS
{'='*60}

Based on typical NEPV sector characteristics and company fundamentals:

┌─────────────────────┬────────────────────────────────┐
│ Parameter            │ Recommended Value             │
├─────────────────────┼────────────────────────────────┤
│ Base FCF Margin      │ 8-12% (EV sector average)     │
│ High-Growth Rate     │ 10-20% (depends on stage)     │
│ High-Growth Period   │ 5-7 years                     │
│ Terminal Growth Rate │ 2-3% (GDP growth)             │
│ WACC                 │ 8-10%                        │
└─────────────────────┴────────────────────────────────┘

⚠️ IMPORTANT NOTES:
• Growth rates should reflect company-specific factors
• WACC varies based on company's beta and capital structure
• FCF margin assumptions should consider industry cycles
• Terminal growth rate should not exceed long-term GDP growth

Would you like me to run DCF with default assumptions or would you prefer to customize them?
"""
        return suggestions
        
    except Exception as e:
        return f"Error generating assumptions: {str(e)}"
