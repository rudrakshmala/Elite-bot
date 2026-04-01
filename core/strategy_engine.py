import pandas as pd
import numpy as np
import market_feeder as mf  # We import your previous script!
import config

def calculate_pairs_strategy(symbol_a, symbol_b):
    print(f"--- Analyzing Pair: {symbol_a} vs {symbol_b} ---")

    # 1. Get Data for both assets
    df_a = mf.get_data(symbol_a)
    df_b = mf.get_data(symbol_b)

    if df_a is None or df_b is None:
        print("Error: Could not fetch data for one of the assets.")
        return None

    # 2. Merge Dataframes to align the dates perfectly
    # We rename columns to avoid confusion (e.g., Close_BTC, Close_ETH)
    df = pd.merge(df_a['Close'], df_b['Close'], left_index=True, right_index=True, suffixes=(f'_{symbol_a}', f'_{symbol_b}'))

    # 3. Calculate the Spread (Ratio)
    # How many ETH does 1 BTC buy?
    col_a = f'Close_{symbol_a}'
    col_b = f'Close_{symbol_b}'
    df['Spread'] = df[col_a] / df[col_b]

    # 4. Calculate Z-Score (The "Elite" Indicator)
    # We look at the rolling average of the last 20 days (window=20)
    window = 20
    df['Spread_Mean'] = df['Spread'].rolling(window=window).mean()
    df['Spread_Std'] = df['Spread'].rolling(window=window).std()
    
    # Z-Score formula: (Current Value - Average) / Standard Deviation
    df['Z_Score'] = (df['Spread'] - df['Spread_Mean']) / df['Spread_Std']

    # 5. Generate Signals based on Z-Score
    conditions = [
        (df['Z_Score'] < -1.5),  # Spread is too low -> BUY Ratio (Buy A, Sell B)
        (df['Z_Score'] > 1.5),   # Spread is too high -> SELL Ratio (Sell A, Buy B)
        (abs(df['Z_Score']) < 0.5)  # Spread is normal -> EXIT Positions
    ]
    choices = ['BUY_PAIR', 'SELL_PAIR', 'EXIT']
    df['Signal'] = np.select(conditions, choices, default='HOLD')

    # 6. Fee Filter: only BUY/SELL if expected convergence >= 3x total fees
    FEE_PER_SIDE = config.FEE_PER_SIDE
    FEE_FILTER_MULTIPLIER = 3
    DEFAULT_QTY = 5

    last = df.iloc[-1]
    price_a = last[col_a]
    price_b = last[col_b]
    z = last['Z_Score']
    spread_std = last['Spread_Std']
    sig = last['Signal']

    if pd.notna(spread_std) and spread_std > 0 and pd.notna(price_a) and pd.notna(price_b):
        total_fees = 2 * FEE_PER_SIDE * DEFAULT_QTY * (price_a + price_b)
        expected_convergence = abs(z) * spread_std * DEFAULT_QTY * (price_a + price_b)
        if sig in ('BUY_PAIR', 'SELL_PAIR') and expected_convergence < FEE_FILTER_MULTIPLIER * total_fees:
            df.loc[df.index[-1], 'Signal'] = 'HOLD'

    return df

# --- TEST AREA ---
if __name__ == "__main__":
    # Test with Crypto Duo: Bitcoin vs Ethereum
    sym_a = "BTC-USD"
    sym_b = "ETH-USD"
    
    results = calculate_pairs_strategy(sym_a, sym_b)
    
    if results is not None:
        # Show the last 5 days of analysis
        print("\nLATEST TRADING SIGNALS:")
        print(results[['Spread', 'Z_Score', 'Signal']].tail(10))
        
        # Check the very last signal
        latest_signal = results['Signal'].iloc[-1]
        print(f"\n---> CURRENT ACTION REQUIRED: {latest_signal}")