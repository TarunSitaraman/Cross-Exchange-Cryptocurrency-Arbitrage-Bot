import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime

# Page Config (Sleek Dark Mode)
st.set_page_config(
    page_title="QUANTUM | Crypto Arb",
    page_icon="⚡",
    layout="wide",
)

# Premium Custom CSS (Glassmorphism & High-Contrast)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@300;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgb(15, 17, 26) 0%, rgb(5, 7, 10) 90.2%);
    }

    /* Glass Card Style */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 16px;
        padding: 24px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        margin-bottom: 20px;
    }

    div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        color: #00ffa3 !important;
    }

    .status-online { color: #00ffa3; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def load_state():
    state_file = "bot_state.json"
    if not os.path.exists(state_file): return None
    try:
        with open(state_file, "r") as f: return json.load(f)
    except: return None

state = load_state()

# --- HEADER SECTION ---
col_head_1, col_head_2 = st.columns([3, 1])
with col_head_1:
    st.markdown("<h1 style='letter-spacing: -2px; margin-bottom: 0;'>⚡ QUANTUM <span style='color: #555; font-weight: 300;'>ARBITRAGE</span></h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888;'>High-Frequency Cross-Exchange Liquidity Engine</p>", unsafe_allow_html=True)

with col_head_2:
    if state:
        st.markdown(f"<div style='text-align: right; margin-top: 20px;'><span class='status-online'>● SYSTEM LIVE</span><br/><small style='color: #555;'>{state['last_update']}</small></div>", unsafe_allow_html=True)

st.markdown("---")

if state:
    # --- METRICS GRID ---
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("TOTAL REALIZED PNL", f"${state['total_pnl']:.2f}")
    with m2: st.metric("ACTIVE ASSETS", "4 (BTC/ETH/SOL/XRP)")
    with m3: st.metric("AVG LATENCY", "1.2s")
    with m4: st.metric("ARBITRAGE HITS", len(state['trades']))

    # --- MAIN CONTENT GRID ---
    row1_left, row1_right = st.columns([2, 1])

    with row1_left:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.subheader("📈 Multi-Asset Price Dynamics")
        
        if state.get('price_history'):
            df_history = pd.DataFrame(state['price_history'])
            # Since we only track one asset at a time in current state_persistence, 
            # let's visualize the current active one
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_history['timestamp'], y=df_history['binance'], name='Binance', line=dict(color='#00ffa3', width=3)))
            fig.add_trace(go.Scatter(x=df_history['timestamp'], y=df_history['kraken'], name='Kraken', line=dict(color='#ff2d55', width=3)))
            fig.update_layout(
                template="plotly_dark", height=450, 
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="h", x=0, y=1.1)
            )
            st.plotly_chart(fig, width='stretch')
        st.markdown("</div>", unsafe_allow_html=True)

    with row1_right:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.subheader("⚡ System Health")
        
        # Mock Health Analytics
        health_cols = st.columns(2)
        with health_cols[0]:
            st.write("**Binance**")
            st.markdown("<span style='color: #00ffa3;'>Stable 100%</span>", unsafe_allow_html=True)
            st.write("**Kraken**")
            st.markdown("<span style='color: #00ffa3;'>Stable 100%</span>", unsafe_allow_html=True)
        with health_cols[1]:
            st.write("**Coinbase**")
            st.markdown("<span style='color: #00ffa3;'>Stable 100%</span>", unsafe_allow_html=True)
            st.write("**Network**")
            st.markdown("<span style='color: #00ffa3;'>Nominal</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("💰 Exposure")
        for asset, val in state['exposure'].items():
            if val != 0:
                st.write(f"{asset}: `{val:.4f}`")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- RECENT TRADES ---
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📋 Execution Log")
    if state['trades']:
        df_trades = pd.DataFrame(state['trades'])
        st.dataframe(df_trades.sort_values('timestamp', ascending=False), use_container_width=True)
    else:
        st.info("No trades executed in the current session.")
    st.markdown("</div>", unsafe_allow_html=True)

    time.sleep(2)
    st.rerun()

else:
    st.warning("⚡ INITIALIZING QUANTUM ENGINE... PLEASE WAIT.")
    time.sleep(2)
    st.rerun()
