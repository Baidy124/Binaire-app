import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os, base64, uuid, time
from datetime import datetime, timezone, timedelta

st.set_page_config(
    page_title="IQ OPTION AI TRADER DXY V4",
    page_icon="📈",
    layout="wide"
)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

@st.cache_resource
def get_client_auto():
    cle = None
    try:
        cle = st.secrets.get("OPENAI_API_KEY", None)
    except Exception:
        cle = None
    if not cle:
        cle = os.getenv("OPENAI_API_KEY")
    if not cle or not str(cle).startswith("sk-"):
        return None
    try:
        return OpenAI(api_key=str(cle).strip())
    except Exception:
        return None

client_auto = get_client_auto()
CLE_ACTIVE = client_auto is not None

# ================= ⚙️ NIVEAU - MINIMUMS SÉCURISÉS =================
NIVEAU_FILTRE = "DOUX"
SEUIL_V2PRO_MIN = 4
SEUIL_SCALPING_MIN = 3

if NIVEAU_FILTRE == "TRES_DOUX":
    SEUIL_V2PRO = 4; SEUIL_SCALPING = 3; MTF_MIN_ACCORD = 3
    BLOQUER_FAUX_CASSURE = True; BLOQUER_SQUEEZE = False; BLOQUER_VOL_TROP_HAUTE = True; BLOQUER_VOLUME_FAIBLE = False
    NB_DOJI_POUR_BLOQUER = 3; SEUIL_VOLATILITE = 0.000008; DISTANCE_SUPPORT = 0.20; SEUIL_CORPS_BOUGIE = 0.06
elif NIVEAU_FILTRE == "MOYEN":
    SEUIL_V2PRO = 5; SEUIL_SCALPING = 4; MTF_MIN_ACCORD = 3
    BLOQUER_FAUX_CASSURE = True; BLOQUER_SQUEEZE = True; BLOQUER_VOL_TROP_HAUTE = True; BLOQUER_VOLUME_FAIBLE = True
    NB_DOJI_POUR_BLOQUER = 2; SEUIL_VOLATILITE = 0.00002; DISTANCE_SUPPORT = 0.20; SEUIL_CORPS_BOUGIE = 0.12
else:
    SEUIL_V2PRO = 4; SEUIL_SCALPING = 3; MTF_MIN_ACCORD = 3
    BLOQUER_FAUX_CASSURE = True; BLOQUER_SQUEEZE = False; BLOQUER_VOL_TROP_HAUTE = True; BLOQUER_VOLUME_FAIBLE = False
    NB_DOJI_POUR_BLOQUER = 3; SEUIL_VOLATILITE = 0.000008; DISTANCE_SUPPORT = 0.20; SEUIL_CORPS_BOUGIE = 0.06

SEUIL_V2PRO = max(SEUIL_V2PRO, SEUIL_V2PRO_MIN)
SEUIL_SCALPING = max(SEUIL_SCALPING, SEUIL_SCALPING_MIN)

st.title("📈 IQ OPTION AI TRADER DXY V4")
st.caption(f"V4 FINAL CORRIGÉ | Graphique 2m | MTF 2m-5m-15m | V2 PRO {SEUIL_V2PRO}/6 | Scalping {SEUIL_SCALPING}/6 | Historique sauvegardé + Backtest")

# ✅ CORRECTION 16 : Avertissement Yahoo vs IQ Option OTC
st.warning("⚠️ ATTENTION : Ce code utilise Yahoo Finance (marché réel). IQ Option utilise un prix OTC légèrement différent avec 1-2 secondes de délai. Ne clique JAMAIS sans vérifier le graphique IQ Option. Le signal est une aide, pas une garantie. Attends 5 secondes après la fermeture de la bougie avant de trader.")
st.info("💡 Conseil DXY : Si DXY ne marche pas, utilise EUR/USD en miroir. Quand DXY monte, EUR/USD descend en général.")

if CLE_ACTIVE:
    st.success("✅ Clé OpenAI AUTOMATIQUE active")
else:
    st.info("ℹ️ Pas de clé. Capture en MANUEL.")

# ================= ✅ CORRECTION 19 : Historique sauvegardé dans un fichier CSV, pas juste en mémoire =================
FICHIER_HISTORIQUE = "historique_v4.csv"

def charger_historique():
    if os.path.exists(FICHIER_HISTORIQUE):
        try:
            df = pd.read_csv(FICHIER_HISTORIQUE)
            if not df.empty and "ID" in df.columns:
                return df.to_dict("records")
        except Exception:
            return []
    return []

def sauvegarder_historique():
    try:
        if len(st.session_state.historique) > 0:
            pd.DataFrame(st.session_state.historique).to_csv(FICHIER_HISTORIQUE, index=False)
    except Exception:
        pass

if "historique" not in st.session_state:
    st.session_state.historique = charger_historique()
    # Si le fichier existe mais session est vide, on charge
    if len(st.session_state.historique) == 0 and os.path.exists(FICHIER_HISTORIQUE):
        st.session_state.historique = charger_historique()

PAIRES = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X", "USD/CHF": "USDCHF=X",
    "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X", "USD/CAD": "USDCAD=X",
    "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X", "EUR/CHF": "EURCHF=X", "EUR/AUD": "EURAUD=X",
    "EUR/CAD": "EURCAD=X", "EUR/NZD": "EURNZD=X",
    "GBP/JPY": "GBPJPY=X", "GBP/CHF": "GBPCHF=X", "GBP/AUD": "GBPAUD=X", "GBP/CAD": "GBPCAD=X",
    "AUD/JPY": "AUDJPY=X", "AUD/CAD": "AUDCAD=X", "AUD/CHF": "AUDCHF=X",
    "CAD/JPY": "CADJPY=X", "CHF/JPY": "CHFJPY=X", "NZD/JPY": "NZDJPY=X", "NZD/CAD": "NZDCAD=X",
    "USD/BRL": "USDBRL=X", "EUR/BRL": "EURBRL=X", "USD/MXN": "USDMXN=X", "USD/ZAR": "USDZAR=X",
    "USD/TRY": "USDTRY=X", "USD/INR": "USDINR=X",
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "LTC/USD": "LTC-USD", "XRP/USD": "XRP-USD",
    # ✅ CORRECTION 17 : DXY avec ticker de secours
    "Dollar Index (DXY)": "DX-Y.NYB",
    "Dollar Index (DXY) - Secours": "^DXY",
}

# ✅ CORRECTION 17 : Fonction spéciale pour DXY
def recuperer_donnees_avec_secours(ticker, interval="2m", period="1d", paire_nom=""):
    df = recuperer_donnees(ticker, interval=interval, period=period)
    # Si c'est DXY et que ça ne marche pas, on essaie le secours
    if df.empty and paire_nom == "Dollar Index (DXY)":
        st.warning("⚠️ DXY principal (DX-Y.NYB) ne répond pas. J'essaie le ticker de secours ^DXY...")
        df = recuperer_donnees("^DXY", interval=interval, period=period)
        if df.empty:
            st.error("❌ DXY ne marche pas sur Yahoo en 2m. Conseil : Utilise EUR/USD en miroir. Quand DXY monte, EUR/USD descend. C'est plus fiable que DXY sur Yahoo.")
            return df
        else:
            st.success("✅ DXY secours (^DXY) marche.")
    return df

col_m1, col_m2 = st.columns(2)
with col_m1:
    mode = st.radio("Mode :", [f"📊 V2 PRO - {SEUIL_V2PRO}/6", f"⚡ SCALPING - {SEUIL_SCALPING}/6"], index=0)
with col_m2:
    use_mtf = st.checkbox("✅ 1. Multi-Timeframe 2m-5m-15m", value=True)
    use_faux = st.checkbox("✅ 2. Faux Cassure (corrigé)", value=True)
    use_vol_intel = st.checkbox("✅ 4. Volatilité Intelligente", value=True)
    use_volume = st.checkbox("✅ 6. Volume", value=True)
    use_horaire = st.checkbox("✅ 5. Horaire / News", value=True)

