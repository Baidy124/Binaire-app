import streamlit as st
import pandas as pd
import numpy as np
import time

try:
    import yfinance as yf
except ImportError:
    yf = None

# --- SEUL AJOUT : LE FLUX IQ ---
try:
    from iqoptionapi.stable_api import IQ_Option
    IQ_LIB = True
except ImportError:
    IQ_Option = None
    IQ_LIB = False

st.set_page_config(page_title="BINAIRE V3.5 - SANS CAPTURE", page_icon="📈", layout="wide")
st.title("📈 BINAIRE V3.5 - SANS CAPTURE")
st.info("Pas de photo, pas de cle. Tu choisis ton flux, tu cliques ANALYSER.")

# --- SEUL AJOUT : CHOIX DU FLUX ---
st.sidebar.header("📡 FLUX")
source = st.sidebar.radio("Choisir le flux :", ["🟡 Yahoo Finance", "🔴 Flux IQ Option"], index=0)

iq_api = None
iq_connecte = False
if source.startswith("🔴"):
    st.sidebar.subheader("🔴 Connexion IQ Option DEMO")
    if not IQ_LIB:
        st.sidebar.error("Mets dans requirements.txt : iqoptionapi")
    else:
        iq_email = st.sidebar.text_input("Email IQ DEMO")
        iq_mdp = st.sidebar.text_input("Mot de passe DEMO", type="password")
        if st.sidebar.button("🔌 Connecter au flux IQ"):
            try:
                iq_api = IQ_Option(iq_email, iq_mdp)
                check, reason = iq_api.connect()
                if check:
                    iq_api.change_balance("PRACTICE")
                    st.session_state["iq_api"] = iq_api
                    st.sidebar.success("✅ Connecte - Flux IQ")
                else:
                    st.sidebar.error(f"Echec : {reason}")
            except Exception as e:
                st.sidebar.error(f"Erreur : {e}")
        if "iq_api" in st.session_state and st.session_state["iq_api"] is not None:
            iq_api = st.session_state["iq_api"]
            try:
                if iq_api.check_connect():
                    iq_connecte = True
                    st.sidebar.success("✅ Flux IQ deja connecte")
            except Exception:
                pass

PAIRES_YAHOO = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "BTC/USD": "BTC-USD",
    "Dollar Index": "DX-Y.NYB"
}
PAIRES_IQ = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "USD/JPY": "USDJPY",
    "AUD/USD": "AUDUSD",
    "EUR/JPY": "EURJPY",
    "GBP/JPY": "GBPJPY",
    "EUR/USD OTC": "EURUSD-OTC",
    "GBP/USD OTC": "GBPUSD-OTC"
}

c1, c2 = st.columns(2)
with c1:
    if source.startswith("🔴"):
        paire = st.selectbox("Paire", list(PAIRES_IQ.keys()))
        code_iq = PAIRES_IQ[paire]
        code_yahoo = PAIRES_YAHOO.get(paire, "EURUSD=X")
    else:
        paire = st.selectbox("Paire", list(PAIRES_YAHOO.keys()))
        code_yahoo = PAIRES_YAHOO[paire]
        code_iq = ""
with c2:
    # --- EXPIRATION COMME TU AS DIT : 1 A 19, JE NE TOUCHE PLUS ---
    expiration = st.slider("Expiration (mn)", 1, 19, 2)

st.divider()
if st.button("🧠 ANALYSER - CALL / PUT / ATTENDRE", type="primary", use_container_width=True):
    st.session_state["lancer_analyse"] = True

