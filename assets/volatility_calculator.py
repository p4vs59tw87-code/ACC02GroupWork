# volatility_calculator.py
import pandas as pd
import numpy as np

def calculate_volatility(df, window=30):
    """
    Calculate rolling volatility, maximum drawdown, and Sharpe ratio for a given DataFrame with price data.
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # Daily return calculation
    if 'ret' in df.columns:
        df['daily_return'] = df['ret']
    else:
        df['daily_return'] = df['prc'].pct_change()
    
    # Rolling annualized volatility (window std * sqrt(252))
    df['rolling_volatility'] = df['daily_return'].rolling(window).std() * np.sqrt(252)
    
    # Maximum drawdown
    df['cummax'] = df['prc'].cummax()
    df['drawdown'] = (df['prc'] - df['cummax']) / df['cummax']
    df['max_drawdown'] = df['drawdown'].cummin()
    
    # Sharpe ratio (annualized, risk-free rate = 0)
    avg_daily = df['daily_return'].mean()
    std_daily = df['daily_return'].std()
    sharpe = (avg_daily / std_daily) * np.sqrt(252) if std_daily != 0 else np.nan
    
    df.attrs['sharpe_ratio'] = sharpe
    df.attrs['overall_max_drawdown'] = df['max_drawdown'].min()
    
    # Clean up temporary columns
    df.drop(['cummax', 'drawdown'], axis=1, inplace=True)
    
    return df