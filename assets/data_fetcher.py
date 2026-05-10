# data_fetcher.py
import psycopg2
import pandas as pd
import streamlit as st

@st.cache_data(ttl=3600)
def fetch_crsp_data(ticker, start_date, end_date, wrds_username, wrds_password):
    """
    Get stock data from WRDS CRSP database for a given ticker and date range.
    Requires the user's WRDS username and password.
    """
    try:
        conn = psycopg2.connect(
            host="wrds-pgdata.wharton.upenn.edu",
            port=9737,
            database="wrds",
            user=wrds_username,
            password=wrds_password
        )
        
        # Use the msenames table to get the permno for the given ticker
        query_permno = f"""
            SELECT permno, ticker, comnam 
            FROM crsp.msenames
            WHERE ticker = '{ticker}'
              AND namedt <= '{end_date}'
              AND (nameendt IS NULL OR nameendt >= '{start_date}')
            ORDER BY namedt DESC
            LIMIT 1
        """
        permno_df = pd.read_sql(query_permno, conn)
        
        if permno_df.empty:
            st.error(f"Stock code {ticker} not found")
            conn.close()
            return pd.DataFrame()
        
        permno = permno_df.iloc[0]['permno']
        company_name = permno_df.iloc[0]['comnam']
        
        # Get daily data
        query_data = f"""
            SELECT date, prc, ret, vol
            FROM crsp.dsf
            WHERE permno = {permno}
              AND date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY date
        """
        df = pd.read_sql(query_data, conn, parse_dates=['date'])
        conn.close()
        
        if df.empty:
            st.warning(f"{ticker} has no data in the selected date range")
            return pd.DataFrame()
        
        df['prc'] = df['prc'].abs()
        df['ret'] = df['ret'].astype(float).fillna(0)
        df.attrs['company_name'] = company_name
        return df
    
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return pd.DataFrame()