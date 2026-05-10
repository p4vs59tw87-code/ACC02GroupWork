"""
WRDS Direct Connection Tool
使用 psycopg2 直连 WRDS PostgreSQL，绕过 Duo 验证
参考 assets/data_fetcher.py 中的成功方案
"""
import psycopg2
import pandas as pd
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context


# WRDS PostgreSQL 连接参数
WRDS_HOST = "wrds-pgdata.wharton.upenn.edu"
WRDS_PORT = 9737
WRDS_DATABASE = "wrds"


def _create_wrds_connection(wrds_username: str, wrds_password: str) -> psycopg2.extensions.connection:
    """创建 WRDS 数据库连接（带超时保护）"""
    ctx = request_context.get() or new_context(method="wrds_connection")
    return psycopg2.connect(
        host=WRDS_HOST,
        port=WRDS_PORT,
        database=WRDS_DATABASE,
        user=wrds_username,
        password=wrds_password,
        connect_timeout=30,  # 30秒超时
        options="-c statement_timeout=60000"  # 查询超时60秒
    )


def _get_permno(conn: psycopg2.extensions.connection, ticker: str) -> tuple:
    """从 CRSP 获取股票的 permno"""
    query = f"""
        SELECT permno, comnam
        FROM crsp.msenames
        WHERE ticker = '{ticker}'
        AND namedt <= CURRENT_DATE
        AND (nameendt IS NULL OR nameendt >= CURRENT_DATE)
        ORDER BY namedt DESC
        LIMIT 1
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        return None, None
    return int(df.iloc[0]['permno']), df.iloc[0]['comnam']


def _get_compustat_fundamentals(conn: psycopg2.extensions.connection, gvkey: str, years: int = 5) -> pd.DataFrame:
    """从 Compustat 获取基本面数据"""
    query = f"""
        SELECT 
            gvkey,
            fyear as year,
            tic as ticker,
            conm as company_name,
            revt as revenue,
            ni as net_income,
            oibdp as operating_income,
            gp as gross_profit,
            fcf as free_cash_flow,
            oancf as operating_cash_flow,
            dlc as total_debt,
            che as cash,
            ceq as equity,
            csho as shares_outstanding
        FROM comp.funda
        WHERE gvkey = '{gvkey}'
        AND indfmt = 'INDL'
        AND datafmt = 'STD'
        AND popsrc = 'D'
        AND consol = 'C'
        AND fyear >= EXTRACT(YEAR FROM CURRENT_DATE) - {years}
        ORDER BY fyear DESC
    """
    return pd.read_sql(query, conn)


def _get_compustat_by_ticker(conn: psycopg2.extensions.connection, ticker: str, years: int = 5) -> pd.DataFrame:
    """通过 ticker 从 Compustat 获取数据"""
    query = f"""
        SELECT 
            gvkey,
            fyear as year,
            tic as ticker,
            conm as company_name,
            revt as revenue,
            ni as net_income,
            oibdp as operating_income,
            gp as gross_profit,
            fcf as free_cash_flow,
            oancf as operating_cash_flow,
            dlc as total_debt,
            che as cash,
            ceq as equity,
            csho as shares_outstanding
        FROM comp.funda
        WHERE LOWER(tic) = LOWER('{ticker}')
        AND indfmt = 'INDL'
        AND datafmt = 'STD'
        AND popsrc = 'D'
        AND consol = 'C'
        AND fyear >= EXTRACT(YEAR FROM CURRENT_DATE) - {years}
        ORDER BY fyear DESC
    """
    return pd.read_sql(query, conn)


def _get_gvkey_from_ticker(conn: psycopg2.extensions.connection, ticker: str) -> str:
    """从 Compustat 获取 gvkey"""
    query = f"""
        SELECT DISTINCT gvkey, conm
        FROM comp.funda
        WHERE LOWER(tic) = LOWER('{ticker}')
        LIMIT 1
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        return None
    return df.iloc[0]['gvkey']


