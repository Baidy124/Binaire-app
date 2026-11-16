import streamlit as st
import pandas as pd
import numpy as np
import os, base64, time
from datetime import datetime, timezone

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# On essaie d'importer le flux IQ Option, si pas installe ca ne plante pas
try:
    from iqoptionapi.stable_api import IQ_Option
    IQ_LIB_DISPO = True
except ImportError:
    IQ_Option = None
    IQ_LIB_DISPO = False

st.set_page_config(page_title="BINAIRE V3.3 - FLUX IQ", page_icon="📈", layout="wide")
st.title("📈 BINAIRE V3.3 - FLUX IQ OPTION + YAHOO + CAPTURE")

# ================= 1. CHOIX DU FLUX =================
st.sidebar.header("📡 Source du prix")
source = st.sidebar.radio(
    "D'ou vient le prix ?",
    ["🟡 Yahoo Finance (Sans risque, mais pas 100% IQ)", "🔴 Flux IQ Option (Vrai prix IQ, mais risque ban)", "📸 Capture seulement (Tu envoies la photo)"],
    index=0
)
st.sidebar.caption("Conseil : Reste sur Yahoo + Capture pour ne pas te faire bloquer.")

# ================= 2. CONNEXION FLUX IQ OPTION =================
iq_api = None
iq_connecte = False
if source.startswith("🔴"):
    st.sidebar.subheader("🔴 Connexion IQ Option")
    st.sidebar.warning("⚠️ Attention : Ne mets jamais ton vrai compte avec de l'argent. Utilise uniquement un compte DEMO. IQ Option peut bloquer les connexions externes.")
    if not IQ_LIB_DISPO:
        st.sidebar.error("Librairie iqoptionapi pas installee. Mets dans requirements.txt : iqoptionapi")
        st.sidebar.code("iqoptionapi\nstreamlit\nyfinance\npandas\nopenai")
    else:
        iq_email = st.sidebar.text_input("Email IQ Option DEMO", placeholder="ton@email.com")
        iq_mdp = st.sidebar.text_input("Mot de passe DEMO", type="password")
        iq_compte = st.sidebar.selectbox("Compte", ["DEMO", "REEL - NE PAS UTILISER"], index=0)
        if st.sidebar.button("🔌 Connecter au flux IQ"):
            if not iq_email or not iq_mdp:
                st.sidebar.error("Mets email + mot de passe")
            elif iq_compte.startswith("REEL"):
                st.sidebar.error("❌ Je bloque le REEL. Mets DEMO seulement pour tester.")
            else:
                try:
                    with st.spinner("Connexion a IQ Option..."):
                        iq_api = IQ_Option(iq_email, iq_mdp)
                        check, reason = iq_api.connect()
                        if check:
                            iq_api.change_balance("PRACTICE")
                            iq_connecte = True
                            st.session_state["iq_api"] = iq_api
                            st.sidebar.success("✅ Connecte au flux IQ - Compte DEMO")
                        else:
                            st.sidebar.error(f"❌ Echec connexion : {reason}")
                except Exception as e:
                    st.sidebar.error(f"Erreur : {e}")
        # Si deja connecte avant
        if "iq_api" in st.session_state and st.session_state["iq_api"] is not None:
            iq_api = st.session_state["iq_api"]
            try:
                if iq_api.check_connect():
                    iq_connecte = True
                    st.sidebar.success("✅ Flux IQ deja connecte")
            except Exception:
                pass

# ================= 3. CLE OPENAI POUR LIRE CAPTURE =================
st.sidebar.header("🔑 Cle IA pour lire capture")
cle_secrets = None
try:
    cle_secrets = st.secrets.get("OPENAI_API_KEY", None)
except Exception:
    cle_secrets = None
cle_env = os.getenv("OPENAI_API_KEY")
cle_manuelle = st.sidebar.text_input("Colle ta cle OpenAI (sk-...)", value="", type="password", placeholder="sk-proj-xxx")
cle_finale = None
if cle_manuelle and str(cle_manuelle).startswith("sk-"):
    cle_finale = str(cle_manuelle).strip()
elif cle_secrets and str(cle_secrets).startswith("sk-"):
    cle_finale = str(cle_secrets).strip()
elif cle_env and str(cle_env).startswith("sk-"):
    cle_finale = str(cle_env).strip()
client_auto = None
if cle_finale and OpenAI is not None:
    try:
        client_auto = OpenAI(api_key=cle_finale)
    except Exception:
        client_auto = None
CLE_ACTIVE = client_auto is not None
if CLE_ACTIVE:
    st.success("✅ IA ACTIVE - Je peux lire tes captures")
else:
    st.info("ℹ️ IA INACTIVE - Mets ta cle a gauche ou utilise MANUEL.")

# ================= 4. CHOIX PAIRE =================
PAIRES_YAHOO = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "BTC/USD": "BTC-USD",
    "Dollar Index": "DX-Y.NYB"
}
PAIRES_IQ = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "USD/JPY": "USDJPY",
    "AUD/USD": "AUDUSD",
    "EUR/USD OTC": "EURUSD-OTC",
    "GBP/USD OTC": "GBPUSD-OTC"
}

col1, col2 = st.columns(2)
with col1:
    if source.startswith("🔴"):
        paire = st.selectbox("Paire IQ Option", list(PAIRES_IQ.keys()))
        code_iq = PAIRES_IQ[paire]
        code_yahoo = PAIRES_YAHOO.get(paire, "EURUSD=X")
    else:
        paire = st.selectbox("Paire", list(PAIRES_YAHOO.keys()))
        code_yahoo = PAIRES_YAHOO[paire]
        code_iq = ""
