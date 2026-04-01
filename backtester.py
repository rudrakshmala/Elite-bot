import pandas as pd
import strategy_engine as strategy  # We import your strategy brain

def run_backtest(symbol_a, symbol_b):
    print(f"--- 💰 RUNNING BACKTEST: {symbol_a} vs {symbol_b} ---")
    
    # 1. Get the Strategy Signals
    df = strategy.calculate_pairs_strategy(symbol_a, symbol_b)
    
    if df is None: return

    # 2. Setup Virtual Wallet
    initial_balance = 10000.00  # $10,000 starting cash
    balance = initial_balance
    position = 0  # 0 = No trade, 1 = Long Spread, -1 = Short Spread
    entry_spread = 0.0
    shares = 0
    
    trade_log = [] # To keep track of wins/losses

    # 3. Loop through time (Simulate trading day by day)
    # We iterate through the DataFrame to simulate "live" decisions
    for date, row in df.iterrows():
        
        current_spread = row['Spread']
        signal = row['Signal']
        
        # --- LOGIC TO OPEN TRADES ---
        if position == 0:
            if signal == "BUY_PAIR":
                # Bet that spread will go UP
                position = 1
                entry_spread = current_spread
                # Simple simulation: We buy $5000 worth of the spread
                shares = 5000 / current_spread 
                print(f"[{date.date()}] OPEN LONG (Bet Spread Up) @ {entry_spread:.4f}")

            elif signal == "SELL_PAIR":
                # Bet that spread will go DOWN
                position = -1
                entry_spread = current_spread
                shares = 5000 / current_spread
                print(f"[{date.date()}] OPEN SHORT (Bet Spread Down) @ {entry_spread:.4f}")

        # --- LOGIC TO CLOSE TRADES ---
        elif position != 0:
            # If Signal says EXIT or Signal flips to opposite side
            if signal == "EXIT" or (position == 1 and signal == "SELL_PAIR") or (position == -1 and signal == "BUY_PAIR"):
                
                pnl = 0.0
                
                if position == 1: # We were Long
                    pnl = (current_spread - entry_spread) * shares
                elif position == -1: # We were Short
                    pnl = (entry_spread - current_spread) * shares
                
                balance += pnl
                trade_log.append(pnl)
                
                outcome = "WIN" if pnl > 0 else "LOSS"
                print(f"[{date.date()}] CLOSE POSITION ({outcome}) PnL: ${pnl:.2f}")
                
                # Reset
                position = 0
                entry_spread = 0
                shares = 0

    # 4. Final Results
    print("\n" + "="*30)
    print(f"STARTING BALANCE: ${initial_balance:,.2f}")
    print(f"FINAL BALANCE:    ${balance:,.2f}")
    print(f"TOTAL RETURN:     {((balance - initial_balance) / initial_balance) * 100:.2f}%")
    print(f"TOTAL TRADES:     {len(trade_log)}")
    print("="*30)

if __name__ == "__main__":
    run_backtest("BTC-USD", "ETH-USD")