def _format_financial_data(df: pd.DataFrame, company_name: str, ticker: str) -> dict:
    """格式化财务数据为标准格式"""
    if df.empty:
        return {
            "status": "error",
            "message": "No data found for this ticker"
        }
    
    # 转换为百万单位（WRDS 通常以美元计，需要换算）
    # 这里简化处理，假设数据已经是所需单位
    timeline = df['year'].tolist()
    
    # 处理 NaN 值
    def safe_float(val):
        if pd.isna(val):
            return 0.0
        return float(val)
    
    result = {
        "status": "success",
        "company_name": company_name or df.iloc[0]['company_name'] if 'company_name' in df.columns else ticker,
        "ticker": ticker,
        "data_source": "WRDS Compustat",
        "timeline": timeline,
        "raw_data": {
            "revenue": [safe_float(x) for x in df['revenue'].tolist()],
            "net_income": [safe_float(x) for x in df['net_income'].tolist()],
            "operating_income": [safe_float(x) for x in df['operating_income'].tolist()],
            "gross_profit": [safe_float(x) for x in df['gross_profit'].tolist()],
            "fcf": [safe_float(x) for x in df['fcf'].tolist()],
            "total_debt": [safe_float(x) for x in df['total_debt'].tolist()],
            "cash": [safe_float(x) for x in df['cash'].tolist()],
            "equity": [safe_float(x) for x in df['equity'].tolist()],
            "shares_outstanding": [safe_float(x) for x in df['shares_outstanding'].tolist()],
        },
        "chart_data": {}
    }
    
    # 生成图表数据
    n = len(timeline)
    result["chart_data"] = {
        "timeline": timeline,
        "revenue": [safe_float(x) for x in df['revenue'].tolist()],
        "net_income": [safe_float(x) for x in df['net_income'].tolist()],
        "fcf": [safe_float(x) for x in df['fcf'].tolist()] if 'fcf' in df.columns else [0] * n,
        "gross_margin": [],
        "net_margin": [],
        "revenue_growth": []
    }
    
    # 计算利润率
    revenues = df['revenue'].tolist()
    net_incomes = df['net_income'].tolist()
    gross_profits = df['gross_profit'].tolist() if 'gross_profit' in df.columns else [0] * n
    
    for i in range(n):
        rev = safe_float(revenues[i])
        ni = safe_float(net_incomes[i])
        gp = safe_float(gross_profits[i])
        
        if rev > 0:
            result["chart_data"]["gross_margin"].append(round(gp / rev * 100, 2))
            result["chart_data"]["net_margin"].append(round(ni / rev * 100, 2))
        else:
            result["chart_data"]["gross_margin"].append(0)
            result["chart_data"]["net_margin"].append(0)
    
    # 计算收入增长率
    for i in range(1, n):
        prev_rev = safe_float(revenues[i - 1])
        curr_rev = safe_float(revenues[i])
        if prev_rev > 0:
            growth = (curr_rev - prev_rev) / prev_rev * 100
            result["chart_data"]["revenue_growth"].append(round(growth, 2))
    
    return result


