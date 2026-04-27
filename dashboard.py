import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Crypto Arbitrage Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Look
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .stTable {
        background-color: #1e2130;
        border-radius: 10px;
    }
    h1, h2, h3 {
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def load_state():
    state_file = "bot_state.json"
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r") as f:
            return json.load(f)
    except Exception as e:
        return None

# Sidebar
st.sidebar.title("🤖 Bot Control")
st.sidebar.info("Phase 1: BTC/USDT Arbitrage")
is_running = st.sidebar.button("Refresh Data")
st.sidebar.markdown("---")
st.sidebar.write("**Settings**")
st.sidebar.write("- Threshold: 0.05%")
st.sidebar.write("- Mode: Paper Trading")

# Layout
st.title("🚀 Cross-Exchange Arbitrage Monitor")
st.markdown("Real-time arbitrage detection and execution dashboard.")

# Main dashboard loop
state = load_state()

if state:
    # 1. Top Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total PnL (USDT)", f"{state['total_pnl']:.4f}", delta=f"{state['total_pnl']:.4f}")
    with col2:
        num_trades = len(state['trades'])
        st.metric("Total Trades", num_trades)
    with col3:
        exposure_btc = state['exposure'].get('BTC', 0)
        st.metric("Net BTC Exposure", f"{exposure_btc:.6f}")
    with col4:
        st.metric("Bot Status", "ONLINE", delta_color="normal")

    st.markdown("---")

    # 2. Real-time Spreads
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("📊 Price Spreads")
        
        prices = pd.DataFrame({
            'Exchange': ['Binance', 'Kraken'],
            'Bid': [state['binance_best_bid'], state['kraken_best_bid']],
            'Ask': [state['binance_best_ask'], state['kraken_best_ask']]
        })
        
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Best Bid', x=prices['Exchange'], y=prices['Bid'], marker_color='#00ff88'))
        fig.add_trace(go.Bar(name='Best Ask', x=prices['Exchange'], y=prices['Ask'], marker_color='#ff3366'))
        fig.update_layout(
            barmode='group', 
            template="plotly_dark", 
            title="Live Bid-Ask Comparison",
            yaxis=dict(range=[min(prices['Bid'])*0.9995, max(prices['Ask'])*1.0005])
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("🕒 Execution History")
        if state['trades']:
            df_trades = pd.DataFrame(state['trades'])
            df_trades = df_trades[['timestamp', 'actual_net_profit', 'status']]
            st.table(df_trades.tail(5))
        else:
            st.warning("No trades executed yet.")

    # 3. Price History Chart
    st.subheader("📈 Real-Time Price Feed")
    if state.get('price_history'):
        df_history = pd.DataFrame(state['price_history'])
        fig_history = go.Figure()
        fig_history.add_trace(go.Scatter(x=df_history['timestamp'], y=df_history['binance'], name='Binance', line=dict(color='#00ff88', width=2)))
        fig_history.add_trace(go.Scatter(x=df_history['timestamp'], y=df_history['kraken'], name='Kraken', line=dict(color='#ff3366', width=2)))
        fig_history.update_layout(
            template="plotly_dark",
            xaxis_title="Time",
            yaxis_title="Price (USDT)",
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_history, use_container_width=True)

    # 4. PnL Chart
    st.subheader("💰 Cumulative PnL")
    if state['trades']:
        pnl_history = pd.DataFrame(state['trades'])
        pnl_history['cumulative_pnl'] = pnl_history['actual_net_profit'].cumsum()
        fig_pnl = px.line(pnl_history, x='timestamp', y='cumulative_pnl', title="Cumulative Realized Profit")
        fig_pnl.update_layout(template="plotly_dark")
        st.plotly_chart(fig_pnl, use_container_width=True)

    # 4. Refresh Logic (Auto-refresh using streamlit's sleep or just manual)
    st.caption(f"Last updated: {state['last_update']}")
    time.sleep(2)
    st.rerun()

else:
    st.warning("Waiting for bot data... Please make sure `main.py` is running.")
    time.sleep(2)
    st.rerun()
