
                import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os, base64
from datetime import datetime, timezone

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

st.set_page_config(page_title="BINAIRE V3.2 + LECTURE CAPTURE", page_icon="📈", layout="wide")
st.title("📈 BINAIRE V3.2 - LECTURE CAPTURE")

# ================= 🔑 NOUVEAU : CASE CLÉ D'ACCÈS =================
st.sidebar.header("🔑 Clé d'accès IA")
st.sidebar.info("Colle ta clé OpenAI ici pour que le robot puisse lire tes captures. La clé n'est pas enregistrée dans le code.")

# 1. On essaie d'abord Secrets, puis variable d'environnement, puis la case
cle_secrets = None
try:
    cle_secrets = st.secrets.get("OPENAI_API_KEY", None)
except Exception:
    cle_secrets = None
cle_env = os.getenv("OPENAI_API_KEY")

# 2. La case où TU mets ta clé
cle_manuelle = st.sidebar.text_input(
    "Colle ta clé OpenAI (sk-...) :",
    value="",
    type="password",
    placeholder="sk-proj-xxxxxxxxxxxx",
    help="Tu la trouves sur platform.openai.com -> API Keys"
)

# 3. On choisit la clé : manuelle en priorité, sinon Secrets, sinon env
cle_finale = None
if cle_manuelle and str(cle_manuelle).startswith("sk-"):
    cle_finale = str(cle_manuelle).strip()
    st.sidebar.success("✅ Clé manuelle détectée")
elif cle_secrets and str(cle_secrets).startswith("sk-"):
    cle_finale = str(cle_secrets).strip()
    st.sidebar.success("✅ Clé Secrets détectée")
elif cle_env and str(cle_env).startswith("sk-"):
    cle_finale = str(cle_env).strip()
    st.sidebar.success("✅ Clé Environnement détectée")
else:
    st.sidebar.warning("⚠️ Pas de clé. Mets ta clé ci-dessus pour activer la lecture de capture.")

# 4. On crée le client
client_auto = None
if cle_finale and OpenAI is not None:
    try:
        client_auto = OpenAI(api_key=cle_finale)
    except Exception as e:
        st.sidebar.error(f"Erreur clé : {e}")
        client_auto = None

CLE_ACTIVE = client_auto is not None

if CLE_ACTIVE:
    st.success("✅ IA ACTIVE - Je peux lire tes captures")
else:
    st.info("ℹ️ IA INACTIVE - Mets ta clé dans la barre à gauche, ou utilise le mode MANUEL en bas.")

# Bouton pour tester la clé
if st.sidebar.button("🧪 Tester ma clé"):
    if not CLE_ACTIVE:
        st.sidebar.error("❌ Pas de clé valide. Colle une clé qui commence par sk-")
    else:
        try:
            # Petit test très court
            resp = client_auto.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Dis juste OK"}],
                max_tokens=5
            )
            st.sidebar.success("✅ Ta clé MARCHE ! L'IA peut lire.")
        except Exception as e:
            st.sidebar.error(f"❌ Ta clé ne marche pas : {e}")
            st.sidebar.info("Vérifie : 1) Tu as mis du crédit ? 2) La clé est bien copiée en entier ?")

# ================= ⚙️ NIVEAU =================
NIVEAU_FILTRE = "DOUX"
if NIVEAU_FILTRE == "TRES_DOUX":
    SEUIL_V2PRO = 3; SEUIL_SCALPING = 2; MTF_MIN_ACCORD = 2
    BLOQUER_FAUX_CASSURE = False; BLOQUER_SQUEEZE = False; BLOQUER_VOL_TROP_HAUTE = False; BLOQUER_VOLUME_FAIBLE = False
    NB_DOJI_POUR_BLOQUER = 4; SEUIL_VOLATILITE = 0.000005; DISTANCE_SUPPORT = 0.05; SEUIL_CORPS_BOUGIE = 0.05
elif NIVEAU_FILTRE == "MOYEN":
    SEUIL_V2PRO = 5; SEUIL_SCALPING = 4; MTF_MIN_ACCORD = 3
    BLOQUER_FAUX_CASSURE = True; BLOQUER_SQUEEZE = True; BLOQUER_VOL_TROP_HAUTE = True; BLOQUER_VOLUME_FAIBLE = True
    NB_DOJI_POUR_BLOQUER = 2; SEUIL_VOLATILITE = 0.00002; DISTANCE_SUPPORT = 0.20; SEUIL_CORPS_BOUGIE = 0.12