@tool
def wrds_direct_fetch(
    wrds_username: str,
    ticker: str,
    wrds_password: str = "",
    company_name: str = "",
    years: int = 5
) -> str:
    """
    直接连接 WRDS 数据库获取财务数据（绕过 Duo 验证）。
    
    Args:
        wrds_username: WRDS 账户用户名（如 university_id）
        wrds_password: WRDS 账户密码
        ticker: 股票代码（如 BYD, TSLA, 002594 等）
        company_name: 公司名称（可选）
        years: 获取最近多少年的数据（默认 5 年）
    
    Returns:
        JSON 格式的财务数据和图表数据
    
    Example:
        wrds_direct_fetch(
            wrds_username="zhangsan@stanford.edu",
            wrds_password="mypassword",
            ticker="BYD",
            company_name="BYD Company Limited"
        )
    """
    ctx = request_context.get() or new_context(method="wrds_direct_fetch")
    
    if not wrds_password:
        return """{
    "status": "error",
    "message": "WRDS password is required. Please provide your WRDS account password."
}"""
    
    try:
        # 创建数据库连接
        conn = _create_wrds_connection(wrds_username, wrds_password)
        
        # 从 Compustat 获取数据
        df = _get_compustat_by_ticker(conn, ticker, years)
        conn.close()
        
        if df.empty:
            return f"""{{
    "status": "error",
    "message": "No data found for ticker '{ticker}' in WRDS Compustat. Please verify the ticker symbol."
}}"""
        
        # 格式化数据
        result = _format_financial_data(df, company_name, ticker)
        import json
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        if "authentication failed" in error_msg.lower():
            return """{
    "status": "error",
    "message": "WRDS authentication failed. Please verify your username and password."
}"""
        elif "could not connect" in error_msg.lower():
            return """{
    "status": "error", 
    "message": "Cannot connect to WRDS server. Please check your network connection."
}"""
        else:
            return f'{{"status": "error", "message": "Database connection error: {error_msg}"}}'
    except Exception as e:
        return f'{{"status": "error", "message": "Unexpected error: {str(e)}"}}'


@tool
def wrds_fetch_crsp_stock_data(
    wrds_username: str,
    wrds_password: str,
    ticker: str,
    start_date: str = "2020-01-01",
    end_date: str = "2024-12-31"
) -> str:
    """
    从 WRDS CRSP 获取股票交易数据（价格、收益率、成交量）。
    
    Args:
        wrds_username: WRDS 账户用户名
        wrds_password: WRDS 账户密码
        ticker: 股票代码（如 BYD, TSLA）
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
    
    Returns:
        JSON 格式的股票数据
    """
    ctx = request_context.get() or new_context(method="wrds_fetch_crsp")
    
    try:
        conn = _create_wrds_connection(wrds_username, wrds_password)
        
        # 获取 permno
        permno_query = f"""
            SELECT permno, comnam
            FROM crsp.msenames
            WHERE ticker = '{ticker}'
            AND namedt <= '{end_date}'
            AND (nameendt IS NULL OR nameendt >= '{start_date}')
            ORDER BY namedt DESC
            LIMIT 1
        """
        permno_df = pd.read_sql(permno_query, conn)
        
        if permno_df.empty:
            conn.close()
            return f'{{"status": "error", "message": "Ticker {ticker} not found in CRSP"}}'
        
        permno = int(permno_df.iloc[0]['permno'])
        company_name = permno_df.iloc[0]['comnam']
        
        # 获取日交易数据
        data_query = f"""
            SELECT date, prc, ret, vol
            FROM crsp.dsf
            WHERE permno = {permno}
            AND date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY date
        """
        df = pd.read_sql(data_query, conn, parse_dates=['date'])
        conn.close()
        
        if df.empty:
            return f'{{"status": "error", "message": "No trading data for {ticker} in date range"}}'
        
        # 格式化数据
        import json
        df['prc'] = df['prc'].abs()
        df['ret'] = df['ret'].astype(float).fillna(0)
        
        result = {
            "status": "success",
            "company_name": company_name,
            "ticker": ticker,
            "data_source": "WRDS CRSP",
            "date_range": f"{start_date} to {end_date}",
            "data": {
                "dates": [d.strftime('%Y-%m-%d') for d in df['date'].tolist()],
                "prices": df['prc'].tolist(),
                "returns": df['ret'].tolist(),
                "volumes": df['vol'].tolist() if 'vol' in df.columns else []
            },
            "summary": {
                "total_trading_days": len(df),
                "avg_price": round(df['prc'].mean(), 2),
                "avg_volume": int(df['vol'].mean()) if 'vol' in df.columns else 0,
                "annual_return": round((1 + df['ret'].mean()) ** 252 - 1, 4) if len(df) > 0 else 0
            }
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except psycopg2.OperationalError as e:
        return f'{{"status": "error", "message": "Database error: {str(e)}"}}'
    except Exception as e:
        return f'{{"status": "error", "message": "{str(e)}"}}'
