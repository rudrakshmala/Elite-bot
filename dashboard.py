import streamlit as st
import requests
import time

st.set_page_config(page_title="Elite-Bot Command", layout="wide", page_icon="🦅")

st.markdown("""
    <style>
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🦅 Elite-Bot Multi-Asset Hub")
st.write("Select your market and initialize your AI Crew.")

def get_data():
    try: return requests.get("http://127.0.0.1:8080/telemetry", timeout=1).json()
    except: return None

def start_bot(market):
    try: requests.post(f"http://127.0.0.1:8080/start/{market}")
    except: pass

data = get_data()

if data:
    # --- 🗂️ TABBED INTERFACE ---
    tab_forex, tab_crypto = st.tabs(["💱 Forex Trading", "🪙 Crypto Trading"])
    
    # --- FOREX WINDOW ---
    with tab_forex:
        st.header("💱 MetaTrader Forex Logic")
        st.write(f"**Status:** {data['forex']['status']}")
        
        if data['forex']['status'] == "💤 Sleeping":
            if st.button("▶️ START FOREX CREW", use_container_width=True, type="primary"):
                start_bot("forex")
                st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1: st.metric("Daily Profit", f"${data['forex']['pnl']:.2f}", delta=f"Goal: ${data['forex']['goal']}")
            with col2: st.info("🤖 CrewAI Agents are actively scanning MT5 charts...")

    # --- CRYPTO WINDOW ---
    with tab_crypto:
        st.header("🪙 Alpaca Crypto Logic")
        st.write(f"**Status:** {data['crypto']['status']}")
        
        if data['crypto']['status'] == "💤 Sleeping":
            if st.button("▶️ START CRYPTO CREW", use_container_width=True, type="primary"):
                start_bot("crypto")
                st.rerun()
        else:
            col1, col2 = st.columns(2)
            with col1: st.metric("Daily Profit", f"${data['crypto']['pnl']:.2f}", delta=f"Goal: ${data['crypto']['goal']}")
            with col2: st.info("🤖 CrewAI Agents are actively scanning Alpaca pairs...")

else:
    st.error("🚨 BACKEND OFFLINE: Connecting to engines...")

# Auto-refresh only if an engine is actually running
if data and ("🟢 Running" in [data['crypto']['status'], data['forex']['status']]):
    time.sleep(3)
    st.rerun()