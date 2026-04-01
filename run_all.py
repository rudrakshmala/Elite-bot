import subprocess
import time
import sys
import os

def launch():
    print("🔥 Starting Elite-Bot Full-Stack System...")
    
    # 1. Start the Backend Brain (app.py)
    # Using sys.executable ensures we use your (venv)
    backend = subprocess.Popen([sys.executable, "app.py"])
    
    # 2. Wait for Backend to initialize
    print("⏳ Waiting for engines to warm up...")
    time.sleep(5)
    
    # 3. Start the Frontend Dashboard (dashboard.py)
    print("🎨 Launching Streamlit Dashboard...")
    frontend = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "dashboard.py"])
    
    print("\n🚀 SYSTEM ONLINE. Press Ctrl+C in this terminal to stop everything.")
    
    try:
        # Keep the main process alive
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\n🛑 SHUTTING DOWN...")
        backend.terminate()
        frontend.terminate()
        print("👋 All systems stopped.")

if __name__ == "__main__":
    launch()