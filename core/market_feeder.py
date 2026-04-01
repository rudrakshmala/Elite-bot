import yfinance as yf
import pandas as pd
import ta # <--- The new stable library

def get_data(symbol, period="1y", interval="1d"):
    print(f"Fetching data for {symbol}...")
    
    # 1. Fetch Data
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, multi_level_index=False)
    except:
        df = yf.download(symbol, period=period, interval=interval, progress=False)
    
    if df.empty:
        print("Error: No data found.")
        return None

    # 2. Add Elite Indicators using 'ta' library
    
    # RSI (Relative Strength Index) - Momentum
    # We use the built-in class to calculate it and add it as a column
    rsi_indicator = ta.momentum.RSIIndicator(close=df["Close"], window=14)
    df["RSI"] = rsi_indicator.rsi()
    
    # ATR (Average True Range) - Volatility (Risk Management)
    atr_indicator = ta.volatility.AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14)
    df["ATR"] = atr_indicator.average_true_range()
    
    # SMA (Simple Moving Average) - Trend
    sma_indicator = ta.trend.SMAIndicator(close=df["Close"], window=200)
    df["SMA_200"] = sma_indicator.sma_indicator()

    # 3. Clean up (Remove empty rows from the start where indicators are calculating)
    df.dropna(inplace=True)
    
    return df

# --- TEST AREA ---
if __name__ == "__main__":
    symbol = "BTC-USD"
    data = get_data(symbol)
    
    if data is not None:
        print("\nSUCCESS! Data downloaded and indicators calculated.")
        
        last_row = data.iloc[-1]
        print(f"Latest Price: ${last_row['Close']:.2f}")
        print(f"Current RSI: {last_row['RSI']:.2f}")
        print(f"Current Volatility (ATR): {last_row['ATR']:.2f}")
        
        print("\nLast 5 rows of your data:")
        print(data.tail())
    else:
        print("Failed to get data.")