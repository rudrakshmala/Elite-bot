from alpaca.trading.client import TradingClient
# Line 2 is deleted
import config  # We import your keys from the secure file

def test_connection():
    print("--- 🔌 CONNECTING TO ALPACA... ---")

    try:
        # 1. Initialize the Client
        trading_client = TradingClient(config.API_KEY, config.SECRET_KEY, paper=True)

        # 2. Ask for Account Details
        account = trading_client.get_account()

        # 3. Check if we are active
        if account.status == 'ACTIVE':
            print("\n✅ SUCCESS! CONNECTION ESTABLISHED.")
            print(f"💰 Buying Power: ${float(account.buying_power):,.2f}")
            print(f"💵 Cash:         ${float(account.cash):,.2f}")
            print(f"📉 Portfolio Value: ${float(account.portfolio_value):,.2f}")
            
            # Check if we are blocked from trading
            if account.trading_blocked:
                print("⚠️ WARNING: Trading is currently BLOCKED on this account.")
            else:
                print("🚀 SYSTEM READY: Trading is ENABLED.")
        else:
            print(f"❌ ERROR: Account Status is {account.status}")

    except Exception as e:
        print("\n❌ CRITICAL ERROR: Could not connect.")
        print(f"Reason: {e}")
        print("--> Check if your Keys in config.py are correct.")

if __name__ == "__main__":
    test_connection()