with col2:
    mode = st.radio("Mode", ["📊 V2 PRO", "⚡ SCALPING"], index=0, horizontal=True)
    expiration = st.slider("Expiration (mn)", 1, 5, 2) if mode.startswith("⚡") else st.slider("Expiration (mn)", 1, 19, 5)

# ================= 5. FONCTION POUR RECUPERER LES BOUGIES =================
def get_bougies_yahoo(ticker):
    if yf is None:
        return pd.DataFrame()
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        return df
    except Exception:
        return pd.DataFrame()

def get_bougies_iq(api, actif, nb=100):
    # Retourne un DataFrame comme Yahoo mais avec le VRAI flux IQ
    try:
        api.start_candles_stream(actif, 60, nb)
        time.sleep(1)
        candles = api.get_realtime_candles(actif, 60)
        api.stop_candles_stream(actif, 60)
        rows = []
        for ts in sorted(candles.keys()):
            c = candles[ts]
            rows.append({"Open": c["open"], "High": c["max"], "Low": c["min"], "Close": c["close"]})
        df = pd.DataFrame(rows)
        return df
    except Exception as e:
        st.error(f"Erreur flux IQ : {e}")
        return pd.DataFrame()

# ================= 6. AFFICHAGE DU FLUX =================
st.divider()
st.subheader(f"📡 Flux actuel : {source} - {paire}")

df_flux = pd.DataFrame()
prix_actuel = None
source_reelle = ""

if source.startswith("🔴"):
    if iq_connecte and iq_api is not None:
        df_flux = get_bougies_iq(iq_api, code_iq, 100)
        if not df_flux.empty:
            prix_actuel = float(df_flux["Close"].iloc[-1])
            source_reelle = "IQ OPTION - VRAI PRIX"
            st.success(f"✅ Flux IQ : {paire} = {prix_actuel} - {len(df_flux)} bougies 1m")
        else:
            st.warning("Flux IQ vide, on bascule sur Yahoo en secours")
            df_flux = get_bougies_yahoo(code_yahoo)
            source_reelle = "YAHOO SECOURS"
    else:
        st.warning("⚠️ Pas connecte au flux IQ. Clique sur Connecter a gauche, ou choisis Yahoo.")
        df_flux = get_bougies_yahoo(code_yahoo)
        source_reelle = "YAHOO SECOURS"
elif source.startswith("🟡"):
    df_flux = get_bougies_yahoo(code_yahoo)
    if not df_flux.empty:
        prix_actuel = float(df_flux["Close"].iloc[-1])
        source_reelle = "YAHOO - PRIX APPROXIMATIF, PAS CELUI DE IQ"
        st.info(f"🟡 Yahoo : {paire} = {prix_actuel} - Ce prix est proche de IQ mais pas 100% pareil.")
    else:
        st.error("Yahoo ne repond pas. Envoie une capture.")
else:
    st.info("📸 Mode Capture seulement - Envoie ta capture en bas, l'IA lira le vrai prix IQ sur ta photo.")

if not df_flux.empty and prix_actuel is not None:
    st.line_chart(df_flux["Close"].tail(50))
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Prix actuel", f"{prix_actuel:.5f}")
    col_b.metric("Source", source_reelle)
    # 3 dernieres bougies
    last3 = df_flux.tail(3)
    txt = []
    for i, row in last3.iterrows():
        coul = "Verte 🟢" if row["Close"] >= row["Open"] else "Rouge 🔴"
        txt.append(coul)
    col_c.metric("3 dernieres bougies", " / ".join(txt))

# ================= 7. CAPTURE IA =================
st.divider()
st.header(f"📸 Capture - Lecture IA - {paire}")
uploaded = st.file_uploader("Envoie ta capture IQ Option", type=["png", "jpg", "jpeg", "webp"], key="cap_v33")
if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)
    if CLE_ACTIVE:
        if st.button("🧠 ANALYSER MA CAPTURE - LIRE CFO / RSI / WCCI / DPO + FLUX", type="primary", use_container_width=True):
            try:
                mime = uploaded.type or "image/png"
                encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                data_url = f"data:{mime};base64,{encoded}"
                prompt = f"""
Tu es analyste PRO. Actif {paire}. Expiration {expiration} mn. Source prix {source_reelle}.
Lis la capture IQ Option, n'invente rien.
1. 3 dernieres bougies : Verte / Rouge / Doji ?
2. Indicateurs en bas : CFO >0 ou <0 ? RSI >50 ou <50 ? WCCI >0 ou <0 ? DPO si present ?
3. Ichimoku : Prix DESSUS / DESSOUS / DANS nuage ?
4. Compare le prix sur la capture avec le prix flux {prix_actuel} si visible.
Donne : Tableau bougies, Tableau CFO/RSI/WCCI/DPO, Score, CONCLUSION CALL / PUT / ATTENDRE + 2 phrases. Ne garantis jamais un gain.
"""
                with st.spinner("🧠 Lecture..."):
                    resp = client_auto.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}]}],
                        max_tokens=1500
                    )
                    st.markdown(resp.choices[0].message.content)
            except Exception as e:
                st.error(f"Erreur IA : {e}")
    else:
        st.warning("Mets ta cle OpenAI a gauche pour activer la lecture IA.")

st.caption("V3.3 | Yahoo = sans risque. Flux IQ = vrai prix mais risque de ban. Utilise DEMO seulement.")
