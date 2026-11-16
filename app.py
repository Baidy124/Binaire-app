import streamlit as st
import pandas as pd
import numpy as np
import os, base64

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

st.set_page_config(page_title="BINAIRE V3.4 - BOUTON EN HAUT", page_icon="📈", layout="wide")
st.title("📈 BINAIRE V3.4 - TELEPHONE")

# ================= 1. CLE IA =================
st.sidebar.header("🔑 Cle IA")
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
    st.success("✅ IA ACTIVE")
else:
    st.warning("⚠️ Mets ta cle a gauche pour activer le bouton ANALYSER")

# ================= 2. CHOIX PAIRE =================
PAIRES = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "BTC/USD": "BTC-USD",
    "Dollar Index": "DX-Y.NYB"
}
c1, c2 = st.columns(2)
with c1:
    paire = st.selectbox("Paire", list(PAIRES.keys()))
with c2:
    expiration = st.selectbox("Expiration", [1, 2, 3, 5], index=1)

# ================= 3. CAPTURE EN HAUT - BOUTON TOUJOURS VISIBLE =================
st.divider()
st.header(f"📸 1. CAPTURE - {paire}")
st.info("👆 Envoie ta capture ici, le bouton ANALYSER est juste en dessous, pas besoin de descendre.")
uploaded = st.file_uploader("Envoie ta capture IQ Option", type=["png", "jpg", "jpeg", "webp"], key="cap_v34")

if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)

# BOUTON TOUJOURS VISIBLE, MEME SANS PHOTO
if st.button("🧠 ANALYSER MA CAPTURE - LIRE CFO / RSI / WCCI / DPO", type="primary", use_container_width=True):
    if uploaded is None:
        st.error("❌ Envoie d'abord ta capture juste au-dessus, puis re-clique sur ANALYSER.")
    elif not CLE_ACTIVE:
        st.error("❌ Mets d'abord ta cle OpenAI dans la barre a gauche.")
    else:
        try:
            mime = uploaded.type or "image/png"
            encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
            data_url = f"data:{mime};base64,{encoded}"
            prompt = f"""
Tu es analyste PRO. Actif {paire}. Expiration {expiration} mn.
Regarde la capture IQ Option, n'invente rien.
1. 3 dernieres bougies : Verte / Rouge / Doji ?
2. Indicateurs en bas : CFO >0 ou <0 ? RSI >50 ou <50 ? WCCI >0 ou <0 ? DPO si present ?
3. Ichimoku : Prix DESSUS / DESSOUS / DANS nuage ?
4. Moyennes : Verte au-dessus de Rouge ?
Donne : Tableau bougies, Tableau CFO / RSI / WCCI / DPO, Score, CONCLUSION CALL / PUT / ATTENDRE + 2 phrases. Ne garantis jamais un gain. Si tu ne vois pas un chiffre, dis Je ne vois pas.
"""
            with st.spinner("🧠 L'IA lit ta capture... 10-20 sec"):
                resp = client_auto.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}]}],
                    max_tokens=1500
                )
                st.markdown(resp.choices[0].message.content)
                st.success("✅ Lecture terminee")
        except Exception as e:
            st.error(f"Erreur IA : {e}")

# ================= 4. INDICATEURS YAHOO EN GROS =================
st.divider()
st.header(f"📊 2. MES INDICATEURS - {paire} (Yahoo)")

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_cfo(close, period=14):
    # CFO simplifie : (Close - EMA) / EMA * 100
    ema = close.ewm(span=period).mean()
    return (close - ema) / ema * 100

def calc_cci(high, low, close, period=20):
    tp = (high + low + close) / 3
    sma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    return (tp - sma) / (0.015 * md.replace(0, np.nan))

def calc_dpo(close, period=20):
    sma = close.rolling(period).mean()
    return close - sma.shift(period // 2 + 1)

df = pd.DataFrame()
if yf is not None:
    try:
        df = yf.download(PAIRES[paire], period="1d", interval="1m", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
    except Exception:
        df = pd.DataFrame()

if df.empty:
    st.warning("Yahoo ne repond pas. Utilise seulement la capture en haut.")
else:
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    rsi = calc_rsi(close, 7).iloc[-1]
    rsi14 = calc_rsi(close, 14).iloc[-1]
    cfo = calc_cfo(close, 14).iloc[-1]
    wcci = calc_cci(high, low, close, 20).iloc[-1]
    dpo = calc_dpo(close, 20).iloc[-1]
    ema5 = close.ewm(span=5).mean().iloc[-1]
    ema9 = close.ewm(span=9).mean().iloc[-1]
    ema21 = close.ewm(span=21).mean().iloc[-1]
    prix = float(close.iloc[-1])
    # 3 dernieres bougies
    last3 = df.tail(3)
    txt_bougies = []
    for idx, row in last3.iterrows():
        txt_bougies.append("🟢 Verte" if row["Close"] >= row["Open"] else "🔴 Rouge")
    # Affichage en gros
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Prix", f"{prix:.5f}")
    col_b.metric("RSI 7", f"{rsi:.1f}", "CALL si >50" if rsi > 50 else "PUT si <50")
    col_c.metric("CFO", f"{cfo:.2f}", "CALL si >0" if cfo > 0 else "PUT si <0")
    col_d.metric("WCCI", f"{wcci:.1f}", "CALL si >0" if wcci > 0 else "PUT si <0")
    col_e, col_f, col_g, col_h = st.columns(4)
    col_e.metric("DPO", f"{dpo:.5f}", "CALL si >0" if dpo > 0 else "PUT si <0")
    col_f.metric("RSI 14", f"{rsi14:.1f}")
    col_g.metric("EMA 5 / 9 / 21", f"{ema5:.5f} / {ema9:.5f} / {ema21:.5f}")
    col_h.metric("3 Bougies", " | ".join(txt_bougies))
    # Decision simple
    score_call = 0
    score_put = 0
    if rsi > 50:
        score_call += 1
    else:
        score_put += 1
    if cfo > 0:
        score_call += 1
    else:
        score_put += 1
    if wcci > 0:
        score_call += 1
    else:
        score_put += 1
    if dpo > 0:
        score_call += 1
    else:
        score_put += 1
    if ema5 > ema9 > ema21:
        score_call += 1
    elif ema5 < ema9 < ema21:
        score_put += 1
    st.subheader(f"Score Yahoo : 🟢 CALL {score_call} / 🔴 PUT {score_put}")
    if score_call >= 4:
        st.success(f"🟢 CALL {paire} - Yahoo dit CALL")
    elif score_put >= 4:
        st.error(f"🔴 PUT {paire} - Yahoo dit PUT")
    else:
        st.warning(f"🟡 ATTENDRE {paire} - Yahoo pas clair, regarde ta capture en haut")
    st.line_chart(close.tail(50))

st.caption("V3.4 | Bouton ANALYSER en haut. Indicateurs en gros en bas. Mets ta cle a gauche.")
