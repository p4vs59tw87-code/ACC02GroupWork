"""
NEPV DCF Valuation Agent - Direct Tool Calling Version
"""
import os
import json
import logging
from typing import Annotated
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from coze_coding_utils.runtime_ctx.context import default_headers
from storage.memory.memory_saver import get_memory_saver

LLM_CONFIG = "config/agent_llm_config.json"
MAX_MESSAGES = 40

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _windowed_messages(old, new):
    return add_messages(old, new)[-MAX_MESSAGES:]

class AgentState(MessagesState):
    messages: Annotated[list[AnyMessage], _windowed_messages]

def _load_tools():
    """Load all tools."""
    tools = []
    try:
        from tools import (
            auto_financial_data_fetcher,
            generate_visualization,
            generate_dcf_sensitivity_chart,
            calculate_dcf
        )
        tools.extend([auto_financial_data_fetcher, generate_visualization, generate_dcf_sensitivity_chart, calculate_dcf])
        logger.info(f"Loaded {len(tools)} tools")
    except Exception as e:
        logger.error(f"Failed to load tools: {e}")
    return tools

def build_agent(ctx=None):
    """Build the NEPV DCF Valuation Agent."""
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    config_path = os.path.join(workspace_path, LLM_CONFIG)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    
    api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
    base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")
    
    tools = _load_tools()
    logger.info(f"Building agent with {len(tools)} tools: {[t.name for t in tools]}")
    
    llm = ChatOpenAI(
        model=cfg['config'].get("model", "doubao-seed-2-0-pro-260215"),
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
        streaming=True,
        timeout=120,
        extra_body={"thinking": {"type": "disabled"}},
        default_headers=default_headers(ctx) if ctx else {}
    )
    
    system_prompt = """You are a financial data analysis assistant. When the user asks to analyze a company like 'BYD' or 'NIO':

**IMMEDIATELY** call the `auto_financial_data_fetcher` tool with:
- ticker: the company ticker (e.g., 'BYD', 'NIO')
- company_name: the full company name

Do NOT ask the user for anything. Just call the tool.

After getting the data, **IMMEDIATELY** call `generate_visualization` with the chart_data from the result.

Finally, summarize the key metrics for the user.

Example conversation:
User: analyze BYD
Assistant: [calls auto_financial_data_fetcher, then generate_visualization, then summarizes results]
"""

    return create_agent(
        model=llm,
        system_prompt=system_prompt,
        tools=tools,
        checkpointer=get_memory_saver(),
        state_schema=AgentState,
    )