col1, col2 = st.columns(2)
with col1:
    paire = st.selectbox("Choisir un actif", list(PAIRES.keys()))
with col2:
    expiration = st.slider("Expiration SCALPING", 1, 5, 2) if mode.startswith("⚡") else st.slider("Expiration V2 PRO", 1, 19, 5)

st.info(f"Actif : {paire} | Mode : {mode} | Expiration : {expiration} mn | Graphique principal : 2m | MTF : 2m-5m-15m")

@st.cache_data(ttl=30)
def recuperer_donnees(ticker, interval="2m", period="1d"):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).strip() for c in df.columns]
        cols = ["Open", "High", "Low", "Close"]
        if "Volume" in df.columns:
            cols.append("Volume")
        if not all(c in df.columns for c in cols[:4]):
            return pd.DataFrame()
        df = df[cols].copy()
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["Open","High","Low","Close"])
        return df
    except Exception:
        return pd.DataFrame()

# ✅ CORRECTION 18 : Utiliser l'heure de Yahoo, pas l'heure du serveur Streamlit
def garder_que_les_bougies_fermees(df, interval="2m"):
    if df is None or df.empty:
        return df
    try:
        # On prend l'heure de la dernière bougie ET l'heure de l'avant-dernière pour calculer le vrai intervalle
        # On utilise l'index de Yahoo, pas datetime.now() du serveur, pour éviter le décalage de 10 secondes
        if len(df) < 2:
            return df
        last_time = df.index[-1]
        prev_time = df.index[-2]
        # Durée réelle entre les 2 dernières bougies (normalement 2 minutes)
        duree_reelle = (last_time - prev_time).total_seconds()
        if duree_reelle <= 0:
            duree_reelle = 120
        # Maintenant, on regarde l'heure actuelle en UTC, mais on compare avec l'heure de Yahoo
        # Si Yahoo est en retard, on ne va pas enlever une bougie déjà fermée
        # On utilise l'heure de Yahoo : la dernière bougie est fermée si la bougie suivante aurait dû commencer
        # On estime l'heure actuelle de Yahoo comme : last_time + duree_reelle
        # Mais on a aussi l'heure du serveur, on prend la plus petite des deux pour être prudent
        now_server = datetime.now(timezone.utc)
        # Convertir last_time en UTC
        if last_time.tzinfo is None:
            last_time_utc = last_time.tz_localize("UTC")
        else:
            last_time_utc = last_time.tz_convert("UTC")
        # Si la dernière bougie a commencé il y a plus que sa durée + 5 secondes de marge, elle est fermée
        # ✅ CORRECTION 16 : On ajoute 5 secondes de marge pour le délai OTC Yahoo -> IQ Option
        age = (now_server - last_time_utc).total_seconds()
        minutes = 2
        if interval == "5m":
            minutes = 5
        elif interval == "15m":
            minutes = 15
        elif interval == "1m":
            minutes = 1
        # On exige age > minutes*60 + 5 secondes (délai OTC)
        if age < minutes * 60 + 5:
            return df.iloc[:-1].copy()
        else:
            return df.copy()
    except Exception:
        return df.iloc[:-1].copy() if len(df) > 1 else df

