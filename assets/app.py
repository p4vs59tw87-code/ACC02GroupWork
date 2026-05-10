# app.py
import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from src.data_fetcher import fetch_crsp_data
from src.volatility_calculator import calculate_volatility

st.set_page_config(layout="wide")
st.title("📊 Individual Stock Volatility and Risk Analysis board")
st.markdown("Data Source: WRDS CRSP Database")

with st.sidebar:
    st.header("Parameter settings")
    
    # Add WRDS account input fields
    st.subheader("🔐 WRDS Account")
    wrds_user = st.text_input("WRDS username", type="default")
    wrds_pass = st.text_input("WRDS password", type="password")
    
    st.subheader("📈 Stock Parameters")
    ticker = st.text_input("Stock code", "AAPL").upper()
    start_date = st.date_input("Start Date", value=pd.to_datetime("2023-01-01"))
    end_date = st.date_input("End date", value=pd.to_datetime("2024-12-31"))
    window = st.slider("Rolling Window (Days)", 10, 60, 30)
    load_button = st.button("🚀 Load Data")

if load_button:
    # Check if WRDS credentials are provided
    if not wrds_user or not wrds_pass:
        st.error("Please enter your WRDS username and password on the left")
        st.stop()
    
    with st.spinner(f"Fetching {ticker} data from WRDS..."):
        raw_data = fetch_crsp_data(ticker, start_date, end_date, wrds_user, wrds_pass)
    
    if raw_data.empty:
        st.stop()
    
    # No change to the data fetching logic, just pass the raw data to the volatility calculation function
    analyzed_data = calculate_volatility(raw_data, window)
    company_name = analyzed_data.attrs.get('company_name', ticker)
    
    st.header(f"{company_name} ({ticker}) Risk Analysis Report")
    
    # Target metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Latest Price", f"${analyzed_data['prc'].iloc[-1]:.2f}")
    with col2:
        latest_vol = analyzed_data['rolling_volatility'].dropna().iloc[-1]
        st.metric("Latest Annualized Volatility", f"{latest_vol:.2%}")
    with col3:
        sharpe = analyzed_data.attrs.get('sharpe_ratio', np.nan)
        st.metric("Annualized Sharpe Ratio", f"{sharpe:.2f}" if not np.isnan(sharpe) else "N/A")
    with col4:
        mdd = analyzed_data.attrs.get('overall_max_drawdown', np.nan)
        st.metric("Historical Maximum Drawdown", f"{mdd:.2%}")
    
    # Price trend
    st.subheader("📈 Historical Closing Prices")
    fig_price = px.line(analyzed_data, x='date', y='prc', 
                        title=f"{ticker} Closing Price Trend",
                        labels={'date': 'Date', 'prc': 'Price (USD)'})
    st.plotly_chart(fig_price, width='stretch')
    
    # Volatility trend
    st.subheader("📉 Rolling Annualized Volatility")
    fig_vol = px.line(analyzed_data, x='date', y='rolling_volatility',
                      title=f"{window}-Day Rolling Annualized Volatility",
                      labels={'date': 'Date', 'rolling_volatility': 'Annualized Volatility'})
    fig_vol.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig_vol, width='stretch')
    
    # Daily return distribution
    st.subheader("📊 Daily Return Distribution")
    fig_hist = px.histogram(analyzed_data, x='daily_return', nbins=50,
                            title="Daily Return Histogram",
                            labels={'daily_return': 'Daily Return'})
    fig_hist.update_xaxes(tickformat=".1%")
    st.plotly_chart(fig_hist, width='stretch')
    
    # Data table
    with st.expander("View Raw Data"):
        st.dataframe(analyzed_data[['date', 'prc', 'daily_return', 'rolling_volatility']].round(4))

else:
    st.info("👈 Please enter your WRDS credentials and stock parameters on the left, then click \"Load Data\"")