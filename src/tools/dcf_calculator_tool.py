"""
DCF (Discounted Cash Flow) Calculator Tool
Performs professional equity valuation using DCF methodology for NEPV companies.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


@dataclass
class DCFAssumptions:
    """User-provided DCF valuation assumptions"""
    base_revenue: float  # Latest revenue (million CNY)
    base_fcf_margin: float  # FCF margin assumption (e.g., 0.10 for 10%)
    high_growth_rate: float  # High-growth period revenue/FCF growth rate (e.g., 0.15 for 15%)
    high_growth_years: int  # Length of high-growth period (years)
    terminal_growth_rate: float  # Terminal growth rate (typically 0.02-0.03)
    wacc: float  # Weighted Average Cost of Capital (e.g., 0.10 for 10%)
    net_debt: float  # Net debt position (million CNY)
    shares_outstanding: float  # Shares outstanding (million)


@dataclass
class DCFResult:
    """DCF valuation results"""
    company_name: str
    equity_value: float  # Million CNY
    value_per_share: float  # CNY per share
    total_enterprise_value: float  # Million CNY
    high_growth_pv: float  # PV of high-growth period
    terminal_pv: float  # PV of terminal value
    high_growth_fcf: List[float]  # Projected FCFs in high-growth period
    implied_exit_multiple: float  # Implied exit EV/Revenue or EV/EBITDA multiple


def _calculate_dcf(assumptions: DCFAssumptions, company_name: str = "Company") -> DCFResult:
    """Calculate DCF valuation based on provided assumptions"""
    
    # Step 1: Project FCF for high-growth period
    high_growth_fcf = []
    current_fcf = assumptions.base_revenue * assumptions.base_fcf_margin
    current_revenue = assumptions.base_revenue
    
    for year in range(1, assumptions.high_growth_years + 1):
        # Revenue grows at high_growth_rate
        current_revenue = current_revenue * (1 + assumptions.high_growth_rate)
        # FCF margin can be assumed constant or slightly improving
        fcf = current_revenue * assumptions.base_fcf_margin
        high_growth_fcf.append(fcf)
    
    # Step 2: Calculate PV of high-growth period FCFs
    high_growth_pv = 0
    for year, fcf in enumerate(high_growth_fcf, start=1):
        discount_factor = (1 + assumptions.wacc) ** year
        pv = fcf / discount_factor
        high_growth_pv += pv
    
    # Step 3: Calculate Terminal Value (Gordon Growth Model)
    # TV = FCF_last * (1 + terminal_growth_rate) / (WACC - terminal_growth_rate)
    terminal_fcf = high_growth_fcf[-1] * (1 + assumptions.terminal_growth_rate)
    terminal_value = terminal_fcf / (assumptions.wacc - assumptions.terminal_growth_rate)
    
    # Step 4: Calculate PV of Terminal Value
    discount_factor = (1 + assumptions.wacc) ** assumptions.high_growth_years
    terminal_pv = terminal_value / discount_factor
    
    # Step 5: Calculate Enterprise Value
    total_ev = high_growth_pv + terminal_pv
    
    # Step 6: Calculate Equity Value
    # Equity Value = Enterprise Value - Net Debt
    equity_value = total_ev - assumptions.net_debt
    
    # Step 7: Calculate Value per Share
    if assumptions.shares_outstanding > 0:
        value_per_share = equity_value / assumptions.shares_outstanding
    else:
        value_per_share = 0
    
    # Step 8: Calculate implied exit multiple (EV/Revenue at end of high-growth period)
    final_revenue = current_revenue  # Revenue at end of projection period
    implied_exit_multiple = total_ev / final_revenue if final_revenue > 0 else 0
    
    return DCFResult(
        company_name=company_name,
        equity_value=round(equity_value, 2),
        value_per_share=round(value_per_share, 2),
        total_enterprise_value=round(total_ev, 2),
        high_growth_pv=round(high_growth_pv, 2),
        terminal_pv=round(terminal_pv, 2),
        high_growth_fcf=[round(f, 2) for f in high_growth_fcf],
        implied_exit_multiple=round(implied_exit_multiple, 2)
    )


def _format_dcf_report(result: DCFResult, assumptions: DCFAssumptions) -> str:
    """Format DCF results into a professional report"""
    
    report = []
    report.append("=" * 70)
    report.append("DCF VALUATION ANALYSIS REPORT")
    report.append("China New Energy Passenger Vehicle (NEPV) Sector")
    report.append("=" * 70)
    
    report.append(f"\nCompany: {result.company_name}")
    report.append(f"Report Date: Analysis based on provided assumptions")
    
    # Assumptions section
    report.append("\n" + "-" * 70)
    report.append("VALUATION ASSUMPTIONS")
    report.append("-" * 70)
    report.append(f"\nBase Year Revenue:         {assumptions.base_revenue:,.2f} Million CNY")
    report.append(f"Assumed FCF Margin:       {assumptions.base_fcf_margin * 100:.1f}%")
    report.append(f"High-Growth Rate:        {assumptions.high_growth_rate * 100:.1f}% per annum")
    report.append(f"High-Growth Period:      {assumptions.high_growth_years} years")
    report.append(f"Terminal Growth Rate:    {assumptions.terminal_growth_rate * 100:.1f}%")
    report.append(f"Discount Rate (WACC):    {assumptions.wacc * 100:.1f}%")
    report.append(f"Net Debt:                {assumptions.net_debt:,.2f} Million CNY")
    report.append(f"Shares Outstanding:      {assumptions.shares_outstanding:,.2f} Million")
    
    # Projection section
    report.append("\n" + "-" * 70)
    report.append("HIGH-GROWTH PERIOD PROJECTIONS")
    report.append("-" * 70)
    report.append(f"\n{'Year':<8} {'Projected FCF':>20} {'Discount Factor':>18} {'PV of FCF':>18}")
    report.append("-" * 66)
    
    cumulative_pv = 0
    for year, fcf in enumerate(result.high_growth_fcf, start=1):
        discount_factor = (1 + assumptions.wacc) ** year
        pv = fcf / discount_factor
        cumulative_pv += pv
        report.append(f"{year:<8} {fcf:>20,.2f} {discount_factor:>18.4f} {pv:>18,.2f}")
    
    report.append("-" * 66)
    report.append(f"{'Total PV (High-Growth):':<30}{cumulative_pv:>35,.2f}")
    
    # Terminal value section
    report.append("\n" + "-" * 70)
    report.append("TERMINAL VALUE CALCULATION")
    report.append("-" * 70)
    
    last_fcf = result.high_growth_fcf[-1]
    terminal_fcf = last_fcf * (1 + assumptions.terminal_growth_rate)
    tv = terminal_fcf / (assumptions.wacc - assumptions.terminal_growth_rate)
    discount_factor = (1 + assumptions.wacc) ** assumptions.high_growth_years
    pv_terminal = tv / discount_factor
    
    report.append(f"\nTerminal FCF (Year {assumptions.high_growth_years + 1}):   {terminal_fcf:,.2f} Million CNY")
    report.append(f"Terminal Growth Rate:                        {assumptions.terminal_growth_rate * 100:.1f}%")
    report.append(f"WACC - Terminal Growth:                     {(assumptions.wacc - assumptions.terminal_growth_rate) * 100:.1f}%")
    report.append(f"Terminal Value (Gordon Growth Model):       {tv:,.2f} Million CNY")
    report.append(f"Discount Factor (Year {assumptions.high_growth_years}):        {discount_factor:.4f}")
    report.append(f"PV of Terminal Value:                       {pv_terminal:,.2f} Million CNY")
    
    # Summary section
    report.append("\n" + "-" * 70)
    report.append("ENTERPRISE VALUE & EQUITY VALUE SUMMARY")
    report.append("-" * 70)
    
    total_ev = cumulative_pv + pv_terminal
    
    report.append(f"\nPV of High-Growth FCFs:      {cumulative_pv:>30,.2f} Million CNY")
    report.append(f"PV of Terminal Value:        {pv_terminal:>30,.2f} Million CNY")
    report.append("-" * 66)
    report.append(f"Total Enterprise Value:     {total_ev:>30,.2f} Million CNY")
    report.append(f"Less: Net Debt:             {assumptions.net_debt:>30,.2f} Million CNY")
    report.append("-" * 66)
    report.append(f"Equity Value:               {result.equity_value:>30,.2f} Million CNY")
    report.append(f"Shares Outstanding:         {assumptions.shares_outstanding:>30,.2f} Million")
    report.append("=" * 66)
    report.append(f"DCF VALUE PER SHARE:        {result.value_per_share:>30,.2f} CNY")
    report.append("=" * 66)
    
    # Implied metrics
    report.append("\n" + "-" * 70)
    report.append("IMPLIED VALUATION METRICS")
    report.append("-" * 70)
    
    final_revenue = assumptions.base_revenue * ((1 + assumptions.high_growth_rate) ** assumptions.high_growth_years)
    report.append(f"\nImplied EV/Revenue Multiple:    {result.implied_exit_multiple:.2f}x")
    report.append(f"(Based on Year-{assumptions.high_growth_years} revenue of {final_revenue:,.2f} Million CNY)")
    
    # Sensitivity analysis
    report.append("\n" + "-" * 70)
    report.append("SENSITIVITY ANALYSIS (Value Per Share)")
    report.append("-" * 70)
    
    # Create sensitivity table for WACC vs Terminal Growth
    wacc_values = [assumptions.wacc - 0.01, assumptions.wacc, assumptions.wacc + 0.01]
    tg_values = [assumptions.terminal_growth_rate - 0.005, assumptions.terminal_growth_rate, assumptions.terminal_growth_rate + 0.005]
    
    # Header
    header = f"{'':>12}"
    for tg in tg_values:
        header += f"TG={tg*100:.1f}%{'':>8}"
    report.append(f"\n{'':>12}" + "".join([f"{tg*100:.1f}%{'':>12}" for tg in tg_values]))
    report.append("-" * (12 + 20 * len(tg_values)))
    
    for wacc in wacc_values:
        row = f"WACC={wacc*100:.1f}% "
        for tg in tg_values:
            if wacc <= tg:
                row += f"{'N/A':>15}"
            else:
                # Recalculate with adjusted parameters
                test_assumptions = DCFAssumptions(
                    base_revenue=assumptions.base_revenue,
                    base_fcf_margin=assumptions.base_fcf_margin,
                    high_growth_rate=assumptions.high_growth_rate,
                    high_growth_years=assumptions.high_growth_years,
                    terminal_growth_rate=tg,
                    wacc=wacc,
                    net_debt=assumptions.net_debt,
                    shares_outstanding=assumptions.shares_outstanding
                )
                test_result = _calculate_dcf(test_assumptions, result.company_name)
                row += f"{test_result.value_per_share:>15,.2f}"
        report.append(row)
    
    # Disclaimer
    report.append("\n" + "-" * 70)
    report.append("DISCLAIMER")
    report.append("-" * 70)
    report.append("\nThis DCF valuation is for educational and internal research purposes only.")
    report.append("It does not constitute a buy/sell recommendation.")
    report.append("Actual valuations should consider additional factors including:")
    report.append("- Market conditions and competitive dynamics")
    report.append("- Policy and subsidy environment in China EV sector")
    report.append("- Company-specific risks and growth strategies")
    report.append("- Comparable company and transaction multiples")
    report.append("\n" + "=" * 70)
    report.append("END OF DCF ANALYSIS")
    report.append("=" * 70)
    
    return "\n".join(report)


@tool
def calculate_dcf(
    base_revenue: str,
    base_fcf_margin: str,
    high_growth_rate: str,
    high_growth_years: str,
    terminal_growth_rate: str,
    wacc: str,
    net_debt: str,
    shares_outstanding: str,
    company_name: str = "NEPV Company"
) -> str:
    """
    Calculate DCF (Discounted Cash Flow) valuation for NEPV companies.
    
    This tool performs a comprehensive DCF analysis including:
    - High-growth period FCF projections
    - Terminal value using Gordon Growth Model
    - Enterprise and equity value calculation
    - Value per share computation
    - Sensitivity analysis
    
    Args:
        base_revenue: Latest revenue in Million CNY (e.g., "50000" for 50 billion CNY)
        base_fcf_margin: FCF margin as decimal (e.g., "0.08" for 8%, or "8" for 8%)
        high_growth_rate: Expected revenue/FCF growth rate for high-growth period (e.g., "0.15" for 15% or "15" for 15%)
        high_growth_years: Length of high-growth period in years (e.g., "5")
        terminal_growth_rate: Terminal growth rate as decimal (e.g., "0.025" for 2.5% or "2.5" for 2.5%)
        wacc: Weighted Average Cost of Capital as decimal (e.g., "0.10" for 10% or "10" for 10%)
        net_debt: Net debt position in Million CNY (e.g., "10000")
        shares_outstanding: Shares outstanding in Million (e.g., "3000")
        company_name: Name of the company (optional, default "NEPV Company")
    
    Returns:
        A comprehensive DCF valuation report with projections, calculations, and sensitivity analysis
    
    Example:
        calculate_dcf(
            base_revenue="80000",        # 80 billion CNY
            base_fcf_margin="0.10",     # 10% FCF margin
            high_growth_rate="0.15",    # 15% growth
            high_growth_years="5",       # 5 years
            terminal_growth_rate="0.025", # 2.5% terminal
            wacc="0.09",                # 9% WACC
            net_debt="15000",          # 15 billion CNY net debt
            shares_outstanding="3500",  # 3.5 billion shares
            company_name="BYD"
        )
    """
    ctx = request_context.get() or new_context(method="calculate_dcf")
    
    try:
        # Parse all numeric inputs
        # Handle both decimal ("0.10") and percentage ("10") formats
        def parse_number(val: str, is_percentage: bool = False) -> float:
            val = val.strip()
            if not val:
                raise ValueError("Empty value provided")
            
            # Remove % sign if present
            if val.endswith('%'):
                val = val[:-1]
            
            num = float(val)
            
            # Convert to decimal if percentage format was used
            if is_percentage and abs(num) > 1:
                num = num / 100
            
            return num
        
        base_rev = parse_number(base_revenue)
        fcf_margin = parse_number(base_fcf_margin, is_percentage=True)
        growth_rate = parse_number(high_growth_rate, is_percentage=True)
        high_growth_yrs = int(float(high_growth_years))
        term_growth = parse_number(terminal_growth_rate, is_percentage=True)
        discount_rate = parse_number(wacc, is_percentage=True)
        net_debt_val = parse_number(net_debt)
        shares = parse_number(shares_outstanding)
        
        # Validate inputs
        if base_rev <= 0:
            return "Error: Base revenue must be positive"
        if fcf_margin <= 0 or fcf_margin > 1:
            return "Error: FCF margin should be between 0 and 1 (e.g., 0.10 for 10%)"
        if growth_rate < 0:
            return "Error: Growth rate cannot be negative"
        if high_growth_yrs <= 0:
            return "Error: High-growth period must be at least 1 year"
        if term_growth < 0:
            return "Error: Terminal growth rate cannot be negative"
        if discount_rate <= term_growth:
            return "Error: WACC must be greater than terminal growth rate"
        if discount_rate <= 0:
            return "Error: WACC must be positive"
        if shares <= 0:
            return "Error: Shares outstanding must be positive"
        
        # Create assumptions object
        assumptions = DCFAssumptions(
            base_revenue=base_rev,
            base_fcf_margin=fcf_margin,
            high_growth_rate=growth_rate,
            high_growth_years=high_growth_yrs,
            terminal_growth_rate=term_growth,
            wacc=discount_rate,
            net_debt=net_debt_val,
            shares_outstanding=shares
        )
        
        # Calculate DCF
        result = _calculate_dcf(assumptions, company_name)
        
        # Format and return report
        report = _format_dcf_report(result, assumptions)
        return report
        
    except ValueError as e:
        return f"Input Error: {str(e)}\n\nPlease ensure all inputs are valid numbers."
    except Exception as e:
        return f"Calculation Error: {str(e)}\n\nPlease check your inputs and try again."