else:
    SEUIL_V2PRO = 3; SEUIL_SCALPING = 2; MTF_MIN_ACCORD = 2
    BLOQUER_FAUX_CASSURE = False; BLOQUER_SQUEEZE = False; BLOQUER_VOL_TROP_HAUTE = True; BLOQUER_VOLUME_FAIBLE = False
    NB_DOJI_POUR_BLOQUER = 3; SEUIL_VOLATILITE = 0.000008; DISTANCE_SUPPORT = 0.08; SEUIL_CORPS_BOUGIE = 0.06

if "historique" not in st.session_state:
    st.session_state.historique = []

PAIRES = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X", "USD/CHF": "USDCHF=X",
    "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X", "USD/CAD": "USDCAD=X",
    "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X", "EUR/CHF": "EURCHF=X", "EUR/AUD": "EURAUD=X",
    "EUR/CAD": "EURCAD=X", "EUR/NZD": "EURNZD=X",
    "GBP/JPY": "GBPJPY=X", "GBP/CHF": "GBPCHF=X", "GBP/AUD": "GBPAUD=X", "GBP/CAD": "GBPCAD=X",
    "AUD/JPY": "AUDJPY=X", "AUD/CAD": "AUDCAD=X", "AUD/CHF": "AUDCHF=X",
    "CAD/JPY": "CADJPY=X", "CHF/JPY": "CHFJPY=X", "NZD/JPY": "NZDJPY=X", "NZD/CAD": "NZDCAD=X",
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD",
    "Dollar Index (DXY)": "DX-Y.NYB"
}

col_m1, col_m2 = st.columns(2)
with col_m1:
    mode = st.radio("Mode :", [f"📊 V2 PRO - {SEUIL_V2PRO}/6", f"⚡ SCALPING - {SEUIL_SCALPING}/6"], index=0)
with col_m2:
    use_mtf = st.checkbox("✅ 1. Multi-Timeframe + Ichimoku", value=True)
    use_faux = st.checkbox("✅ 2. Faux Cassure", value=True)
    use_vol_intel = st.checkbox("✅ 4. Volatilité", value=True)
    use_volume = st.checkbox("✅ 6. Volume", value=True)
    use_horaire = st.checkbox("✅ 5. Horaire / News", value=True)
    use_ichi = st.checkbox("✅ 7. Ichimoku", value=True)

col1, col2 = st.columns(2)
with col1:
    paire = st.selectbox("Choisir un actif", list(PAIRES.keys()))
with col2:
    expiration = st.slider("Expiration SCALPING", 1, 5, 2) if mode.startswith("⚡") else st.slider("Expiration V2 PRO", 1, 19, 5)

# ========== TOUT LE RESTE DE TON CODE V3.1 - ICHIMOKU + MTF ==========
# ... (tu gardes tout ton code calculer_indicateurs, analyser_ichimoku, analyser_mtf, etc. comme avant) ...
# Pour ne pas tout recopier, garde la partie du milieu de l'ancien code, elle ne change pas.

@st.cache_data(ttl=30)
def recuperer_donnees(ticker, interval="1m", period="1d"):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        cols = ["Open", "High", "Low", "Close"]
        if "Volume" in df.columns:
            cols.append("Volume")
        df = df[cols].copy()
        df = df.dropna(subset=["Open","High","Low","Close"])
        return df
    except Exception:
        return pd.DataFrame()

# ================= 📸 PARTIE CAPTURE - NOUVELLE VERSION QUI LIT VRAIMENT =================
st.divider()
st.header(f"📸 Capture - Lecture IA - {paire} - {expiration} mn")

if not CLE_ACTIVE:
    st.warning("⚠️ Mets ta clé dans la barre à gauche (sidebar) pour activer la lecture IA. Sinon utilise le MANUEL en dessous.")
    mode_capture = "✍️ MANUEL"
else:
    mode_capture = st.radio("Mode capture :", ["🤖 AUTO IA - Lit ta capture IQ Option", "✍️ MANUEL"], index=0, horizontal=True)

uploaded = st.file_uploader("Envoie ta capture IQ Option", type=["png","jpg","jpeg","webp"], key="capture_v32")

