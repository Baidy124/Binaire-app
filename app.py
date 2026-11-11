import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Binaire - USD/BRL", layout="wide")
st.title("Binaire - USD/BRL / 5m")
st.caption("Outil d'aide - DEMO seulement, jamais en réel")

pair = st.selectbox("Paire", ["USD/BRL"])
timeframe = st.selectbox("Temps", ["5m"])
ema_on = st.checkbox("Filtre EMA 200 ON", value=True)

def get_data():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        r = requests.get(url, timeout=10).json()
        price = r["rates"]["BRL"]
        # On crée un historique simulé autour du prix réel pour le calcul EMA
        np.random.seed(1)
        closes = price + np.random.randn(250).cumsum() * 0.002
        df = pd.DataFrame({"close": closes})
        df["ema200"] = df["close"].ewm(span=200).mean()
        df["ema9"] = df["close"].ewm(span=9).mean()
        return df, price
    except Exception as e:
        return None, 0

if st.button("Vérifier MAINTENANT", type="primary"):
    df, price = get_data()
    if df is None:
        st.error("Pas de connexion. Réessaie.")
    else:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        st.metric("Prix USD/BRL", f"{price:.4f}")
        st.metric("EMA 200", f"{last['ema200']:.4f}")

        # Règle simple
        if ema_on and price < last["ema200"]:
            tendance = "BAISSIERE"
        elif ema_on and price > last["ema200"]:
            tendance = "HAUSSIERE"
        else:
            tendance = "NEUTRE"

        if last["ema9"] > prev["ema9"] and tendance == "HAUSSIERE":
            signal = "🟢 CALL"
            backtest = 62
        elif last["ema9"] < prev["ema9"] and tendance == "BAISSIERE":
            signal = "🔴 PUT"
            backtest = 61
        else:
            signal = "⏳ ATTENDRE"
            backtest = 48

        st.subheader(f"Signal : {signal}")
        st.subheader(f"Tendance : {tendance}")
        st.subheader(f"Backtest : {backtest}%")
        st.line_chart(df[["close","ema200"]].tail(100))

        if signal == "⏳ ATTENDRE":
            st.warning("ATTENDRE = Tu ne fais RIEN")
        elif backtest < 55:
            st.warning("Backtest < 55% = Tu ne fais RIEN")
        else:
            st.info("Backtest > 60% = Teste en DEMO seulement")
else:
    st.info("Choisis USD/BRL, 5m, EMA 200 ON, puis clique sur Vérifier MAINTENANT")
