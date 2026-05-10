"""
NEPV DCF Valuation Agent - Standalone Web Application
"""
from flask import Flask, render_template, request, jsonify
from coze_coding_dev_sdk import LLMClient
from coze_coding_utils.runtime_ctx.context import new_context
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import json
import traceback

app = Flask(__name__)

# System prompt for the NEPV DCF Agent
SYSTEM_PROMPT = """You are a professional equity research analyst specializing in the China New Energy Passenger Vehicle (NEPV) industry.

You have access to these tools:
1. wrds_direct_fetch - Fetch real financial data from WRDS using user's credentials
2. auto_financial_data_fetcher - Use sample financial data for quick analysis
3. generate_visualization - Generate interactive HTML charts with charts saved to object storage
4. calculate_dcf - Calculate DCF valuation
5. generate_dcf_sensitivity_chart - Generate sensitivity heatmap

WORKFLOW:
1. If user provides WRDS credentials (username + password), use wrds_direct_fetch to get real data
2. Otherwise, use auto_financial_data_fetcher with sample data
3. Generate visualization charts (will be saved to cloud storage and links provided)
4. Ask user for DCF assumptions or use reasonable defaults
5. Calculate DCF valuation
6. Display all results with chart links

Supported tickers: BYD, TSLA, XPeng, LiAuto, NIO

IMPORTANT RULES:
- ALWAYS call generate_visualization to create charts - the chart will be uploaded to cloud storage
- Display chart URLs as clickable links [View Charts](URL)
- Use the wrds_direct_fetch tool when user provides WRDS credentials
- Reply in the same language as the user (Chinese or English)
- Do NOT provide investment advice
- For DCF, use these default assumptions if user doesn't specify:
  * High-growth period: 5 years
  * High-growth rate: 15%
  * Terminal growth rate: 2.5%
  * WACC: 9%
"""

# Initialize LLM client
llm_client = None

def get_llm_client():
    global llm_client
    if llm_client is None:
        ctx = new_context(method="web_chat")
        llm_client = LLMClient(ctx=ctx)
    return llm_client

# Sample financial data for quick analysis
SAMPLE_DATA = {
    "BYD": {
        "company_name": "BYD Company Limited",
        "timeline": [2020, 2021, 2022, 2023, 2024],
        "revenue": [156598, 216142, 424061, 602335, 760307],
        "net_income": [4233, 2720, 16622, 28038, 29041],
        "fcf": [8563, 4521, 18294, 32450, 35218],
        "gross_margin": [17.8, 13.0, 17.0, 20.0, 21.0],
        "operating_margin": [3.5, 1.48, 4.9, 5.31, 4.73],
        "net_margin": [2.7, 1.26, 3.92, 4.65, 3.82],
        "revenue_growth": [38.02, 96.2, 42.04, 26.23]
    },
    "TSLA": {
        "company_name": "Tesla Inc.",
        "timeline": [2020, 2021, 2022, 2023, 2024],
        "revenue": [31536, 53823, 81462, 96773, 97000],
        "net_income": [721, 5647, 12556, 15000, 7800],
        "fcf": [2740, 6490, 14700, 20600, 20000],
        "gross_margin": [20.1, 25.6, 25.6, 18.2, 17.4],
        "operating_margin": [5.4, 12.1, 17.2, 9.2, 6.5],
        "net_margin": [2.3, 10.5, 15.4, 15.5, 8.0],
        "revenue_growth": [28.3, 70.7, 51.4, 18.8, 0.2]
    },
    "NIO": {
        "company_name": "NIO Inc.",
        "timeline": [2021, 2022, 2023, 2024],
        "revenue": [36136, 49274, 55618, 61703],
        "net_income": [-40283, -145570, -207196, -224991],
        "fcf": [-35000, -70000, -90000, -50000],
        "gross_margin": [20.1, 13.7, 5.5, 9.1],
        "operating_margin": [-45.1, -88.9, -56.3, -38.4],
        "net_margin": [-111.5, -295.5, -372.5, -364.6],
        "revenue_growth": [122.3, 36.3, 12.9, 10.9]
    },
    "XPeng": {
        "company_name": "XPeng Inc.",
        "timeline": [2021, 2022, 2023, 2024],
        "revenue": [20988, 30658, 30658, 40800],
        "net_income": [-285917, -48608, -23277, -23621],
        "fcf": [-45000, -20000, -20000, -10000],
        "gross_margin": [20.5, 19.4, 19.4, 14.3],
        "operating_margin": [-35.2, -42.3, -42.3, -25.0],
        "net_margin": [-136.2, -158.6, -158.6, -60.0],
        "revenue_growth": [259.1, 46.1, 0.0, 33.1]
    },
    "LiAuto": {
        "company_name": "Li Auto Inc.",
        "timeline": [2021, 2022, 2023, 2024],
        "revenue": [27019, 45281, 144800, 144500],
        "net_income": [-32063, -20243, 117203, 80000],
        "fcf": [-20000, -10000, 80000, 70000],
        "gross_margin": [20.6, 22.2, 22.2, 20.0],
        "operating_margin": [-5.1, -1.8, 9.5, 8.0],
        "net_margin": [-11.8, -4.5, 8.1, 5.5],
        "revenue_growth": [185.6, 67.6, 219.8, -0.2]
    }
}

@app.route('/')
def index():
    """Render the chat interface"""
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    try:
        data = request.json
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        wrds_username = data.get('wrds_username')
        wrds_password = data.get('wrds_password')
        
        # Build messages
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        
        # Add conversation history
        for msg in conversation_history:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            else:
                messages.append(AIMessage(content=msg['content']))
        
        # Add current message with WRDS info if provided
        if wrds_username and wrds_password:
            enhanced_message = f"""{user_message}

IMPORTANT: The user has provided WRDS credentials:
- WRDS Username: {wrds_username}
- WRDS Password: {wrds_password}

You MUST use the wrds_direct_fetch tool with these credentials to fetch real financial data from WRDS."""
            messages.append(HumanMessage(content=enhanced_message))
        else:
            messages.append(HumanMessage(content=user_message))
        
        # Get LLM response
        client = get_llm_client()
        response = client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.7
        )
        
        # Extract text from response
        response_text = response.content if isinstance(response.content, str) else str(response.content)
        
        return jsonify({
            'success': True,
            'response': response_text,
            'wrds_connected': bool(wrds_username and wrds_password)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/companies', methods=['GET'])
def get_companies():
    """Get list of supported companies"""
    return jsonify({
        'success': True,
        'companies': list(SAMPLE_DATA.keys())
    })

@app.route('/api/sample_data/<ticker>', methods=['GET'])
def get_sample_data(ticker):
    """Get sample data for a company"""
    ticker = ticker.upper()
    if ticker in SAMPLE_DATA:
        return jsonify({
            'success': True,
            'data': SAMPLE_DATA[ticker]
        })
    return jsonify({
        'success': False,
        'error': 'Company not found'
    }), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
