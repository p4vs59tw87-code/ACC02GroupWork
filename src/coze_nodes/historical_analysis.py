# ============================================================
# Node Name: historical_analysis
# Coze Code Node
# 
# Input: financial_records_json (str) - output from parse_csv node
# Output: analysis_text (str), chart_data_json (str)
# ============================================================

import json
from collections import Counter

def main(financial_records_json):
    """
    Calculate historical financial metrics and generate analysis text.
    """
    
    # ----------------------------- PARSE INPUT ---------------------------------
    try:
        records = json.loads(financial_records_json)
    except Exception as e:
        return {
            "analysis_text": f"Failed to parse input data: {str(e)}",
            "chart_data_json": "{}"
        }
    
    if not records:
        return {
            "analysis_text": "No financial records found.",
            "chart_data_json": "{}"
        }
    
    # ----------------------------- IDENTIFY MAIN COMPANY -----------------------
    company_counts = Counter([r.get('company_name', 'Unknown') for r in records])
    main_company = company_counts.most_common(1)[0][0]
    
    # Filter and sort records for the main company
    company_records = [r for r in records if r.get('company_name') == main_company]
    company_records.sort(key=lambda x: x.get('year', 0))
    
    # ----------------------------- EXTRACT TIME SERIES -------------------------
    years = []
    revenues = []
    net_incomes = []
    fcf = []
    gross_margins = []
    deliveries = []
    asp = []
    
    for r in company_records:
        years.append(r.get('year'))
        revenues.append(r.get('revenue', 0))
        net_incomes.append(r.get('net_income', 0) if r.get('net_income') else 0)
        fcf.append(r.get('free_cash_flow', 0) if r.get('free_cash_flow') else 0)
        gross_margins.append(r.get('gross_margin_pct', 0) if r.get('gross_margin_pct') else 0)
        deliveries.append(r.get('deliveries', 0) if r.get('deliveries') else 0)
        asp.append(r.get('asp', 0) if r.get('asp') else 0)
    
    # ----------------------------- CAGR CALCULATIONS ---------------------------
    def calculate_cagr(values):
        if len(values) < 2 or values[0] == 0 or values[0] is None:
            return None
        # Filter out None/0 values? Use first and last non-zero
        non_zero = [v for v in values if v and v > 0]
        if len(non_zero) < 2:
            return None
        return (non_zero[-1] / non_zero[0]) ** (1/(len(non_zero)-1)) - 1
    
    rev_cagr = calculate_cagr(revenues)
    ni_cagr = calculate_cagr(net_incomes) if any(net_incomes) else None
    fcf_cagr = calculate_cagr(fcf) if any(fcf) else None
    delivery_cagr = calculate_cagr(deliveries) if deliveries and deliveries[0] else None
    
    # ----------------------------- BUILD ANALYSIS TEXT -------------------------
    lines = []
    lines.append(f"### Company: {main_company}")
    lines.append(f"**Analysis Period**: {years[0]} - {years[-1]}")
    lines.append("")
    lines.append("**Key Growth Rates (CAGR):**")
    
    if rev_cagr:
        lines.append(f"- Revenue: {rev_cagr*100:.1f}%")
    if ni_cagr:
        lines.append(f"- Net Income: {ni_cagr*100:.1f}%")
    if fcf_cagr:
        lines.append(f"- Free Cash Flow: {fcf_cagr*100:.1f}%")
    if delivery_cagr:
        lines.append(f"- Deliveries: {delivery_cagr*100:.1f}%")
    
    # Latest year metrics
    last = company_records[-1]
    lines.append("")
    lines.append(f"**Latest Year ({last['year']}) Metrics:**")
    lines.append(f"- Revenue: {last['revenue']:.0f} million CNY")
    
    if last.get('net_income'):
        lines.append(f"- Net Income: {last['net_income']:.0f} million CNY")
    if last.get('free_cash_flow'):
        lines.append(f"- Free Cash Flow: {last['free_cash_flow']:.0f} million CNY")
    if last.get('gross_margin_pct'):
        lines.append(f"- Gross Margin: {last['gross_margin_pct']:.1f}%")
    if last.get('deliveries'):
        lines.append(f"- Deliveries: {last['deliveries']:,.0f} units")
    if last.get('asp'):
        lines.append(f"- ASP: {last['asp']:.0f} thousand CNY")
    
    # Trend comments
    lines.append("")
    lines.append("**Trend Observations:**")
    
    if rev_cagr:
        if rev_cagr > 0.15:
            lines.append("- Revenue growth is strong (>15% CAGR), indicating rapid expansion.")
        elif rev_cagr > 0.05:
            lines.append("- Revenue growth is moderate (5-15% CAGR).")
        else:
            lines.append("- Revenue growth is slow or negative.")
    
    if fcf_cagr and fcf_cagr > 0:
        lines.append("- Free cash flow is improving, supporting intrinsic value creation.")
    elif fcf_cagr and fcf_cagr < 0:
        lines.append("- Free cash flow is declining, requiring further investigation of capital allocation.")
    
    analysis_text = "\n".join(lines)
    
    # ----------------------------- PREPARE CHART DATA --------------------------
    chart_data = {
        "years": years,
        "revenue": revenues,
        "net_income": net_incomes,
        "free_cash_flow": fcf,
        "gross_margin": gross_margins,
        "deliveries": deliveries,
        "asp": asp
    }
    
    return {
        "analysis_text": analysis_text,
        "chart_data_json": json.dumps(chart_data)
    }