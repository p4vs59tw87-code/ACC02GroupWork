"""
Report Generator Tool
Generates comprehensive equity research reports for NEPV company analysis.
"""
from typing import Dict, Optional, Any
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


@tool
def generate_report(
    company_name: str,
    historical_analysis: str,
    dcf_valuation: str,
    additional_commentary: Optional[str] = None
) -> str:
    """
    Generate a comprehensive equity research report combining historical analysis and DCF valuation.
    
    This tool creates a professional investment research report with:
    - Executive summary
    - Historical financial analysis
    - DCF valuation results
    - Industry context commentary
    - Key risks and considerations
    
    Args:
        company_name: Name of the NEPV company being analyzed
        historical_analysis: Historical financial analysis output from parse_wrds_csv tool
        dcf_valuation: DCF valuation output from calculate_dcf tool
        additional_commentary: Optional industry-specific commentary (NEPV sector dynamics, policy outlook, etc.)
    
    Returns:
        A comprehensive equity research report in professional format
    
    Example:
        generate_report(
            company_name="BYD",
            historical_analysis=parsed_csv_output,
            dcf_valuation=dcf_calculation_output,
            additional_commentary="China NEV penetration rate reached 38% in 2024..."
        )
    """
    ctx = request_context.get() or new_context(method="generate_report")
    
    try:
        report = []
        
        # Header
        report.append("=" * 80)
        report.append(" " * 20 + "EQUITY RESEARCH REPORT")
        report.append(" " * 15 + "China New Energy Passenger Vehicle (NEPV) Sector")
        report.append("=" * 80)
        report.append(f"\nCompany: {company_name}")
        report.append("Report Type: DCF Valuation Analysis")
        report.append("Sector: China New Energy Passenger Vehicles")
        report.append("Analyst Tool: Automated NEPV Equity Research Assistant")
        report.append("")
        report.append("This report is generated for internal research and educational purposes.")
        report.append("It does not constitute a buy/sell recommendation.")
        report.append("=" * 80)
        
        # Executive Summary
        report.append("\n" + "=" * 80)
        report.append("EXECUTIVE SUMMARY")
        report.append("=" * 80)
        report.append(f"""
This report provides a comprehensive DCF-based equity valuation analysis for {company_name}, 
a leading player in China's New Energy Passenger Vehicle (NEPV) industry.

The analysis encompasses:
• Historical financial performance review
• Free Cash Flow (FCF) projections based on industry growth dynamics
• Discounted Cash Flow (DCF) valuation with terminal value
• Sensitivity analysis to key assumptions
• Industry context and considerations specific to China's EV market

Key assumptions for this valuation include high-growth period revenue growth rates, 
terminal growth rate, and weighted average cost of capital (WACC) calibrated for 
the NEPV sector's risk profile.
""")
        
        # Industry Context
        report.append("\n" + "=" * 80)
        report.append("INDUSTRY CONTEXT: CHINA NEPV SECTOR")
        report.append("=" * 80)
        report.append("""
China's New Energy Passenger Vehicle (NEPV) market is the world's largest and fastest-growing 
EV market. Key industry metrics and considerations include:

Market Dynamics:
• NEV penetration rate has exceeded 40% in 2024, well ahead of government targets
• Competition intensifying with both domestic champions and international OEMs
• Price war pressure ongoing since 2023, impacting margins across the sector
• Technology迭代加速 (rapid technology iteration): battery innovations, autonomous driving

Policy Environment:
• Subsidy phase-out completed in 2022; market now operates on commercial dynamics
• Purchase tax exemption extended through 2027 for NEVs
• Infrastructure support: charging network expanding rapidly
• New energy vehicle credit system driving production mandates

Competitive Landscape:
• BYD maintaining market leadership with vertically integrated model
• NIO, Li Auto, Xpeng competing in premium segments
• Traditional OEMs (Geely, GAC, Changan) accelerating EV transitions
• Tesla Shanghai Gigafactory as major international competitor
""")
        
        # Historical Analysis Section
        report.append("\n" + "=" * 80)
        report.append("SECTION 1: HISTORICAL FINANCIAL ANALYSIS")
        report.append("=" * 80)
        report.append("\n" + "-" * 80)
        report.append("The following analysis is based on WRDS-exported financial data:")
        report.append("-" * 80)
        report.append(f"\n{historical_analysis}")
        
        # DCF Valuation Section
        report.append("\n\n" + "=" * 80)
        report.append("SECTION 2: DCF VALUATION ANALYSIS")
        report.append("=" * 80)
        report.append("\n" + "-" * 80)
        report.append("Based on the valuation assumptions provided:")
        report.append("-" * 80)
        report.append(f"\n{dcf_valuation}")
        
        # Additional Commentary
        if additional_commentary:
            report.append("\n\n" + "=" * 80)
            report.append("SECTION 3: ADDITIONAL COMMENTARY")
            report.append("=" * 80)
            report.append(f"\n{additional_commentary}")
        
        # Valuation Considerations
        report.append("\n" + "=" * 80)
        report.append("VALUATION CONSIDERATIONS & RISKS")
        report.append("=" * 80)
        report.append("""
Key factors to consider when interpreting this DCF valuation:

Bull Case Factors:
• Continued market share gains in China's expanding EV market
• Technology leadership in battery, autonomous driving capabilities
• Export potential to emerging markets and Europe
• Operating leverage as scale increases

Bear Case Risks:
• Intensifying price competition compressing margins
• Policy changes affecting credit system or incentives
• Execution risk in technology transitions
• Capital intensity for R&D and manufacturing capacity
• Potential overcapacity in domestic market

Methodology Notes:
• DCF is particularly suitable for growth companies with visible cash flow trajectories
• Terminal value represents significant portion of total value (typical for growth companies)
• Key sensitivities: WACC, terminal growth rate, FCF margin assumptions
• Consider alongside comparable company analysis and precedent transactions
""")
        
        # Conclusion
        report.append("\n" + "=" * 80)
        report.append("CONCLUSION")
        report.append("=" * 80)
        report.append(f"""
This DCF analysis provides a fundamental valuation framework for {company_name} 
based on projected cash flows and standard discount rate assumptions.

The valuation is sensitive to:
1. Revenue growth rate assumptions during the high-growth period
2. FCF margin trajectory and sustainability
3. Terminal growth rate reflecting long-term industry growth
4. WACC (discount rate) reflecting systematic risk

The analyst should adjust these assumptions based on:
• Company-specific competitive position and strategy
• Industry penetration rate trajectory and market size estimates
• Macroeconomic conditions and interest rate environment
• Company-specific risk factors (technology, execution, regulatory)

This analysis should be used in conjunction with:
• Comparable company analysis (EV/Revenue, EV/EBITDA multiples)
• Precedent transaction analysis
• Historical trading ranges
• Price target from alternative methodologies
""")
        
        # Disclaimer
        report.append("\n" + "=" * 80)
        report.append("IMPORTANT DISCLAIMER")
        report.append("=" * 80)
        report.append("""
This report is generated by an automated equity research tool for educational and 
internal research purposes only.

IMPORTANT:
• This is NOT a buy/sell recommendation
• This analysis should not be the sole basis for investment decisions
• Actual valuations require professional judgment and qualitative analysis
• Past performance is not indicative of future results
• The NEPV sector carries elevated risk due to:
  - Rapid technological change
  - Evolving regulatory environment  
  - Intense competitive dynamics
  - Commodity price volatility (lithium, cobalt, nickel)

Users of this tool should:
• Independently verify all data inputs
• Consult with qualified investment professionals
• Consider their own risk tolerance and investment objectives
• Review additional research and analysis from licensed analysts
""")
        
        report.append("\n" + "=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)
        
        return "\n".join(report)
        
    except Exception as e:
        return f"Error generating report: {str(e)}\n\nPlease ensure all inputs are valid."