if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)

    if mode_capture.startswith("🤖"):
        if not CLE_ACTIVE:
            st.error("❌ Mets d'abord ta clé dans la barre à gauche.")
        else:
            if st.button("🧠 ANALYSER MA CAPTURE - LIRE CFO / RSI / WCCI / DPO", type="primary", use_container_width=True):
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"

                    # 🆕 Prompt simplifié pour que l'IA lise vraiment, comme sur tes photos
                    prompt = f"""
Tu es un analyste PRO. Actif : {paire}. Expiration : {expiration} mn. Niveau {NIVEAU_FILTRE}.

Regarde la capture IQ Option. Lis UNIQUEMENT ce que tu vois, n'invente rien.

1. Lis les 3 dernières bougies sur le graphique principal : Verte ? Rouge ? Doji ?
2. Lis les indicateurs en bas, un par un :
   - CFO (Chande Forecast Oscillator) : valeur ? >0 ou <0 ?
   - RSI (7 ou 8) : valeur ? >50 ou <50 ?
   - WCCI : valeur ? >0 ou <0 ? Et sa timeframe (30m / 1h) ?
   - DPO si présent : valeur ? >0 ou <0 ?
3. Lis Ichimoku si présent : Prix DESSUS nuage ? DESSOUS ? DANS ?
4. Lis les Moyennes : Verte au-dessus de Rouge ? Ou en-dessous ?

Ensuite donne :
- Tableau 3 bougies
- Tableau CFO / RSI / WCCI / DPO
- Score HAUSSE /6 et BAISSE /6
- MTF : 1m, 5m, 15m si visible
- CONCLUSION claire : 🟢 CALL / 🔴 PUT / ⏳ ATTENDRE + pourquoi en 2 phrases.
- Ne garantis jamais un gain.
- Si tu ne vois pas un chiffre, dis "Je ne vois pas" au lieu d'inventer.
"""
                    with st.spinner("🧠 L'IA lit ta capture... (10-20 secondes)"):
                        # 🆕 On utilise gpt-4o qui lit les images, pas gpt-5.5
                        resp = client_auto.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "user", "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}
                                ]}
                            ],
                            max_tokens=1500
                        )
                        st.markdown(resp.choices[0].message.content)
                        st.success("✅ Lecture terminée")
                except Exception as e:
                    st.error(f"Erreur IA : {e}")
                    st.info("Astuce : Si ça dit 'insufficient_quota', c'est que ta clé n'a plus de crédit. Va sur platform.openai.com -> Billing -> Add funds 5$.")
    else:
        # MANUEL - Toujours là en secours
        c1, c2, c3 = st.columns(3)
        b3_m = c1.selectbox("Bougie -3", ["Verte","Rouge","Doji"], key="b3_v32")
        b2_m = c2.selectbox("Bougie -2", ["Verte","Rouge","Doji"], key="b2_v32")
        b1_m = c3.selectbox("Bougie -1", ["Verte","Rouge","Doji"], key="b1_v32")
        vol_m = st.selectbox("Volume", ["Fort","Normal","Faible","Je ne vois pas"], key="vol_v32")
        mtf_m = st.selectbox("5m et 15m ?", ["HAUSSE comme 1m","BAISSE comme 1m","Contraire à 1m","Je ne sais pas"], key="mtf_v32")
        if st.button("🔎 ANALYSER MANUEL - SANS IA", type="primary", use_container_width=True):
            nb_v = [b3_m, b2_m, b1_m].count("Verte")
            nb_r = [b3_m, b2_m, b1_m].count("Rouge")
            if nb_v == 3:
                st.success(f"🟢 CALL {paire} - 3 Soldats Blancs")
            elif nb_r == 3:
                st.error(f"🔴 PUT {paire} - 3 Corbeaux Noirs")
            elif nb_v == 2 and b1_m == "Verte":
                st.success(f"🟢 CALL {paire} - 2 vertes + dernière verte")
            elif nb_r == 2 and b1_m == "Rouge":
                st.error(f"🔴 PUT {paire} - 2 rouges + dernière rouge")
            else:
                st.warning(f"🟡 ATTENDRE {paire} - Pas clair")

st.caption("V3.2 | Mets ta clé dans la sidebar à gauche. Ne partage jamais ta clé à quelqu'un d'autre.")
