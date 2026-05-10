# ============================================================
# Node Name: dcf_valuation
# Coze Code Node
# 
# Input:
#   - latest_fcf (float): Latest year's free cash flow (million CNY)
#   - growth_high (float): Growth rate during high-growth period (e.g., 0.15)
#   - years_high (int): Number of years in high-growth period
#   - growth_terminal (float): Terminal growth rate (e.g., 0.02)
#   - wacc (float): Discount rate / WACC (e.g., 0.09)
#   - net_debt (float): Net debt = total debt - cash (million CNY)
#   - shares_outstanding (float): Number of shares outstanding (million)
# 
# Output:
#   - enterprise_value_mn (float)
#   - equity_value_mn (float)
#   - equity_value_per_share (float)
#   - valuation_summary (str)
# ============================================================

def main(latest_fcf, growth_high, years_high, growth_terminal, wacc, net_debt, shares_outstanding):
    """
    Two-stage Discounted Cash Flow (DCF) valuation model.
    """
    
    # ----------------------------- INPUT VALIDATION ----------------------------
    try:
        fcf = float(latest_fcf)
        g_high = float(growth_high)
        n_high = int(years_high)
        g_term = float(growth_terminal)
        r = float(wacc)
        net_debt = float(net_debt)
        shares = float(shares_outstanding) if shares_outstanding else None
    except (TypeError, ValueError) as e:
        return {
            "error": f"Invalid input types: {str(e)}",
            "enterprise_value_mn": None,
            "equity_value_mn": None,
            "equity_value_per_share": None,
            "valuation_summary": ""
        }
    
    if fcf <= 0:
        return {
            "error": "Latest free cash flow must be positive for DCF valuation.",
            "enterprise_value_mn": None,
            "equity_value_mn": None,
            "equity_value_per_share": None,
            "valuation_summary": ""
        }
    
    if r <= g_term:
        return {
            "error": "Discount rate (WACC) must be greater than terminal growth rate.",
            "enterprise_value_mn": None,
            "equity_value_mn": None,
            "equity_value_per_share": None,
            "valuation_summary": ""
        }
    
    if n_high <= 0:
        return {
            "error": "High-growth period years must be positive.",
            "enterprise_value_mn": None,
            "equity_value_mn": None,
            "equity_value_per_share": None,
            "valuation_summary": ""
        }
    
    # ----------------------------- STAGE 1: HIGH GROWTH ------------------------
    pv_stage1 = 0.0
    current_fcf = fcf
    
    for t in range(1, n_high + 1):
        current_fcf = current_fcf * (1 + g_high)
        pv_stage1 += current_fcf / ((1 + r) ** t)
    
    # ----------------------------- STAGE 2: TERMINAL VALUE ---------------------
    fcf_terminal_start = current_fcf * (1 + g_term)
    terminal_value = fcf_terminal_start / (r - g_term)
    pv_terminal = terminal_value / ((1 + r) ** n_high)
    
    # ----------------------------- VALUATION RESULTS ---------------------------
    enterprise_value = pv_stage1 + pv_terminal
    equity_value = enterprise_value - net_debt
    
    if shares and shares > 0:
        value_per_share = equity_value / shares
    else:
        value_per_share = None
    
    # ----------------------------- SUMMARY REPORT ------------------------------
    summary_lines = [
        "**DCF Valuation Summary**",
        "",
        "**Assumptions:**",
        f"- Latest Free Cash Flow (LTM): {fcf:.0f} million CNY",
        f"- High-growth period: {n_high} years @ {g_high*100:.1f}% growth",
        f"- Terminal growth rate: {g_term*100:.1f}%",
        f"- Discount rate (WACC): {r*100:.1f}%",
        "- Net debt: {net_debt:.0f} million CNY",
        "",
        "**Results:**",
        f"- Present value of high-growth period: {pv_stage1:.0f} million CNY",
        f"- Present value of terminal value: {pv_terminal:.0f} million CNY",
        f"- **Enterprise Value**: {enterprise_value:.0f} million CNY",
        f"- **Equity Value**: {equity_value:.0f} million CNY",
    ]
    
    if value_per_share:
        summary_lines.append(f"- **Value per Share**: {value_per_share:.2f} CNY")
        summary_lines.append(f"  (based on {shares:.0f} million shares outstanding)")
    
    summary_lines.extend([
        "",
        "**Sensitivity Guidance:**",
        "- Value per share increases by ~1.5-2% for every 0.5% increase in terminal growth",
        "- Value per share decreases by ~1-1.5% for every 0.5% increase in WACC",
        "",
        "**Disclaimer**: This valuation is for educational purposes only. "
        "Actual investment decisions require additional qualitative analysis and risk assessment."
    ])
    
    summary_text = "\n".join(summary_lines)
    
    return {
        "error": "",
        "enterprise_value_mn": round(enterprise_value, 2),
        "equity_value_mn": round(equity_value, 2),
        "equity_value_per_share": round(value_per_share, 2) if value_per_share else None,
        "valuation_summary": summary_text
    }