if st.session_state.get("lancer_analyse", False):
    df = pd.DataFrame()
    nom_flux = ""
    if source.startswith("🔴"):
        if iq_connecte and iq_api is not None:
            try:
                iq_api.start_candles_stream(code_iq, 60, 100)
                time.sleep(1)
                candles = iq_api.get_realtime_candles(code_iq, 60)
                iq_api.stop_candles_stream(code_iq, 60)
                rows = []
                for ts in sorted(candles.keys()):
                    c = candles[ts]
                    rows.append({"Open": c["open"], "High": c["max"], "Low": c["min"], "Close": c["close"]})
                df = pd.DataFrame(rows)
                nom_flux = "IQ OPTION - VRAI PRIX"
            except Exception as e:
                st.error(f"Erreur flux IQ : {e}")
        else:
            st.warning("Pas connecte au flux IQ. Connecte-toi a gauche ou choisis Yahoo.")
    else:
        if yf is not None:
            try:
                df = yf.download(code_yahoo, period="1d", interval="1m", progress=False, auto_adjust=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df = df.dropna()
                nom_flux = "YAHOO"
            except Exception as e:
                st.error(f"Erreur Yahoo : {e}")

    if df.empty:
        st.error("Pas de bougies. Re-clique sur ANALYSER.")
    else:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        def calc_rsi(s, p=14):
            d = s.diff()
            g = d.where(d > 0, 0).rolling(p).mean()
            l = -d.where(d < 0, 0).rolling(p).mean()
            rs = g / l.replace(0, np.nan)
            return 100 - (100 / (1 + rs))
        def calc_cfo(c, p=14):
            ema = c.ewm(span=p).mean()
            return (c - ema) / ema * 100
        def calc_cci(h, l, c, p=20):
            tp = (h + l + c) / 3
            sma = tp.rolling(p).mean()
            md = tp.rolling(p).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
            return (tp - sma) / (0.015 * md.replace(0, np.nan))
        def calc_dpo(c, p=20):
            sma = c.rolling(p).mean()
            return c - sma.shift(p // 2 + 1)
        rsi7 = float(calc_rsi(close, 7).iloc[-1])
        rsi14 = float(calc_rsi(close, 14).iloc[-1])
        cfo = float(calc_cfo(close, 14).iloc[-1])
        wcci = float(calc_cci(high, low, close, 20).iloc[-1])
        dpo = float(calc_dpo(close, 20).iloc[-1])
        ema5 = float(close.ewm(span=5).mean().iloc[-1])
        ema9 = float(close.ewm(span=9).mean().iloc[-1])
        ema21 = float(close.ewm(span=21).mean().iloc[-1])
        prix = float(close.iloc[-1])
        last3 = df.tail(3)
        bougies = []
        for idx, row in last3.iterrows():
            bougies.append("Verte" if row["Close"] >= row["Open"] else "Rouge")
        nb_v = bougies.count("Verte")
        nb_r = bougies.count("Rouge")
        score_call = 0
        score_put = 0
        details = []
        if rsi7 > 50:
            score_call += 1
            details.append("RSI 7 > 50 = CALL")
        else:
            score_put += 1
            details.append("RSI 7 < 50 = PUT")
        if cfo > 0:
            score_call += 1
            details.append("CFO > 0 = CALL")
        else:
            score_put += 1
            details.append("CFO < 0 = PUT")
        if wcci > 0:
            score_call += 1
            details.append("WCCI > 0 = CALL")
        else:
            score_put += 1
            details.append("WCCI < 0 = PUT")
        if dpo > 0:
            score_call += 1
            details.append("DPO > 0 = CALL")
        else:
            score_put += 1
            details.append("DPO < 0 = PUT")
        if ema5 > ema9 > ema21:
            score_call += 1
            details.append("EMA 5>9>21 = CALL")
        elif ema5 < ema9 < ema21:
            score_put += 1
            details.append("EMA 5<9<21 = PUT")
        else:
            details.append("EMA melange = neutre")
        if nb_v == 3:
            score_call += 1
            details.append("3 bougies vertes = CALL")
        elif nb_r == 3:
            score_put += 1
            details.append("3 bougies rouges = PUT")
        st.divider()
        st.subheader(f"Resultat - {paire} - {expiration} mn")
        st.caption(f"Flux utilise : {nom_flux}")
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Prix", f"{prix:.5f}")
        col_b.metric("RSI 7", f"{rsi7:.1f}")
        col_c.metric("CFO", f"{cfo:.2f}")
        col_d.metric("WCCI", f"{wcci:.1f}")
        col_e, col_f, col_g, col_h = st.columns(4)
        col_e.metric("DPO", f"{dpo:.5f}")
        col_f.metric("RSI 14", f"{rsi14:.1f}")
        col_g.metric("EMA 5/9/21", f"{ema5:.4f} / {ema9:.4f} / {ema21:.4f}")
        col_h.metric("3 Bougies", " / ".join(bougies))
        st.write("**Details :**")
        for d in details:
            st.write(f"- {d}")
        st.subheader(f"Score : 🟢 CALL {score_call} - 🔴 PUT {score_put}")
        if score_call >= 4:
            st.success(f"🟢 CALL {paire} - {expiration} mn")
        elif score_put >= 4:
            st.error(f"🔴 PUT {paire} - {expiration} mn")
        else:
            st.warning(f"🟡 ATTENDRE {paire} - Pas clair")
        st.line_chart(close.tail(50))
else:
    st.info("👆 Clique sur le bouton ANALYSER.")

st.caption("V3.5 + FLUX | Sans capture. Expiration 1 a 19.")