def calculer_indicateurs(df):
    df = df.copy()
    close = df["Close"]; high = df["High"]; low = df["Low"]
    df["EMA9"] = close.ewm(span=9, adjust=False).mean()
    df["EMA21"] = close.ewm(span=21, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()
    df["EMA5"] = close.ewm(span=5, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    df.loc[(avg_loss == 0) & (avg_gain > 0), "RSI"] = 100
    df.loc[(avg_gain == 0) & (avg_loss > 0), "RSI"] = 0
    avg_gain7 = gain.ewm(alpha=1/7, adjust=False, min_periods=7).mean()
    avg_loss7 = loss.ewm(alpha=1/7, adjust=False, min_periods=7).mean()
    rs7 = avg_gain7 / avg_loss7.replace(0, np.nan)
    df["RSI7"] = 100 - (100 / (1 + rs7))
    df["BB_MID"] = close.rolling(20).mean()
    ecart = close.rolling(20).std()
    df["BB_UPPER"] = df["BB_MID"] + (2 * ecart)
    df["BB_LOWER"] = df["BB_MID"] - (2 * ecart)
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / df["BB_MID"].replace(0, np.nan)
    typical = (high + low + close) / 3
    moyenne = typical.rolling(14).mean()
    deviation = typical.rolling(14).apply(lambda x: np.mean(np.abs(x - np.mean(x))) if len(x) > 0 else np.nan, raw=True)
    df["WCCI"] = ((typical - moyenne) / (0.015 * deviation.replace(0, np.nan)))
    def forecast(x):
        try:
            x = np.array(x, dtype=float)
            x = x[~np.isnan(x)]
            if len(x) < 5:
                return np.nan
            indices = np.arange(len(x))
            coefficients = np.polyfit(indices, x, 1)
            return float(np.polyval(coefficients, len(x) - 1))
        except Exception:
            return np.nan
    prevision = close.rolling(14).apply(forecast, raw=True)
    df["CFO"] = ((close - prevision) / close.replace(0, np.nan)) * 100
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = (df["MACD"] - df["MACD_SIGNAL"])
    previous_close = close.shift(1)
    tr = pd.concat([high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    df["ATR_MOYEN"] = df["ATR"].rolling(50).mean()
    df["SUPPORT"] = low.rolling(30).min().shift(1)
    df["RESISTANCE"] = high.rolling(30).max().shift(1)
    if "Volume" in df.columns:
        df["VOL_MOYEN"] = df["Volume"].rolling(20).mean()
    return df

def decrire_une_bougie(row):
    try:
        o = float(row["Open"]); c = float(row["Close"]); h = float(row["High"]); l = float(row["Low"])
    except Exception:
        return "Invalide", "NEUTRE", 0
    corps = abs(c - o)
    amplitude = h - l
    if amplitude == 0 or np.isnan(amplitude):
        return "Invalide", "NEUTRE", 0
    ratio = corps / amplitude
    if ratio < 0.10:
        return "Doji", "NEUTRE", ratio
    if c > o:
        return ("Verte Forte" if ratio > 0.60 else "Verte"), "HAUSSE", ratio
    else:
        return ("Rouge Forte" if ratio > 0.60 else "Rouge"), "BAISSE", ratio

def analyser_trois_bougies_avance(df):
    if df is None or len(df) < 3:
        return {"liste": [], "figure_3": "Pas assez de bougies", "direction_3": "NEUTRE", "force_3": "Faible", "nb_hausse": 0, "nb_baisse": 0, "nb_doji": 0, "chandelier": "Pas assez de bougies", "direction": "NEUTRE", "derniere_direction": "NEUTRE", "derniere_est_doji": True}
    b3 = df.iloc[-3]; b2 = df.iloc[-2]; b1 = df.iloc[-1]
    desc3, dir3, ratio3 = decrire_une_bougie(b3)
    desc2, dir2, ratio2 = decrire_une_bougie(b2)
    desc1, dir1, ratio1 = decrire_une_bougie(b1)
    def safe_float(x):
        try:
            return round(float(x), 5)
        except Exception:
            return 0.0
    liste = [
        {"Bougie": "Bougie -3", "Type": desc3, "Direction": dir3, "Open": safe_float(b3["Open"]), "Close": safe_float(b3["Close"]), "Corps %": round(ratio3*100,1)},
        {"Bougie": "Bougie -2", "Type": desc2, "Direction": dir2, "Open": safe_float(b2["Open"]), "Close": safe_float(b2["Close"]), "Corps %": round(ratio2*100,1)},
        {"Bougie": "Bougie -1 (dernière fermée)", "Type": desc1, "Direction": dir1, "Open": safe_float(b1["Open"]), "Close": safe_float(b1["Close"]), "Corps %": round(ratio1*100,1)},
    ]
    nb_hausse = sum([1 for d in [dir3, dir2, dir1] if d == "HAUSSE"])
    nb_baisse = sum([1 for d in [dir3, dir2, dir1] if d == "BAISSE"])
    nb_doji = sum([1 for d in [dir3, dir2, dir1] if d == "NEUTRE"])
    figure_3 = "Aucune figure spéciale"; direction_3 = "NEUTRE"; force_3 = "Faible"
    try:
        b3_o = float(b3["Open"]); b3_c = float(b3["Close"]); b1_c = float(b1["Close"]); b2_c = float(b2["Close"])
        b2_o = float(b2["Open"]); b1_o = float(b1["Open"])
        if dir3 == "BAISSE" and ratio3 > 0.5 and dir2 == "NEUTRE" and dir1 == "HAUSSE" and ratio1 > 0.5 and b1_c > (b3_o + b3_c)/2:
            figure_3 = "🌅 Étoile du Matin"; direction_3 = "HAUSSE"; force_3 = "Forte"
        elif dir3 == "HAUSSE" and ratio3 > 0.5 and dir2 == "NEUTRE" and dir1 == "BAISSE" and ratio1 > 0.5 and b1_c < (b3_o + b3_c)/2:
            figure_3 = "🌇 Étoile du Soir"; direction_3 = "BAISSE"; force_3 = "Forte"
        elif dir3 == "BAISSE" and ratio3 > 0.6 and dir2 == "HAUSSE" and b2_o < b3_c and b1_c > b3_o:
            figure_3 = "🤰 Harami Haussier"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
        elif dir3 == "HAUSSE" and ratio3 > 0.6 and dir2 == "BAISSE" and b2_o > b3_c and b1_c < b3_o:
            figure_3 = "🤰 Harami Baissier"; direction_3 = "BAISSE"; force_3 = "Moyenne"
        elif nb_hausse == 3:
            figure_3 = "🟢 3 Soldats Blancs" if b1_c > b2_c > b3_c else "🟢 3 Bougies Vertes"; direction_3 = "HAUSSE"; force_3 = "Forte" if "Soldats" in figure_3 else "Moyenne"
        elif nb_baisse == 3:
            figure_3 = "🔴 3 Corbeaux Noirs" if b1_c < b2_c < b3_c else "🔴 3 Bougies Rouges"; direction_3 = "BAISSE"; force_3 = "Forte" if "Corbeaux" in figure_3 else "Moyenne"
        elif nb_hausse == 2 and nb_baisse == 1 and dir1 == "HAUSSE":
            figure_3 = "🟢 2 Vertes / 1 Rouge - Dernière verte"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
        elif nb_baisse == 2 and nb_hausse == 1 and dir1 == "BAISSE":
            figure_3 = "🔴 2 Rouges / 1 Verte - Dernière rouge"; direction_3 = "BAISSE"; force_3 = "Moyenne"
        elif nb_doji >= 2:
            figure_3 = "🟡 Beaucoup de Doji"; direction_3 = "NEUTRE"; force_3 = "Faible"
        elif dir2 == "BAISSE" and dir1 == "HAUSSE" and b1_c >= b2_o and b1_o <= b2_c:
            figure_3 = "🟢 Englobante Haussière"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
        elif dir2 == "HAUSSE" and dir1 == "BAISSE" and b1_c <= b2_o and b1_o >= b2_c:
            figure_3 = "🔴 Englobante Baissière"; direction_3 = "BAISSE"; force_3 = "Moyenne"
        else:
            corps1 = abs(b1_c - b1_o); amp1 = float(b1["High"]) - float(b1["Low"])
            if amp1 > 0:
                meche_haute = float(b1["High"]) - max(b1_o, b1_c)
                meche_basse = min(b1_o, b1_c) - float(b1["Low"])
                if meche_basse >= corps1 * 2 and meche_haute <= corps1 and dir1 == "HAUSSE":
                    figure_3 = "🔨 Marteau Haussier"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
                elif meche_haute >= corps1 * 2 and meche_basse <= corps1 and dir1 == "BAISSE":
                    figure_3 = "⭐ Étoile Filante"; direction_3 = "BAISSE"; force_3 = "Moyenne"
                elif meche_basse >= corps1 * 2 and meche_haute <= corps1 and dir1 == "BAISSE":
                    figure_3 = "🪦 Pendu"; direction_3 = "BAISSE"; force_3 = "Faible"
                elif meche_haute >= corps1 * 2 and meche_basse <= corps1 and dir1 == "HAUSSE":
                    figure_3 = "🔨 Marteau Inversé"; direction_3 = "HAUSSE"; force_3 = "Faible"
    except Exception:
        pass
    return {"liste": liste, "figure_3": figure_3, "direction_3": direction_3, "force_3": force_3, "nb_hausse": nb_hausse, "nb_baisse": nb_baisse, "nb_doji": nb_doji, "chandelier": figure_3, "direction": direction_3, "derniere_direction": dir1, "derniere_est_doji": (dir1 == "NEUTRE")}

def analyser_mtf(ticker):
    resultats = {}
    for interval, period in [("2m","1d"), ("5m","5d"), ("15m","5d")]:
        try:
            df = recuperer_donnees(ticker, interval=interval, period=period)
            if df.empty or len(df) < 50:
                resultats[interval] = "NEUTRE"; continue
            df = calculer_indicateurs(df)
            df = garder_que_les_bougies_fermees(df, interval=interval)
            df = df.dropna(subset=["RSI","EMA50"])
            if df.empty:
                resultats[interval] = "NEUTRE"; continue
            c = df.iloc[-1]
            if pd.isna(c["EMA9"]) or pd.isna(c["EMA21"]) or pd.isna(c["RSI"]):
                resultats[interval] = "NEUTRE"; continue
            if float(c["EMA9"]) > float(c["EMA21"]) and float(c["RSI"]) > 50:
                resultats[interval] = "HAUSSE"
            elif float(c["EMA9"]) < float(c["EMA21"]) and float(c["RSI"]) < 50:
                resultats[interval] = "BAISSE"
            else:
                resultats[interval] = "NEUTRE"
        except Exception:
            resultats[interval] = "NEUTRE"
    nb_h = list(resultats.values()).count("HAUSSE"); nb_b = list(resultats.values()).count("BAISSE"); nb_n = list(resultats.values()).count("NEUTRE")
    if nb_h > 0 and nb_b > 0:
        accord = f"🔴 CONFLIT MTF - 2m={resultats.get('2m')}, 5m={resultats.get('5m')}, 15m={resultats.get('15m')} - On ne trade pas quand les timeframes se contredisent."
        direction_mtf = "CONFLIT"
    elif nb_h == 3:
        accord = "✅ ACCORD TOTAL HAUSSE (2m + 5m + 15m)"; direction_mtf = "HAUSSE"
    elif nb_b == 3:
        accord = "✅ ACCORD TOTAL BAISSE (2m + 5m + 15m)"; direction_mtf = "BAISSE"
    elif nb_h == 2 and nb_n == 1:
        accord = "🟡 Accord HAUSSE 2/3 + 1 Neutre - OK, pas de conflit"; direction_mtf = "HAUSSE"
    elif nb_b == 2 and nb_n == 1:
        accord = "🟡 Accord BAISSE 2/3 + 1 Neutre - OK, pas de conflit"; direction_mtf = "BAISSE"
    elif nb_h == 1 and nb_n == 2:
        accord = "🟡 Faible HAUSSE 1/3 - Pas assez fort"; direction_mtf = "NEUTRE"
    elif nb_b == 1 and nb_n == 2:
        accord = "🟡 Faible BAISSE 1/3 - Pas assez fort"; direction_mtf = "NEUTRE"
    else:
        accord = "🟡 MTF Neutre"; direction_mtf = "NEUTRE"
    return {"details": resultats, "accord": accord, "direction": direction_mtf, "nb_h": nb_h, "nb_b": nb_b}

def detecter_faux_cassure(df):
    if df is None or len(df) < 6:
        return {"faux": False, "texte": "Pas assez de données"}
    try:
        faux_hausse = False; faux_baisse = False; details = []
        for i in range(-6, -1):
            row = df.iloc[i]
            res_i = float(row["RESISTANCE"]) if pd.notna(row["RESISTANCE"]) else np.nan
            sup_i = float(row["SUPPORT"]) if pd.notna(row["SUPPORT"]) else np.nan
            close_i = float(row["Close"])
            if i + 1 < 0:
                row_next = df.iloc[i+1]
                close_next = float(row_next["Close"])
                if pd.notna(res_i) and close_i > res_i and close_next < res_i:
                    faux_hausse = True
                    details.append(f"Bougie {i} a cassé Résistance {res_i:.5f} puis est revenue à {close_next:.5f}")
                if pd.notna(sup_i) and close_i < sup_i and close_next > sup_i:
                    faux_baisse = True
                    details.append(f"Bougie {i} a cassé Support {sup_i:.5f} puis est revenue à {close_next:.5f}")
        if faux_hausse:
            return {"faux": True, "texte": "⚠️ FAUX BREAKOUT HAUSSIER - " + " | ".join(details), "type": "FAUX_HAUSSE"}
        if faux_baisse:
            return {"faux": True, "texte": "⚠️ FAUX BREAKOUT BAISSIER - " + " | ".join(details), "type": "FAUX_BAISSE"}
        return {"faux": False, "texte": "✅ Pas de faux breakout - Cassure propre (vérifiée avec les niveaux de chaque bougie).", "type": "OK"}
    except Exception as e:
        return {"faux": False, "texte": f"✅ Pas de faux breakout (erreur calcul : {e}).", "type": "OK"}

def analyser_volatilite_intelligente(df):
    try:
        c = df.iloc[-1]
        atr = float(c["ATR"]) if pd.notna(c["ATR"]) else np.nan
        atr_moyen = float(c["ATR_MOYEN"]) if pd.notna(c["ATR_MOYEN"]) else np.nan
        bb_width = float(c["BB_WIDTH"]) if pd.notna(c["BB_WIDTH"]) else np.nan
        bb_moyen_series = df["BB_WIDTH"].rolling(50).mean()
        bb_moyen = float(bb_moyen_series.iloc[-1]) if len(bb_moyen_series) > 0 and pd.notna(bb_moyen_series.iloc[-1]) else np.nan
        if np.isnan(atr) or np.isnan(atr_moyen) or np.isnan(bb_width) or np.isnan(bb_moyen):
            return {"statut": "NEUTRE", "texte": "Volatilité : Données insuffisantes"}
        if bb_width < bb_moyen * 0.7:
            return {"statut": "SQUEEZE", "texte": f"🟡 SQUEEZE : Bandes serrées ({bb_width:.4f} vs {bb_moyen:.4f})"}
        if atr > atr_moyen * 1.8:
            return {"statut": "TROP_HAUTE", "texte": f"🔴 Volatilité TROP HAUTE : ATR {atr:.5f} vs {atr_moyen:.5f}."}
        if atr < atr_moyen * 0.5:
            return {"statut": "TROP_BASSE", "texte": f"🟡 Volatilité TROP BASSE : ATR {atr:.5f} vs {atr_moyen:.5f}."}
        return {"statut": "NORMALE", "texte": f"✅ Volatilité NORMALE : ATR {atr:.5f} vs {atr_moyen:.5f}."}
    except Exception:
        return {"statut": "NEUTRE", "texte": "Volatilité : Erreur calcul"}

def analyser_horaire():
    now = datetime.now(timezone.utc); heure = now.hour; jour = now.weekday()
    avertissements = []
    if jour == 6:
        avertissements.append("🔴 DIMANCHE : Marché fermé.")
    if jour == 5 and heure >= 20:
        avertissements.append("🟡 SAMEDI SOIR GMT : Marché va fermer.")
    if 12 <= heure < 14:
        avertissements.append("🟡 12h-14h GMT : Pause déjeuner - Faux signaux possibles.")
    if heure in [8, 14] or (heure == 13 and now.minute >= 30):
        avertissements.append("⚠️ HEURE DE NEWS : 8h30 / 14h30 GMT = NFP, CPI, FOMC.")
    if 0 <= heure < 6:
        avertissements.append("🟡 00h-06h GMT : Session Asie seule.")
    if 7 <= heure < 10:
        avertissements.append("✅ 07h-10h GMT : Ouverture Londres - Bonne volatilité.")
    if 13 <= heure < 17:
        avertissements.append("✅ 13h-17h GMT : Londres + New York - Meilleure volatilité.")
    if not avertissements:
        avertissements.append(f"✅ Heure OK : {now.strftime('%H:%M')} GMT")
    return {"heure_gmt": now.strftime("%H:%M GMT"), "jour": ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][jour], "avertissements": avertissements}

def analyser_volume(df):
    if "Volume" not in df.columns:
        return {"statut": "SANS_VOLUME", "texte": "⚠️ Pas de volume pour cet actif."}
    try:
        c = df.iloc[-1]
        vol = float(c["Volume"]) if pd.notna(c["Volume"]) else np.nan
        vol_moyen = float(c["VOL_MOYEN"]) if pd.notna(c["VOL_MOYEN"]) else np.nan
        if np.isnan(vol) or np.isnan(vol_moyen) or vol_moyen == 0:
            return {"statut": "NEUTRE", "texte": "Volume : Données insuffisantes"}
        ratio = vol / vol_moyen
        if ratio > 1.5:
            return {"statut": "FORT", "texte": f"✅ Volume FORT : {ratio:.2f}x", "ratio": ratio}
        if ratio < 0.7:
            return {"statut": "FAIBLE", "texte": f"⚠️ Volume FAIBLE : {ratio:.2f}x", "ratio": ratio}
        return {"statut": "NORMAL", "texte": f"✅ Volume NORMAL : {ratio:.2f}x", "ratio": ratio}
    except Exception:
        return {"statut": "NEUTRE", "texte": "Volume : Erreur calcul"}

def analyser_signal_v3_corrige(df, ticker, is_scalping=False, use_mtf=True, use_faux=True, use_vol_intel=True, use_volume=True, mtf_precalcule=None):
    c = df.iloc[-1]
    prix = float(c["Close"]); atr = float(c["ATR"]) if pd.notna(c["ATR"]) else 0.0
    support = float(c["SUPPORT"]) if pd.notna(c["SUPPORT"]) else np.nan
    resistance = float(c["RESISTANCE"]) if pd.notna(c["RESISTANCE"]) else np.nan
    proche_support = (pd.notna(support) and atr > 0 and abs(prix - support) <= atr * 0.20)
    proche_resistance = (pd.notna(resistance) and atr > 0 and abs(resistance - prix) <= atr * 0.20)
    tendance_haussiere = (float(c["EMA9"]) > float(c["EMA21"]) > float(c["EMA50"]))
    tendance_baissiere = (float(c["EMA9"]) < float(c["EMA21"]) < float(c["EMA50"]))
    indicateurs_haut = [tendance_haussiere, 50 < float(c["RSI"]) < 70, float(c["WCCI"]) > 0, float(c["CFO"]) > 0, float(c["MACD_HIST"]) > 0, prix > float(c["BB_MID"])]
    indicateurs_bas = [tendance_baissiere, 30 < float(c["RSI"]) < 50, float(c["WCCI"]) < 0, float(c["CFO"]) < 0, float(c["MACD_HIST"]) < 0, prix < float(c["BB_MID"])]
    info_3 = analyser_trois_bougies_avance(df)
    chandelier = info_3["chandelier"]; direction = info_3["direction"]
    derniere_direction = info_3.get("derniere_direction", "NEUTRE")
    derniere_est_doji = info_3.get("derniere_est_doji", True)
    score_haut = sum(indicateurs_haut); score_bas = sum(indicateurs_bas)
    volatilite_faible = (pd.isna(atr) or atr <= 0 or (atr / prix < SEUIL_VOLATILITE if prix != 0 else True))
    derniere = df.iloc[-1]
    amp_der = float(derniere["High"]) - float(derniere["Low"]); corps_der = abs(float(derniere["Close"]) - float(derniere["Open"]))
    bougie_faible = (amp_der <= 0 or corps_der / amp_der < SEUIL_CORPS_BOUGIE)
    trop_de_doji = (info_3["nb_doji"] >= NB_DOJI_POUR_BLOQUER)
    seuil = SEUIL_SCALPING if is_scalping else SEUIL_V2PRO
    # Pour le backtest, on ne veut pas rappeler l'API MTF à chaque bougie, on utilise le MTF précalculé si fourni
    if mtf_precalcule is not None:
        mtf = mtf_precalcule
    else:
        mtf = analyser_mtf(ticker) if use_mtf else {"direction": "NEUTRE", "accord": "MTF OFF", "details": {}}
    faux = detecter_faux_cassure(df) if use_faux else {"faux": False, "texte": "Faux OFF"}
    vol_intel = analyser_volatilite_intelligente(df) if use_vol_intel else {"statut": "NEUTRE", "texte": "Volatilité OFF"}
    vol = analyser_volume(df) if use_volume else {"statut": "NEUTRE", "texte": "Volume OFF"}
    base = {"score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol, "derniere_direction": derniere_direction, "derniere_est_doji": derniere_est_doji}
    if faux["faux"] and BLOQUER_FAUX_CASSURE:
        return {"signal": "ATTENDRE", "raison": f"FAUX CASSURE CORRIGÉ : {faux['texte']}", **base}
    if vol_intel["statut"] == "SQUEEZE" and BLOQUER_SQUEEZE:
        return {"signal": "ATTENDRE", "raison": f"VOLATILITÉ SQUEEZE : {vol_intel['texte']}", **base}
    if vol_intel["statut"] == "TROP_HAUTE" and BLOQUER_VOL_TROP_HAUTE:
        return {"signal": "ATTENDRE", "raison": f"VOLATILITÉ TROP HAUTE : {vol_intel['texte']}", **base}
    if mtf["direction"] == "CONFLIT":
        return {"signal": "ATTENDRE", "raison": f"MTF CONFLIT CORRIGÉ : {mtf['accord']}", **base}
    if volatilite_faible:
        return {"signal": "ATTENDRE", "raison": "Filtre : Volatilité trop faible", **base}
    if trop_de_doji:
        return {"signal": "ATTENDRE", "raison": f"Filtre : {info_3['nb_doji']} Doji", **base}
    if bougie_faible and direction == "NEUTRE":
        return {"signal": "ATTENDRE", "raison": "Filtre : Bougie trop petite + neutre", **base}
    if vol.get("statut") == "FAIBLE" and BLOQUER_VOLUME_FAIBLE:
        return {"signal": "ATTENDRE", "raison": f"VOLUME : {vol['texte']}", **base}
    if mtf["direction"] == "HAUSSE" and score_bas >= 5 and score_haut <= 1:
        return {"signal": "ATTENDRE", "raison": "MTF : Totalement opposé", **base}
    if mtf["direction"] == "BAISSE" and score_haut >= 5 and score_bas <= 1:
        return {"signal": "ATTENDRE", "raison": "MTF : Totalement opposé", **base}
    if is_scalping:
        scalp_haut_rapide = (float(c["EMA5"]) > float(c["EMA9"]) and float(c["RSI7"]) > 50)
        scalp_bas_rapide = (float(c["EMA5"]) < float(c["EMA9"]) and float(c["RSI7"]) < 50)
        if score_haut >= seuil and scalp_haut_rapide and not proche_resistance:
            if derniere_est_doji:
                return {"signal": "ATTENDRE", "raison": "SCALPING : Dernière bougie est un Doji - Confirmation obligatoire.", **base}
            if derniere_direction != "HAUSSE":
                return {"signal": "ATTENDRE", "raison": f"SCALPING : Dernière bougie est {derniere_direction}, pas HAUSSE.", **base}
            return {"signal": "CALL / HAUSSE", "raison": f"SCALPING CORRIGÉ : {score_haut}/6 + EMA5 + RSI7 + MTF {mtf['direction']} + Dernière bougie HAUSSE confirmée + {chandelier}", **{**base, "direction": "HAUSSE"}}
        if score_bas >= seuil and scalp_bas_rapide and not proche_support:
            if derniere_est_doji:
                return {"signal": "ATTENDRE", "raison": "SCALPING : Dernière bougie est un Doji.", **base}
            if derniere_direction != "BAISSE":
                return {"signal": "ATTENDRE", "raison": f"SCALPING : Dernière bougie est {derniere_direction}, pas BAISSE.", **base}
            return {"signal": "PUT / BAISSE", "raison": f"SCALPING CORRIGÉ : {score_bas}/6 + EMA5 + RSI7 + MTF {mtf['direction']} + Dernière bougie BAISSE confirmée + {chandelier}", **{**base, "direction": "BAISSE"}}
        return {"signal": "ATTENDRE", "raison": f"SCALPING : Pas {seuil}/6 + EMA5/RSI7 + Confirmation bougie.", **base}
    if score_haut >= seuil and not proche_resistance:
        if derniere_est_doji:
            return {"signal": "ATTENDRE", "raison": "V2 PRO : Dernière bougie est un Doji.", **base}
        if derniere_direction != "HAUSSE":
            return {"signal": "ATTENDRE", "raison": f"V2 PRO : Dernière bougie est {derniere_direction}, pas HAUSSE.", **base}
        return {"signal": "CALL / HAUSSE", "raison": f"V2 PRO CORRIGÉ : {score_haut}/6 HAUSSE + MTF {mtf['direction']} + Dernière bougie HAUSSE confirmée + {chandelier}", **{**base, "direction": "HAUSSE"}}
    if score_bas >= seuil and not proche_support:
        if derniere_est_doji:
            return {"signal": "ATTENDRE", "raison": "V2 PRO : Dernière bougie est un Doji.", **base}
        if derniere_direction != "BAISSE":
            return {"signal": "ATTENDRE", "raison": f"V2 PRO : Dernière bougie est {derniere_direction}, pas BAISSE.", **base}
        return {"signal": "PUT / BAISSE", "raison": f"V2 PRO CORRIGÉ : {score_bas}/6 BAISSE + MTF {mtf['direction']} + Dernière bougie BAISSE confirmée + {chandelier}", **{**base, "direction": "BAISSE"}}
    if score_haut >= seuil and proche_resistance:
        return {"signal": "ATTENDRE", "raison": "Filtre : Collé à la Résistance (abs <= 0.20 x ATR)", **base}
    if score_bas >= seuil and proche_support:
        return {"signal": "ATTENDRE", "raison": "Filtre : Collé au Support (abs <= 0.20 x ATR)", **base}
    return {"signal": "ATTENDRE", "raison": f"Filtre : Pas {seuil}/6 - HAUSSE {score_haut}, BAISSE {score_bas}", **base}

# ✅ CORRECTION 20 : BACKTEST - Tester sur le passé avant de mettre de l'argent réel
def faire_backtest(ticker, paire_nom, is_scalping=False, nb_jours=7):
    """
    On rejoue la stratégie sur les 7 derniers jours en 2m.
    Pour chaque bougie, on calcule le signal, puis on regarde si la bougie suivante (expiration) a bien monté/descendu.
    Si on a dit CALL et que le prix 2 minutes après est plus haut, c'est GAGNÉ.
    """
    try:
        df = recuperer_donnees(ticker, interval="2m", period="5d")
        if df.empty or len(df) < 200:
            return None, "Pas assez de données pour le backtest (il faut 5 jours en 2m)."
        df = calculer_indicateurs(df)
        # On enlève les 100 premières lignes pour que les indicateurs soient stables
        df = df.iloc[100:].copy()
        df = df.dropna(subset=["RSI","WCCI","CFO","MACD_HIST","ATR","BB_MID","EMA50"])
        if len(df) < 50:
            return None, "Pas assez de données après calcul des indicateurs."
        nb_gagne = 0; nb_perdu = 0; nb_attendre = 0
        details = []
        # On teste toutes les bougies sauf les 3 dernières (on a besoin de voir le futur)
        # Expiration 2 minutes = 1 bougie 2m après. Pour V2 PRO 5 min = 2-3 bougies après, on prend 2 bougies pour simplifier.
        pas_expiration = 1 if is_scalping else 2
        for i in range(60, len(df) - pas_expiration - 1):
            sous_df = df.iloc[:i+1].copy()
            # Pour le backtest, on ne veut pas appeler l'API MTF à chaque fois, on met MTF neutre pour aller vite
            # On garde les autres filtres qui sont les plus importants
            res = analyser_signal_v3_corrige(sous_df, ticker, is_scalping=is_scalping, use_mtf=False, use_faux=True, use_vol_intel=True, use_volume=True, mtf_precalcule={"direction": "NEUTRE", "accord": "Backtest MTF OFF", "details": {}})
            signal = res["signal"]
            if signal == "ATTENDRE":
                nb_attendre += 1
                continue
            prix_entree = float(df.iloc[i]["Close"])
            prix_sortie = float(df.iloc[i + pas_expiration]["Close"])
            gagne = False
            if signal == "CALL / HAUSSE" and prix_sortie > prix_entree:
                gagne = True
            if signal == "PUT / BAISSE" and prix_sortie < prix_entree:
                gagne = True
            if gagne:
                nb_gagne += 1
            else:
                nb_perdu += 1
            if len(details) < 20:
                details.append({"Bougie": str(df.index[i]), "Signal": signal, "Prix Entrée": round(prix_entree,5), "Prix Sortie": round(prix_sortie,5), "Résultat": "GAGNÉ" if gagne else "PERDU"})
        total = nb_gagne + nb_perdu
        taux = (nb_gagne / total * 100) if total > 0 else 0
        return {"nb_gagne": nb_gagne, "nb_perdu": nb_perdu, "nb_attendre": nb_attendre, "total_trades": total, "taux": taux, "details": details}, None
    except Exception as e:
        return None, f"Erreur backtest : {e}"

if use_horaire:
    horaire = analyser_horaire()
    st.subheader(f"🕐 Horaire / News - {horaire['jour']} {horaire['heure_gmt']}")
    for av in horaire["avertissements"]:
        if av.startswith("🔴"):
            st.error(av)
        elif av.startswith("⚠️") or av.startswith("🟡"):
            st.warning(av)
        else:
            st.success(av)

# ✅ CORRECTION 20 : Bouton BACKTEST
st.divider()
st.header("🧪 BACKTEST - Teste avant de mettre de l'argent réel")
st.info("Le backtest rejoue ta stratégie sur les 5 derniers jours en 2m. Si ton taux est en dessous de 55%, ne passe pas en réel.")
if st.button("🧪 LANCER LE BACKTEST 5 JOURS - V4 CORRIGÉ", type="secondary"):
    is_scalp_bt = mode.startswith("⚡")
    with st.spinner("Backtest en cours... ça peut prendre 30 secondes..."):
        ticker_bt = PAIRES[paire]
        # Pour DXY, on utilise le secours si besoin
        if paire == "Dollar Index (DXY)":
            df_test = recuperer_donnees(ticker_bt, interval="2m", period="1d")
            if df_test.empty:
                ticker_bt = "^DXY"
        resultat_bt, erreur_bt = faire_backtest(ticker_bt, paire, is_scalping=is_scalp_bt)
        if erreur_bt:
            st.error(erreur_bt)
        else:
            col_b1, col_b2, col_b3, col_b4 = st.columns(4)
            with col_b1:
                st.metric("Trades testés", resultat_bt["total_trades"])
            with col_b2:
                st.metric("✅ GAGNÉ", resultat_bt["nb_gagne"])
            with col_b3:
                st.metric("❌ PERDU", resultat_bt["nb_perdu"])
            with col_b4:
                st.metric("🏆 Taux Backtest", f"{resultat_bt['taux']:.1f}%")
            if resultat_bt["taux"] >= 60:
                st.success(f"✅ Bon backtest : {resultat_bt['taux']:.1f}% - Tu peux tester en démo.")
            elif resultat_bt["taux"] >= 55:
                st.warning(f"🟡 Backtest moyen : {resultat_bt['taux']:.1f}% - Prudence, teste en démo d'abord.")
            else:
                st.error(f"🔴 Backtest faible : {resultat_bt['taux']:.1f}% - NE PASSE PAS EN RÉEL. Change de paire ou de niveau.")
            st.write(f"ATTENDRE : {resultat_bt['nb_attendre']} fois - C'est normal, le filtre bloque beaucoup.")
            if len(resultat_bt["details"]) > 0:
                st.dataframe(pd.DataFrame(resultat_bt["details"]), use_container_width=True, hide_index=True)

if st.button("🔍 ANALYSER MAINTENANT - V4 FINAL CORRIGÉ", type="primary"):
    is_scalp = mode.startswith("⚡")
    with st.spinner("Analyse V4 finale : 2m + MTF 2-5-15 + Faux Cassure corrigé + Confirmation bougie + Délai OTC 5s..."):
        ticker = PAIRES[paire]
        df = recuperer_donnees_avec_secours(ticker, interval="2m", period="1d", paire_nom=paire)
        if df.empty or len(df) < 100:
            st.error("Données insuffisantes.")
        else:
            df = calculer_indicateurs(df)
            df = garder_que_les_bougies_fermees(df, interval="2m")
            df = df.dropna(subset=["RSI", "WCCI", "CFO", "MACD_HIST", "ATR", "BB_MID", "EMA50"])
            if len(df) < 4:
                st.error("Pas assez de données.")
            else:
                analyse = analyser_signal_v3_corrige(df, ticker, is_scalping=is_scalp, use_mtf=use_mtf, use_faux=use_faux, use_vol_intel=use_vol_intel, use_volume=use_volume)
                c = df.iloc[-1]
                nouvel_id = str(uuid.uuid4())[:8]
                st.session_state.historique.append({"ID": nouvel_id, "Heure": datetime.now().strftime("%H:%M:%S"), "Paire": paire, "Mode": "SCALPING" if is_scalp else "V2 PRO", "Signal": analyse["signal"], "Prix": round(float(c["Close"]),5), "Score H": analyse["score_haut"], "Score B": analyse["score_bas"], "MTF": analyse["mtf"]["direction"], "Dernière Bougie": analyse.get("derniere_direction","?"), "Volume": analyse["vol"].get("statut","-"), "Résultat": "En attente"})
                sauvegarder_historique()
                st.divider()
                st.subheader(f"🎯 SIGNAL V4 FINAL - Graphique 2m")
                st.metric("Prix", f"{float(c['Close']):.5f}")
                st.metric("RSI 14 / RSI 7", f"{float(c['RSI']):.1f} / {float(c['RSI7']):.1f}")
                st.metric("EMA 5 / 9 / 21", f"{float(c['EMA5']):.5f} / {float(c['EMA9']):.5f} / {float(c['EMA21']):.5f}")
                st.metric("WCCI / CFO", f"{float(c['WCCI']):.1f} / {float(c['CFO']):.4f}")
                st.metric("Dernière bougie fermée (2m)", f"{analyse.get('derniere_direction','?')} - Doji ? {analyse.get('derniere_est_doji','?')}")
                if analyse["signal"] == "CALL / HAUSSE":
                    st.success(f"🟢 CALL - {expiration} mn - V4 VALIDÉ (2m + MTF + Bougie confirmée)")
                    st.warning("⚠️ Vérifie sur IQ Option avant de cliquer. Attends 5 secondes après la fermeture. Le prix OTC peut être différent de Yahoo.")
                elif analyse["signal"] == "PUT / BAISSE":
                    st.error(f"🔴 PUT - {expiration} mn - V4 VALIDÉ (2m + MTF + Bougie confirmée)")
                    st.warning("⚠️ Vérifie sur IQ Option avant de cliquer. Attends 5 secondes après la fermeture. Le prix OTC peut être différent de Yahoo.")
                else:
                    st.warning("⏳ ATTENDRE - V4 a bloqué")
                st.write("**Motif :**", analyse["raison"])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Score HAUSSE", f"{analyse['score_haut']}/6")
                with col2:
                    st.metric("Score BAISSE", f"{analyse['score_bas']}/6")
                st.divider()
                st.subheader("1️⃣ Multi-Timeframe CORRIGÉ - 2m, 5m, 15m")
                st.info(analyse["mtf"]["accord"])
                st.dataframe(pd.DataFrame([analyse["mtf"]["details"]]), use_container_width=True)
                st.caption("Si 2m dit HAUSSE et 15m dit BAISSE = CONFLIT = ATTENDRE.")
                st.subheader("2️⃣ Faux Cassure CORRIGÉ")
                if analyse["faux"]["faux"]:
                    st.error(analyse["faux"]["texte"])
                else:
                    st.success(analyse["faux"]["texte"])
                st.caption("Vérifié avec les niveaux de chaque bougie au moment de la cassure.")
                st.subheader("4️⃣ Volatilité Intelligente")
                if analyse["vol_intel"]["statut"] in ["SQUEEZE","TROP_HAUTE","TROP_BASSE"]:
                    st.warning(analyse["vol_intel"]["texte"])
                else:
                    st.success(analyse["vol_intel"]["texte"])
                st.subheader("6️⃣ Volume")
                if analyse["vol"].get("statut") == "FORT":
                    st.success(analyse["vol"]["texte"])
                elif analyse["vol"].get("statut") == "FAIBLE":
                    st.warning(analyse["vol"]["texte"])
                else:
                    st.info(analyse["vol"]["texte"])
                st.divider()
                st.subheader("🕯️ 3. Chandeliers Avancés - 3 Bougies 2m")
                if len(analyse["info_3"]["liste"]) > 0:
                    st.info(f"**Figure :** {analyse['info_3']['figure_3']} | **Force :** {analyse['info_3']['force_3']} | **Vertes :** {analyse['info_3']['nb_hausse']} | **Rouges :** {analyse['info_3']['nb_baisse']} | **Doji :** {analyse['info_3']['nb_doji']} | **Dernière :** {analyse.get('derniere_direction')}")
                    st.dataframe(pd.DataFrame(analyse["info_3"]["liste"]), use_container_width=True, hide_index=True)
                st.divider()
                st.subheader("📍 Support / Résistance - abs() 0.20")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Support", f"{float(analyse['support']):.5f}" if pd.notna(analyse["support"]) else "Indisponible")
                    if analyse["proche_support"]:
                        st.caption("⚠️ Collé au Support : abs(prix - support) <= 0.20 x ATR")
                with col2:
                    st.metric("Résistance", f"{float(analyse['resistance']):.5f}" if pd.notna(analyse["resistance"]) else "Indisponible")
                    if analyse["proche_resistance"]:
                        st.caption("⚠️ Collé à la Résistance : abs(résistance - prix) <= 0.20 x ATR")
                st.subheader("📋 Tableau Confirmations")
                confirmations = pd.DataFrame({"Indicateur": ["EMA 9/21/50","RSI 14","WCCI 14","CFO 14","MACD","Bollinger","3 Bougies","Dernière Bougie"], "HAUSSE": [float(c["EMA9"]) > float(c["EMA21"]) > float(c["EMA50"]), 50 < float(c["RSI"]) < 70, float(c["WCCI"]) > 0, float(c["CFO"]) > 0, float(c["MACD_HIST"]) > 0, float(c["Close"]) > float(c["BB_MID"]), analyse["direction"] == "HAUSSE", analyse.get("derniere_direction") == "HAUSSE"], "BAISSE": [float(c["EMA9"]) < float(c["EMA21"]) < float(c["EMA50"]), 30 < float(c["RSI"]) < 50, float(c["WCCI"]) < 0, float(c["CFO"]) < 0, float(c["MACD_HIST"]) < 0, float(c["Close"]) < float(c["BB_MID"]), analyse["direction"] == "BAISSE", analyse.get("derniere_direction") == "BAISSE"]})
                st.dataframe(confirmations, use_container_width=True, hide_index=True)
                st.subheader("📈 Graphique 2m")
                st.line_chart(df[["Close","BB_UPPER","BB_MID","BB_LOWER","EMA5","EMA9","EMA21"]].tail(100))
                st.caption("Graphique principal en 2m, comme ton MTF 2m-5m-15m.")

st.divider()
st.header("📊 7. Historique et VRAI Taux de Réussite - SAUVEGARDÉ")
st.caption("✅ Ton historique est maintenant sauvegardé dans historique_v4.csv. Même si tu fermes l'app, il reste.")
if len(st.session_state.historique) == 0:
    st.info("Aucun signal encore.")
else:
    df_hist = pd.DataFrame(st.session_state.historique)
    total = len(df_hist)
    df_trades = df_hist[df_hist["Signal"].isin(["CALL / HAUSSE", "PUT / BAISSE"])]
    df_finis = df_trades[df_trades["Résultat"].isin(["GAGNÉ", "PERDU"])]
    nb_gagne = len(df_finis[df_finis["Résultat"] == "GAGNÉ"])
    nb_perdu = len(df_finis[df_finis["Résultat"] == "PERDU"])
    nb_en_attente = len(df_trades[df_trades["Résultat"] == "En attente"])
    nb_attendre = len(df_hist[df_hist["Signal"] == "ATTENDRE"])
    taux = (nb_gagne / (nb_gagne + nb_perdu) * 100) if (nb_gagne + nb_perdu) > 0 else 0
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    with col_s1:
        st.metric("Total Signaux", total)
    with col_s2:
        st.metric("🟢 GAGNÉ", nb_gagne)
    with col_s3:
        st.metric("🔴 PERDU", nb_perdu)
    with col_s4:
        st.metric("⏳ En attente", nb_en_attente)
    with col_s5:
        st.metric("🏆 Taux Réussite", f"{taux:.1f}%")
    if nb_gagne + nb_perdu > 0:
        st.write(f"**Vrai taux :** {nb_gagne} GAGNÉ / {nb_gagne + nb_perdu} trades finis = **{taux:.1f}%**")
        if taux >= 60:
            st.success(f"✅ Bon taux : {taux:.1f}% - Continue comme ça.")
        elif taux >= 50:
            st.warning(f"🟡 Taux moyen : {taux:.1f}% - Il faut améliorer.")
        else:
            st.error(f"🔴 Taux faible : {taux:.1f}% - Arrête et revois ta stratégie.")
    else:
        st.info("Aucun trade fini. Marque tes trades comme GAGNÉ ou PERDU ci-dessous.")
    st.subheader("📜 Marque tes résultats")
    for idx, row in df_hist.iterrows():
        col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 2])
        with col_a:
            st.write(f"**{row['Heure']} - {row['Paire']} - {row['Signal']}** - Prix {row['Prix']} - MTF {row.get('MTF','?')} - Dernière {row.get('Dernière Bougie','?')}")
        with col_b:
            st.write(f"Score H {row['Score H']} / B {row['Score B']} - Mode {row['Mode']}")
        with col_c:
            st.write(f"Résultat actuel : **{row['Résultat']}**")
        with col_d:
            if row["Signal"] in ["CALL / HAUSSE", "PUT / BAISSE"] and row["Résultat"] == "En attente":
                c_g, c_p = st.columns(2)
                with c_g:
                    if st.button(f"✅ GAGNÉ", key=f"gagne_{row['ID']}"):
                        for j in range(len(st.session_state.historique)):
                            if st.session_state.historique[j]["ID"] == row["ID"]:
                                st.session_state.historique[j]["Résultat"] = "GAGNÉ"
                                break
                        sauvegarder_historique()
                        st.rerun()
                with c_p:
                    if st.button(f"❌ PERDU", key=f"perdu_{row['ID']}"):
                        for j in range(len(st.session_state.historique)):
                            if st.session_state.historique[j]["ID"] == row["ID"]:
                                st.session_state.historique[j]["Résultat"] = "PERDU"
                                break
                        sauvegarder_historique()
                        st.rerun()
            elif row["Résultat"] in ["GAGNÉ", "PERDU"]:
                st.write("✅ Enregistré")
            else:
                st.write("— ATTENDRE, pas de trade")
    st.divider()
    st.subheader("📈 Par Paire - Taux par paire")
    if len(df_finis) > 0:
        stats_paire = []
        for paire_nom in df_finis["Paire"].unique():
            df_p = df_finis[df_finis["Paire"] == paire_nom]
            g = len(df_p[df_p["Résultat"] == "GAGNÉ"])
            p = len(df_p[df_p["Résultat"] == "PERDU"])
            taux_p = (g / (g+p) * 100) if (g+p) > 0 else 0
            stats_paire.append({"Paire": paire_nom, "Trades": g+p, "GAGNÉ": g, "PERDU": p, "Taux %": round(taux_p,1)})
        st.dataframe(pd.DataFrame(stats_paire), use_container_width=True, hide_index=True)
    # Bouton télécharger
    try:
        csv_data = pd.DataFrame(st.session_state.historique).to_csv(index=False).encode("utf-8")
        st.download_button("📥 Télécharger mon historique (CSV)", data=csv_data, file_name="historique_v4.csv", mime="text/csv")
    except Exception:
        pass
    if st.button("🗑️ Effacer l'historique"):
        st.session_state.historique = []
        try:
            if os.path.exists(FICHIER_HISTORIQUE):
                os.remove(FICHIER_HISTORIQUE)
        except Exception:
            pass
        st.rerun()

st.divider()
st.header(f"📸 Capture V4 - {paire} - {expiration} mn - Graphique 2m")
st.caption("Pour la capture, regarde les bougies 2m, pas 1m. Et la dernière bougie doit être fermée + 5 secondes.")
if CLE_ACTIVE:
    st.success("✅ AUTO IA active")
    mode_capture = st.radio("Mode capture :", ["🤖 AUTO IA V4", "✍️ MANUEL"], index=0, horizontal=True)
else:
    mode_capture = st.radio("Mode capture :", ["✍️ MANUEL", "🤖 AUTO IA V4"], index=0, horizontal=True)
uploaded = st.file_uploader("Envoie ta capture", type=["png","jpg","jpeg","webp"], key="capture_v4_final_corrige")
if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)
    if mode_capture.startswith("🤖"):
        if not CLE_ACTIVE:
            st.error("❌ Mets ta clé dans Secrets ou utilise MANUEL.")
        else:
            if st.button("🧠 ANALYSER MA CAPTURE V4 FINAL", type="primary", use_container_width=True):
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"
                    prompt = f"Tu es un analyste PRO V4 FINAL CORRIGÉ IQ Option. Actif : {paire}. Expiration : {expiration} mn. Graphique principal : 2m. Règles : 1) MTF 2m-5m-15m, si une timeframe dit l'inverse c'est CONFLIT = ATTENDRE. 2) Faux Cassure : compare chaque bougie avec le Support/Résistance de son époque. 3) Chandeliers sur 3 dernières bougies FERMÉES en 2m. 4) Confirmation obligatoire : CALL = dernière bougie verte et pas Doji, PUT = dernière bougie rouge et pas Doji. 5) Minimum 4/6 V2 PRO, 3/6 Scalping. 6) Yahoo est différent de IQ Option OTC, avertis de vérifier sur IQ Option et d'attendre 5 secondes après fermeture. Donne : tableau 3 bougies 2m, MTF 2-5-15, Faux Cassure, Confirmation dernière bougie, Score /6, CONCLUSION CALL/PUT/ATTENDRE. Ne garantis jamais un gain. Si illisible, dis ILLISIBLE."
                    with st.spinner("🧠 L'IA analyse..."):
                        resp = client_auto.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}]}], max_tokens=1200)
                        st.markdown(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"Erreur IA : {e}")
    else:
        c1, c2, c3 = st.columns(3)
        b3_m = c1.selectbox("Bougie -3 (2m)", ["Verte","Rouge","Doji"], key="b3_final_corrige")
        b2_m = c2.selectbox("Bougie -2 (2m)", ["Verte","Rouge","Doji"], key="b2_final_corrige")
        b1_m = c3.selectbox("Bougie -1 (2m) - Dernière fermée", ["Verte","Rouge","Doji"], key="b1_final_corrige")
        vol_m = st.selectbox("Volume", ["Fort","Normal","Faible","Je ne vois pas"], key="vol_final_corrige")
        mtf_m = st.selectbox("5m et 15m ?", ["HAUSSE comme 2m","BAISSE comme 2m","Contraire à 2m (CONFLIT)","Je ne sais pas"], key="mtf_final_corrige")
        if st.button("🔎 ANALYSER V4 FINAL - SANS CLÉ", type="primary", use_container_width=True):
            nb_v = [b3_m, b2_m, b1_m].count("Verte")
            nb_r = [b3_m, b2_m, b1_m].count("Rouge")
            if mtf_m == "Contraire à 2m (CONFLIT)":
                st.warning("⏳ ATTENDRE - MTF CONFLIT : 2m dit une chose, 5m/15m disent l'inverse.")
            elif b1_m == "Doji":
                st.warning("⏳ ATTENDRE - Dernière bougie Doji - Confirmation obligatoire manquante.")
            elif nb_v == 3 and b1_m == "Verte":
                st.success(f"🟢 CALL {paire} - 3 Soldats Blancs + Dernière verte confirmée - Vérifie sur IQ Option + Attends 5s")
            elif nb_r == 3 and b1_m == "Rouge":
                st.error(f"🔴 PUT {paire} - 3 Corbeaux Noirs + Dernière rouge confirmée - Vérifie sur IQ Option + Attends 5s")
            elif nb_v == 2 and b1_m == "Verte":
                st.success(f"🟢 CALL {paire} - 2 Vertes + Dernière verte confirmée")
            elif nb_r == 2 and b1_m == "Rouge":
                st.error(f"🔴 PUT {paire} - 2 Rouges + Dernière rouge confirmée")
            else:
                st.warning(f"🟡 ATTENDRE {paire} - Dernière bougie ne confirme pas.")

st.caption("IQ OPTION AI TRADER DXY V4 - TOUTES ERREURS CORRIGÉES : 2m + MTF 2-5-15 sans conflit + Seuil min 4/3 + Confirmation bougie + Faux breakout corrigé + Historique CSV sauvegardé + Backtest 5 jours + DXY secours + Heure Yahoo + Délai OTC 5s | Ne trade jamais tout ton capital.")
