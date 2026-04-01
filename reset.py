import config
from alpaca.trading.client import TradingClient

client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)

print("--- ☢️ CLOSING ALL POSITIONS & ORDERS ---")
# 1. Cancel waiting orders
client.cancel_orders()
print("✅ Pending Orders Cancelled.")

# 2. Sell all shares
client.close_all_positions(cancel_orders=True)
print("✅ All Positions Closed. You are FLAT.")