import config
from alpaca.trading.client import TradingClient

# --- ⚙️ CONNECT ---
client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)

print("--- ⚠️ EMERGENCY RESET: CLEAN SLATE PROTOCOL ---")

try:
    # 1. Cancel All Pending Orders
    print("1️⃣  Cancelling all pending orders...")
    client.cancel_orders()
    print("   ✅ All pending orders cancelled.")

    # 2. Close All Open Positions (Sell Everything)
    print("2️⃣  Closing all open positions (selling everything)...")
    positions = client.get_all_positions()
    
    if len(positions) == 0:
        print("   ✅ No open positions found. You are 100% Cash.")
    else:
        print(f"   ⚠️ Found {len(positions)} positions. Closing now...")
        client.close_all_positions(cancel_orders=True)
        print("   ✅ Sell orders submitted for all positions.")

    print("\n--- 🏁 RESET COMPLETE. YOU ARE BACK TO CASH. ---")

except Exception as e:
    print(f"\n❌ Error during reset: {e}")