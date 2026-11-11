import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Binaire - Toutes Paires", layout="centered")
st.title("Binaire - IQ Option / Pocket Option")

# TOUTES LES PAIRES - normal + OTC
PAIRES = {
    # Majeures
    "EUR/USD": "EURUSD=X", "EUR/USD OTC": "EURUSD=X",
    "GBP/USD": "GBPUSD=X", "GBP/USD OTC": "GBPUSD=X",
    "USD/JPY": "USDJPY=X", "USD/JPY OTC": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "USD/CHF OTC": "USDCHF=X",
    "AUD/USD": "AUDUSD=X", "AUD/USD OTC": "AUDUSD=X",
    "NZD/USD": "NZDUSD=X", "NZD/USD OTC": "NZDUSD=X",
    "USD/CAD": "USDCAD=X", "USD/CAD OTC": "USDCAD=X",
    # Mineures / Croisées
    "EUR/GBP": "EURGBP=X", "EUR/GBP OTC": "EURGBP=X",
    "EUR/JPY": "EURJPY=X", "EUR/JPY OTC": "EURJPY=X",
    "EUR/CHF": "EURCHF=X", "EUR/CHF OTC": "EURCHF=X",
    "EUR/AUD": "EURAUD=X", "EUR/AUD OTC": "EURAUD=X",
    "EUR/CAD": "EURCAD=X", "EUR/CAD OTC": "EURCAD=X",
    "EUR/NZD": "EURNZD=X", "EUR/NZD OTC": "EURNZD=X",
    "GBP/JPY": "GBPJPY=X", "GBP/JPY OTC": "GBPJPY=X",
    "GBP/CHF": "GBPCHF=X", "GBP/CHF OTC": "GBPCHF=X",
    "GBP/AUD": "GBPAUD=X", "GBP/AUD OTC": "GBPAUD=X",
    "GBP/CAD": "GBPCAD=X", "GBP/CAD OTC": "GBPCAD=X",
    "AUD/JPY": "AUDJPY=X", "AUD/JPY OTC": "AUDJPY=X",
    "AUD/CAD": "AUDCAD=X", "AUD/CAD OTC": "AUDCAD=X",
    "AUD/CHF": "AUDCHF=X", "AUD/CHF OTC": "AUDCHF=X",
    "CAD/JPY": "CADJPY=X", "CAD/JPY OTC": "CADJPY=X",
    "CHF/JPY": "CHFJPY=X", "CHF/JPY OTC": "CHFJPY=X",
    "NZD/JPY": "NZDJPY=X", "NZD/JPY OTC": "NZDJPY=X",
    "NZD/CAD": "NZDCAD=X", "NZD/CAD OTC": "NZDCAD=X",
    # Exotiques
    "USD/BRL": "USDBRL=X", "USD/BRL OTC": "USDBRL=X",
    "EUR/BRL": "EURBRL=X", "EUR/BRL OTC": "EURBRL=X",
    "USD/MXN": "USDMXN=X", "USD/MXN OTC": "USDMXN=X",
    "USD/ZAR": "USDZAR=X", "USD/ZAR OTC": "USDZAR=X",
    "USD/TRY": "USDTRY=X", "USD/TRY OTC": "USDTRY=X",
    "USD/INR": "USDINR=X", "USD/INR OTC": "USDINR=X",
    "USD/KRW": "USDKRW=X", "USD/KRW OTC": "USDKRW=X",
    "USD/PHP": "USDPHP=X", "USD/PHP OTC": "USDPHP=X",
    "USD/IDR": "USDIDR=X", "USD/IDR OTC": "USDIDR=X",
    # Crypto
    "BTC/USD": "BTC-USD", "BTC/USD OTC": "BTC-USD",
    "ETH/USD": "ETH-USD", "ETH/USD OTC": "ETH-USD",
    "LTC/USD": "LTC-USD", "LTC/USD OTC": "LTC-USD",
    "XRP/USD": "XRP-USD", "XRP/USD OTC": "XRP-USD",
    # Dollar Index - NE PAS OUBLIER
    "Dollar Index (DXY)": "DX-Y.NYB", "Dollar Index OTC": "DX-Y.NYB",
    "USD Index": "DX-Y.NYB", "USD Index OTC": "DX-Y.NYB",
    "DXY": "DX-Y.NYB",
}

paire = st.selectbox("Choisir la paire", list(PAIRES.keys()))

# TEMPS 1mn à 19mn
temps = st.slider("Temps (expiration)", min_value=1, max_value=19, value=5, step=1)
st.write(f"Tu as choisi : **{paire} - {temps} mn**")

if st.button("Vérifier MAINTENANT", type="primary"):
    ticker = PAIRES[paire]
    with st.spinner("Analyse..."):
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty:
            st.error("Pas de données pour cette paire, essaie une autre.")
        else:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"]
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            last_rsi = float(rsi.iloc[-1])
            prix = float(close.iloc[-1])
            ema9 = float(close.ewm(span=9).mean().iloc[-1])
            ema21 = float(close.ewm(span=21).mean().iloc[-1])

            st.metric("Prix actuel", round(prix, 5))
            st.metric("RSI (14)", round(last_rsi, 1))
            st.metric("EMA 9 / 21", f"{round(ema9,5)} / {round(ema21,5)}")

            if last_rsi < 30 and ema9 > ema21:
                st.success(f"🟢 SIGNAL : CALL / HAUSSE pour {temps} mn sur {paire}")
            elif last_rsi > 70 and ema9 < ema21:
                st.error(f"🔴 SIGNAL : PUT / BAISSE pour {temps} mn sur {paire}")
            elif ema9 > ema21:
                st.success(f"🟢 TENDANCE : CALL pour {temps} mn sur {paire}")
            else:
                st.error(f"🔴 TENDANCE : PUT pour {temps} mn sur {paire}")

            st.line_chart(close.tail(60))
            st.caption("Ceci n'est pas un conseil financier. Les paires OTC utilisent le prix de la paire normale comme référence.")
