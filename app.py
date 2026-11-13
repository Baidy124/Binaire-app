import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os, base64
from datetime import datetime, timezone

# ================= 🔑 CLÉ AUTOMATIQUE =================
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

# ================= ⚙️ RÉGLAGES FILTRE DOUX =================
SEUIL_V2PRO = 4
SEUIL_SCALPING = 3
SEUIL_VOLATILITE = 0.00001
DISTANCE_SUPPORT = 0.10
SEUIL_CORPS_BOUGIE = 0.08
NB_DOJI_POUR_BLOQUER = 3

st.set_page_config(page_title="BINAIRE V3 ULTIME", page_icon="📈", layout="wide")
st.title("📈 BINAIRE V3 ULTIME - Multi-Timeframe + Faux Cassure + Volume + Stats")
st.caption("V2 PRO + Scalping + 3 Bougies + Filtre Doux + 7 Nouveautés")

if CLE_ACTIVE:
    st.success("✅ Clé OpenAI AUTOMATIQUE active")
else:
    st.info("ℹ️ Pas de clé. Capture en MANUEL.")

# ================= 📊 HISTORIQUE - INITIALISATION =================
if "historique" not in st.session_state:
    st.session_state.historique = []  # Liste des signaux

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
    "Dollar Index (DXY)": "DX-Y.NYB"
}

# ================= 🎯 MODE + OPTIONS =================
col_m1, col_m2 = st.columns(2)
with col_m1:
    mode = st.radio("Mode :", [f"📊 V2 PRO - {SEUIL_V2PRO}/6", f"⚡ SCALPING - {SEUIL_SCALPING}/6"], index=0)
with col_m2:
    st.write("**Nouveautés V3 à activer :**")
    use_mtf = st.checkbox("✅ 1. Multi-Timeframe (1m + 5m + 15m)", value=True)
    use_faux = st.checkbox("✅ 2. Détection Faux Cassure", value=True)
    use_vol_intel = st.checkbox("✅ 4. Filtre Volatilité Intelligent", value=True)
    use_volume = st.checkbox("✅ 6. Confirmation Volume", value=True)
    use_horaire = st.checkbox("✅ 5. Filtre Horaire / News", value=True)

col1, col2 = st.columns(2)
with col1:
    paire = st.selectbox("Choisir un actif", list(PAIRES.keys()))
with col2:
    if mode.startswith("⚡"):
        expiration = st.slider("Expiration SCALPING", 1, 5, 2)
    else:
        expiration = st.slider("Expiration V2 PRO", 1, 19, 5)

st.info(f"Actif : {paire} | Mode : {mode} | Expiration : {expiration} mn | MTF : {'ON' if use_mtf else 'OFF'} | Faux Cassure : {'ON' if use_faux else 'OFF'}")

@st.cache_data(ttl=30)
def recuperer_donnees(ticker, interval="1m", period="1d"):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # On garde Volume si dispo
        cols = ["Open", "High", "Low", "Close"]
        if "Volume" in df.columns:
            cols.append("Volume")
        if not all(c in df.columns for c in cols[:4]):
            return pd.DataFrame()
        df = df[cols].copy()
        df = df.dropna(subset=["Open","High","Low","Close"])
        return df
    except Exception:
        return pd.DataFrame()

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
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / df["BB_MID"]  # Largeur Bollinger pour Squeeze
    typical = (high + low + close) / 3
    moyenne = typical.rolling(14).mean()
    deviation = typical.rolling(14).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    df["WCCI"] = ((typical - moyenne) / (0.015 * deviation.replace(0, np.nan)))
    def forecast(x):
        indices = np.arange(len(x))
        coefficients = np.polyfit(indices, x, 1)
        return np.polyval(coefficients, len(x) - 1)
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
    # Volume moyen
    if "Volume" in df.columns:
        df["VOL_MOYEN"] = df["Volume"].rolling(20).mean()
    return df

# ================= 🕯️ 3. RECONNAISSANCE AVANCÉE =================
def decrire_une_bougie(row):
    corps = abs(row["Close"] - row["Open"])
    amplitude = row["High"] - row["Low"]
    if amplitude == 0:
        return "Invalide", "NEUTRE", 0
    ratio = corps / amplitude
    if ratio < 0.10:
        return "Doji", "NEUTRE", ratio
    if row["Close"] > row["Open"]:
        return ("Verte Forte" if ratio > 0.60 else "Verte"), "HAUSSE", ratio
    else:
        return ("Rouge Forte" if ratio > 0.60 else "Rouge"), "BAISSE", ratio

def analyser_trois_bougies_avance(df):
    b3 = df.iloc[-3]; b2 = df.iloc[-2]; b1 = df.iloc[-1]
    desc3, dir3, ratio3 = decrire_une_bougie(b3)
    desc2, dir2, ratio2 = decrire_une_bougie(b2)
    desc1, dir1, ratio1 = decrire_une_bougie(b1)
    liste = [
        {"Bougie": "Bougie -3", "Type": desc3, "Direction": dir3, "Open": round(float(b3["Open"]),5), "Close": round(float(b3["Close"]),5), "Corps %": round(ratio3*100,1)},
        {"Bougie": "Bougie -2", "Type": desc2, "Direction": dir2, "Open": round(float(b2["Open"]),5), "Close": round(float(b2["Close"]),5), "Corps %": round(ratio2*100,1)},
        {"Bougie": "Bougie -1", "Type": desc1, "Direction": dir1, "Open": round(float(b1["Open"]),5), "Close": round(float(b1["Close"]),5), "Corps %": round(ratio1*100,1)},
    ]
    nb_hausse = sum([1 for d in [dir3, dir2, dir1] if d == "HAUSSE"])
    nb_baisse = sum([1 for d in [dir3, dir2, dir1] if d == "BAISSE"])
    nb_doji = sum([1 for d in [dir3, dir2, dir1] if d == "NEUTRE"])

    figure_3 = "Aucune figure spéciale"; direction_3 = "NEUTRE"; force_3 = "Faible"

    # --- Figures AVANCÉES sur 3 bougies ---
    # Étoile du Matin : Rouge Forte, Petite bougie, Verte Forte qui monte -> Retournement HAUSSE
    if dir3 == "BAISSE" and ratio3 > 0.5 and dir2 == "NEUTRE" and dir1 == "HAUSSE" and ratio1 > 0.5 and b1["Close"] > (b3["Open"] + b3["Close"])/2:
        figure_3 = "🌅 Étoile du Matin - Retournement HAUSSE très fort"; direction_3 = "HAUSSE"; force_3 = "Forte"
    # Étoile du Soir : Verte Forte, Petite, Rouge Forte -> Retournement BAISSE
    elif dir3 == "HAUSSE" and ratio3 > 0.5 and dir2 == "NEUTRE" and dir1 == "BAISSE" and ratio1 > 0.5 and b1["Close"] < (b3["Open"] + b3["Close"])/2:
        figure_3 = "🌇 Étoile du Soir - Retournement BAISSE très fort"; direction_3 = "BAISSE"; force_3 = "Forte"
    # Harami Haussier : Grande Rouge, Petite Verte dedans -> Retournement HAUSSE
    elif dir3 == "BAISSE" and ratio3 > 0.6 and dir2 == "HAUSSE" and b2["Open"] < b3["Close"] and b2["Close"] > b3["Open"]:
        figure_3 = "🤰 Harami Haussier - Retournement HAUSSE"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
    # Harami Baissier
    elif dir3 == "HAUSSE" and ratio3 > 0.6 and dir2 == "BAISSE" and b2["Open"] > b3["Close"] and b2["Close"] < b3["Open"]:
        figure_3 = "🤰 Harami Baissier - Retournement BAISSE"; direction_3 = "BAISSE"; force_3 = "Moyenne"
    elif nb_hausse == 3:
        if b1["Close"] > b2["Close"] > b3["Close"]:
            figure_3 = "🟢 3 Soldats Blancs"; direction_3 = "HAUSSE"; force_3 = "Forte"
        else:
            figure_3 = "🟢 3 Bougies Vertes"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
    elif nb_baisse == 3:
        if b1["Close"] < b2["Close"] < b3["Close"]:
            figure_3 = "🔴 3 Corbeaux Noirs"; direction_3 = "BAISSE"; force_3 = "Forte"
        else:
            figure_3 = "🔴 3 Bougies Rouges"; direction_3 = "BAISSE"; force_3 = "Moyenne"
    elif nb_hausse == 2 and nb_baisse == 1 and dir1 == "HAUSSE":
        figure_3 = "🟢 2 Vertes / 1 Rouge - Dernière verte"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
    elif nb_baisse == 2 and nb_hausse == 1 and dir1 == "BAISSE":
        figure_3 = "🔴 2 Rouges / 1 Verte - Dernière rouge"; direction_3 = "BAISSE"; force_3 = "Moyenne"
    elif nb_doji >= 2:
        figure_3 = "🟡 Beaucoup de Doji"; direction_3 = "NEUTRE"; force_3 = "Faible"
    # Englobante sur les 2 dernières (b2 + b1)
    # On vérifie aussi Englobante Haussière / Baissière sur b2-b1
    elif dir2 == "BAISSE" and dir1 == "HAUSSE" and b1["Close"] >= b2["Open"] and b1["Open"] <= b2["Close"]:
        figure_3 = "🟢 Englobante Haussière (sur 2 dernières)"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
    elif dir2 == "HAUSSE" and dir1 == "BAISSE" and b1["Close"] <= b2["Open"] and b1["Open"] >= b2["Close"]:
        figure_3 = "🔴 Englobante Baissière (sur 2 dernières)"; direction_3 = "BAISSE"; force_3 = "Moyenne"
    # Marteau / Pendu / Étoile Filante sur dernière bougie
    else:
        # On calcule mèches de b1
        corps1 = abs(b1["Close"] - b1["Open"]); amp1 = b1["High"] - b1["Low"]
        if amp1 > 0:
            meche_haute = b1["High"] - max(b1["Open"], b1["Close"])
            meche_basse = min(b1["Open"], b1["Close"]) - b1["Low"]
            if meche_basse >= corps1 * 2 and meche_haute <= corps1 and dir1 == "HAUSSE":
                figure_3 = "🔨 Marteau Haussier (dernière bougie)"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
            elif meche_haute >= corps1 * 2 and meche_basse <= corps1 and dir1 == "BAISSE":
                figure_3 = "⭐ Étoile Filante (dernière bougie)"; direction_3 = "BAISSE"; force_3 = "Moyenne"
            elif meche_basse >= corps1 * 2 and meche_haute <= corps1 and dir1 == "BAISSE":
                figure_3 = "🪦 Pendu - Attention retournement BAISSE"; direction_3 = "BAISSE"; force_3 = "Faible"
            elif meche_haute >= corps1 * 2 and meche_basse <= corps1 and dir1 == "HAUSSE":
                figure_3 = "🔨 Marteau Inversé - Retournement HAUSSE possible"; direction_3 = "HAUSSE"; force_3 = "Faible"

    return {"liste": liste, "figure_3": figure_3, "direction_3": direction_3, "force_3": force_3, "nb_hausse": nb_hausse, "nb_baisse": nb_baisse, "nb_doji": nb_doji, "chandelier": figure_3, "direction": direction_3}

# ================= 1. MULTI-TIMEFRAME =================
def analyser_mtf(ticker):
    # 1m, 5m, 15m
    resultats = {}
    for interval, period in [("1m","1d"), ("5m","5d"), ("15m","5d")]:
        df = recuperer_donnees(ticker, interval=interval, period=period)
        if df.empty or len(df) < 50:
            resultats[interval] = "NEUTRE"
            continue
        df = calculer_indicateurs(df)
        df = df.iloc[:-1].copy()
        df = df.dropna(subset=["RSI","EMA50"])
        if df.empty:
            resultats[interval] = "NEUTRE"
            continue
        c = df.iloc[-1]
        if c["EMA9"] > c["EMA21"] and c["RSI"] > 50:
            resultats[interval] = "HAUSSE"
        elif c["EMA9"] < c["EMA21"] and c["RSI"] < 50:
            resultats[interval] = "BAISSE"
        else:
            resultats[interval] = "NEUTRE"
    # Accord ?
    nb_h = list(resultats.values()).count("HAUSSE")
    nb_b = list(resultats.values()).count("BAISSE")
    if nb_h == 3:
        accord = "✅ ACCORD TOTAL HAUSSE (1m + 5m + 15m)"
        direction_mtf = "HAUSSE"
    elif nb_b == 3:
        accord = "✅ ACCORD TOTAL BAISSE (1m + 5m + 15m)"
        direction_mtf = "BAISSE"
    elif nb_h == 2 and nb_b == 0:
        accord = "🟡 Accord partiel HAUSSE (2/3)"
        direction_mtf = "HAUSSE"
    elif nb_b == 2 and nb_h == 0:
        accord = "🟡 Accord partiel BAISSE (2/3)"
        direction_mtf = "BAISSE"
    elif nb_h > 0 and nb_b > 0:
        accord = "🔴 CONFLIT MTF - 1m dit une chose, 15m dit l'inverse - ATTENTION"
        direction_mtf = "CONFLIT"
    else:
        accord = "🟡 MTF Neutre"
        direction_mtf = "NEUTRE"
    return {"details": resultats, "accord": accord, "direction": direction_mtf, "nb_h": nb_h, "nb_b": nb_b}

# ================= 2. FAUX CASSURE =================
def detecter_faux_cassure(df):
    # Regarde les 5 dernières bougies : est-ce que le prix a cassé la résistance puis est revenu en dessous ?
    if len(df) < 6:
        return {"faux": False, "texte": "Pas assez de données"}
    c = df.iloc[-1]
    res = c["RESISTANCE"]; sup = c["SUPPORT"]
    # Cassure haussière puis retour
    a_casse_resistance = False
    a_casse_support = False
    for i in range(-5, -1):
        row = df.iloc[i]
        if pd.notna(res) and row["Close"] > res:
            a_casse_resistance = True
        if pd.notna(sup) and row["Close"] < sup:
            a_casse_support = True
    prix_actuel = c["Close"]
    if a_casse_resistance and pd.notna(res) and prix_actuel < res:
        return {"faux": True, "texte": "⚠️ FAUX BREAKOUT HAUSSIER : Le prix a cassé la Résistance puis est revenu en dessous - C'était un piège ! Ne pas prendre CALL.", "type": "FAUX_HAUSSE"}
    if a_casse_support and pd.notna(sup) and prix_actuel > sup:
        return {"faux": True, "texte": "⚠️ FAUX BREAKOUT BAISSIER : Le prix a cassé le Support puis est revenu au-dessus - C'était un piège ! Ne pas prendre PUT.", "type": "FAUX_BAISSE"}
    return {"faux": False, "texte": "✅ Pas de faux breakout détecté - Cassure propre si elle arrive.", "type": "OK"}

# ================= 4. VOLATILITÉ INTELLIGENTE =================
def analyser_volatilite_intelligente(df):
    c = df.iloc[-1]
    atr = c["ATR"]; atr_moyen = c["ATR_MOYEN"]; bb_width = c["BB_WIDTH"]
    # BB Width moyen
    bb_moyen = df["BB_WIDTH"].rolling(50).mean().iloc[-1]
    if pd.isna(atr) or pd.isna(atr_moyen) or pd.isna(bb_width):
        return {"statut": "NEUTRE", "texte": "Volatilité : Données insuffisantes"}
    if bb_width < bb_moyen * 0.7:
        return {"statut": "SQUEEZE", "texte": f"🟡 SQUEEZE Bollinger : Bandes très serrées ({bb_width:.4f} vs moyenne {bb_moyen:.4f}) - Le marché va exploser bientôt, mais on ne sait pas dans quel sens. ATTENDRE la cassure."}
    if atr > atr_moyen * 1.8:
        return {"statut": "TROP_HAUTE", "texte": f"🔴 Volatilité TROP HAUTE : ATR {atr:.5f} vs moyenne {atr_moyen:.5f} (x1.8) - Marché trop nerveux, risque de faux signaux."}
    if atr < atr_moyen * 0.5:
        return {"statut": "TROP_BASSE", "texte": f"🟡 Volatilité TROP BASSE : ATR {atr:.5f} vs moyenne {atr_moyen:.5f} - Marché endormi, pas de mouvement."}
    return {"statut": "NORMALE", "texte": f"✅ Volatilité NORMALE : ATR {atr:.5f} vs moyenne {atr_moyen:.5f} - Bon pour trader."}

# ================= 5. FILTRE HORAIRE / NEWS =================
def analyser_horaire():
    now = datetime.now(timezone.utc)
    heure = now.hour
    jour = now.weekday()  # 0=Lundi, 6=Dimanche
    # Heures en GMT
    avertissements = []
    if jour == 6:
        avertissements.append("🔴 DIMANCHE : Marché fermé / très peu de volume. Ne trade pas le Forex le Dimanche.")
    if jour == 5 and heure >= 20:
        avertissements.append("🟡 SAMEDI SOIR GMT : Marché va fermer. Ne trade pas.")
    if 12 <= heure < 14:
        avertissements.append("🟡 12h-14h GMT : Pause déjeuner Londres/New York - Volatilité faible, beaucoup de faux signaux.")
    if heure in [8, 14] or (heure == 13 and now.minute >= 30):
        avertissements.append("⚠️ HEURE DE NEWS : 8h30 / 14h30 GMT = NFP, CPI, FOMC - Le prix peut bouger très fort dans les 2 sens. Si tu trades, mets un petit montant.")
    if 0 <= heure < 6:
        avertissements.append("🟡 00h-06h GMT : Session Asie seule - Volatilité faible sur EUR/USD, GBP/USD. Préfère USD/JPY, AUD/USD.")
    if 7 <= heure < 10:
        avertissements.append("✅ 07h-10h GMT : Ouverture Londres - Bonne volatilité pour EUR/USD, GBP/USD.")
    if 13 <= heure < 17:
        avertissements.append("✅ 13h-17h GMT : Londres + New York ensemble - Meilleure volatilité pour Forex.")
    if not avertissements:
        avertissements.append(f"✅ Heure OK : {now.strftime('%H:%M')} GMT - Pas de news majeure prévue à cette heure.")
    return {"heure_gmt": now.strftime("%H:%M GMT"), "jour": ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][jour], "avertissements": avertissements}

# ================= 6. VOLUME =================
def analyser_volume(df):
    if "Volume" not in df.columns:
        return {"statut": "SANS_VOLUME", "texte": "⚠️ Yahoo ne donne pas le volume pour cet actif (Forex). On utilise le volume de la paire si dispo, sinon on ignore."}
    c = df.iloc[-1]
    vol = c["Volume"]; vol_moyen = c["VOL_MOYEN"]
    if pd.isna(vol) or pd.isna(vol_moyen) or vol_moyen == 0:
        return {"statut": "NEUTRE", "texte": "Volume : Données insuffisantes"}
    ratio = vol / vol_moyen
    if ratio > 1.5:
        return {"statut": "FORT", "texte": f"✅ Volume FORT : {ratio:.2f}x la moyenne - Le signal est confirmé par beaucoup de traders.", "ratio": ratio}
    if ratio < 0.7:
        return {"statut": "FAIBLE", "texte": f"⚠️ Volume FAIBLE : {ratio:.2f}x la moyenne - Peu de traders, signal faible. Attention faux signal.", "ratio": ratio}
    return {"statut": "NORMAL", "texte": f"✅ Volume NORMAL : {ratio:.2f}x la moyenne.", "ratio": ratio}

# ================= SIGNAL PRINCIPAL V3 =================
def analyser_signal_v3(df, ticker, is_scalping=False, use_mtf=True, use_faux=True, use_vol_intel=True, use_volume=True):
    c = df.iloc[-1]
    prix = c["Close"]; atr = c["ATR"]
    tendance_haussiere = (c["EMA9"] > c["EMA21"] > c["EMA50"])
    tendance_baissiere = (c["EMA9"] < c["EMA21"] < c["EMA50"])
    indicateurs_haut = [tendance_haussiere, 50 < c["RSI"] < 70, c["WCCI"] > 0, c["CFO"] > 0, c["MACD_HIST"] > 0, prix > c["BB_MID"]]
    indicateurs_bas = [tendance_baissiere, 30 < c["RSI"] < 50, c["WCCI"] < 0, c["CFO"] < 0, c["MACD_HIST"] < 0, prix < c["BB_MID"]]
    info_3 = analyser_trois_bougies_avance(df)
    chandelier = info_3["chandelier"]; direction = info_3["direction"]
    score_haut = sum(indicateurs_haut); score_bas = sum(indicateurs_bas)
    support = c["SUPPORT"]; resistance = c["RESISTANCE"]
    proche_support = (pd.notna(support) and atr > 0 and prix - support <= atr * DISTANCE_SUPPORT)
    proche_resistance = (pd.notna(resistance) and atr > 0 and resistance - prix <= atr * DISTANCE_SUPPORT)
    volatilite_faible = (pd.isna(atr) or atr <= 0 or atr / prix < SEUIL_VOLATILITE)
    derniere = df.iloc[-1]
    amp_der = derniere["High"] - derniere["Low"]; corps_der = abs(derniere["Close"] - derniere["Open"])
    bougie_faible = (amp_der <= 0 or corps_der / amp_der < SEUIL_CORPS_BOUGIE)
    trop_de_doji = (info_3["nb_doji"] >= NB_DOJI_POUR_BLOQUER)
    seuil = SEUIL_SCALPING if is_scalping else SEUIL_V2PRO

    # --- NOUVEAUTÉS ---
    mtf = analyser_mtf(ticker) if use_mtf else {"direction": "NEUTRE", "accord": "MTF OFF", "details": {}}
    faux = detecter_faux_cassure(df) if use_faux else {"faux": False, "texte": "Faux breakout OFF"}
    vol_intel = analyser_volatilite_intelligente(df) if use_vol_intel else {"statut": "NEUTRE", "texte": "Volatilité intelligente OFF"}
    vol = analyser_volume(df) if use_volume else {"statut": "NEUTRE", "texte": "Volume OFF"}

    # Faux breakout -> ATTENDRE ou INVERSE ? On met ATTENDRE pour sécurité
    if faux["faux"]:
        return {"signal": "ATTENDRE", "raison": f"FAUX CASSURE : {faux['texte']}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}

    # Volatilité intelligente SQUEEZE ou TROP HAUTE -> ATTENDRE
    if vol_intel["statut"] in ["SQUEEZE", "TROP_HAUTE"]:
        return {"signal": "ATTENDRE", "raison": f"VOLATILITÉ INTELLIGENTE : {vol_intel['texte']}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}

    # Volume faible -> On ne bloque pas totalement, mais on le signale dans la raison. Si score est juste 4/6 et volume faible, on bloque.
    volume_faible_bloque = (vol.get("statut") == "FAIBLE" and max(score_haut, score_bas) < 5)

    # MTF Conflit -> ATTENDRE
    if mtf["direction"] == "CONFLIT":
        return {"signal": "ATTENDRE", "raison": f"MTF CONFLIT : {mtf['accord']} - Ne trade pas quand 1m et 15m se contredisent.", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}

    if volatilite_faible:
        return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Volatilité trop faible", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    if trop_de_doji:
        return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : {info_3['nb_doji']} Doji", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    if bougie_faible and direction == "NEUTRE":
        return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Bougie trop petite + neutre", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    if volume_faible_bloque:
        return {"signal": "ATTENDRE", "raison": f"VOLUME : {vol['texte']} + Score {max(score_haut, score_bas)}/6 pas assez fort pour compenser.", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}

    # MTF doit être d'accord ou neutre, pas opposé
    # Si MTF dit HAUSSE mais score dit BAISSE, on bloque
    if mtf["direction"] == "HAUSSE" and score_bas > score_haut:
        return {"signal": "ATTENDRE", "raison": f"MTF : 5m/15m disent HAUSSE, mais 1m dit BAISSE - Conflit, on attend.", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    if mtf["direction"] == "BAISSE" and score_haut > score_bas:
        return {"signal": "ATTENDRE", "raison": f"MTF : 5m/15m disent BAISSE, mais 1m dit HAUSSE - Conflit, on attend.", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}

    if is_scalping:
        scalp_haut_rapide = (c["EMA5"] > c["EMA9"] and c["RSI7"] > 50)
        scalp_bas_rapide = (c["EMA5"] < c["EMA9"] and c["RSI7"] < 50)
        if score_haut >= seuil and scalp_haut_rapide and not proche_resistance:
            return {"signal": "CALL / HAUSSE", "raison": f"V3 SCALPING : {score_haut}/6 + EMA5 + RSI7 + MTF {mtf['direction']} + Volume {vol.get('statut')} + {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
        if score_bas >= seuil and scalp_bas_rapide and not proche_support:
            return {"signal": "PUT / BAISSE", "raison": f"V3 SCALPING : {score_bas}/6 + EMA5 + RSI7 + MTF {mtf['direction']} + Volume {vol.get('statut')} + {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
        return {"signal": "ATTENDRE", "raison": f"V3 SCALPING : Pas {seuil}/6 + EMA5/RSI7", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}

    if score_haut >= seuil and not proche_resistance:
        return {"signal": "CALL / HAUSSE", "raison": f"V3 : {score_haut}/6 HAUSSE + MTF {mtf['direction']} + Volume {vol.get('statut')} + {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    if score_bas >= seuil and not proche_support:
        return {"signal": "PUT / BAISSE", "raison": f"V3 : {score_bas}/6 BAISSE + MTF {mtf['direction']} + Volume {vol.get('statut')} + {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    if score_haut >= seuil and proche_resistance:
        return {"signal": "ATTENDRE", "raison": "Filtre DOUX : Collé à la Résistance", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    if score_bas >= seuil and proche_support:
        return {"signal": "ATTENDRE", "raison": "Filtre DOUX : Collé au Support", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}
    return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Pas {seuil}/6 - HAUSSE {score_haut}, BAISSE {score_bas}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol}

# ================= 5. AFFICHAGE HORAIRE =================
if use_horaire:
    horaire = analyser_horaire()
    st.subheader(f"🕐 Filtre Horaire / News - {horaire['jour']} {horaire['heure_gmt']}")
    for av in horaire["avertissements"]:
        if av.startswith("🔴"):
            st.error(av)
        elif av.startswith("⚠️") or av.startswith("🟡"):
            st.warning(av)
        else:
            st.success(av)

# ================= ANALYSE =================
if st.button("🔍 ANALYSER MAINTENANT - V3 ULTIME", type="primary"):
    is_scalp = mode.startswith("⚡")
    with st.spinner("Analyse V3 : MTF + Faux Cassure + Volume + Volatilité..."):
        ticker = PAIRES[paire]
        df = recuperer_donnees(ticker, interval="1m", period="1d")
        if df.empty or len(df) < 100:
            st.error("Données insuffisantes.")
        else:
            df = calculer_indicateurs(df)
            df = df.iloc[:-1].copy()
            df = df.dropna(subset=["RSI", "WCCI", "CFO", "MACD_HIST", "ATR", "BB_MID", "EMA50"])
            if len(df) < 4:
                st.error("Pas assez de données.")
            else:
                analyse = analyser_signal_v3(df, ticker, is_scalping=is_scalp, use_mtf=use_mtf, use_faux=use_faux, use_vol_intel=use_vol_intel, use_volume=use_volume)
                c = df.iloc[-1]
                # --- Sauvegarde dans l'historique ---
                st.session_state.historique.append({
                    "Heure": datetime.now().strftime("%H:%M:%S"),
                    "Paire": paire,
                    "Mode": "SCALPING" if is_scalp else "V2 PRO",
                    "Signal": analyse["signal"],
                    "Prix": round(float(c["Close"]),5),
                    "Score H": analyse["score_haut"],
                    "Score B": analyse["score_bas"],
                    "MTF": analyse["mtf"]["direction"],
                    "Volume": analyse["vol"].get("statut","-"),
                    "Résultat": "En attente"  # Tu changeras après
                })
                st.divider()
                st.subheader("🎯 SIGNAL V3 ULTIME")
                st.metric("Prix", f"{c['Close']:.5f}")
                st.metric("RSI 14 / RSI 7", f"{c['RSI']:.1f} / {c['RSI7']:.1f}")
                st.metric("EMA 5 / 9 / 21", f"{c['EMA5']:.5f} / {c['EMA9']:.5f} / {c['EMA21']:.5f}")
                st.metric("WCCI / CFO", f"{c['WCCI']:.1f} / {c['CFO']:.4f}")
                if analyse["signal"] == "CALL / HAUSSE":
                    st.success(f"🟢 CALL - {expiration} mn - V3 VALIDÉ")
                elif analyse["signal"] == "PUT / BAISSE":
                    st.error(f"🔴 PUT - {expiration} mn - V3 VALIDÉ")
                else:
                    st.warning("⏳ ATTENDRE - V3 a bloqué")
                st.write("**Motif :**", analyse["raison"])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Score HAUSSE", f"{analyse['score_haut']}/6")
                with col2:
                    st.metric("Score BAISSE", f"{analyse['score_bas']}/6")
                st.divider()
                # 1. MTF
                st.subheader("1️⃣ Multi-Timeframe")
                st.info(analyse["mtf"]["accord"])
                st.dataframe(pd.DataFrame([analyse["mtf"]["details"]]), use_container_width=True)
                # 2. Faux Cassure
                st.subheader("2️⃣ Faux Cassure")
                if analyse["faux"]["faux"]:
                    st.error(analyse["faux"]["texte"])
                else:
                    st.success(analyse["faux"]["texte"])
                # 4. Volatilité Intelligente
                st.subheader("4️⃣ Volatilité Intelligente")
                if analyse["vol_intel"]["statut"] in ["SQUEEZE","TROP_HAUTE"]:
                    st.warning(analyse["vol_intel"]["texte"])
                elif analyse["vol_intel"]["statut"] == "TROP_BASSE":
                    st.warning(analyse["vol_intel"]["texte"])
                else:
                    st.success(analyse["vol_intel"]["texte"])
                # 6. Volume
                st.subheader("6️⃣ Volume")
                if analyse["vol"].get("statut") == "FORT":
                    st.success(analyse["vol"]["texte"])
                elif analyse["vol"].get("statut") == "FAIBLE":
                    st.warning(analyse["vol"]["texte"])
                else:
                    st.info(analyse["vol"]["texte"])
                st.divider()
                st.subheader("🕯️ 3. Chandeliers Avancés - 3 Bougies")
                st.info(f"**Figure :** {analyse['info_3']['figure_3']} | **Force :** {analyse['info_3']['force_3']} | **Vertes :** {analyse['info_3']['nb_hausse']} | **Rouges :** {analyse['info_3']['nb_baisse']} | **Doji :** {analyse['info_3']['nb_doji']}")
                st.dataframe(pd.DataFrame(analyse["info_3"]["liste"]), use_container_width=True, hide_index=True)
                st.divider()
                st.subheader("📍 Support / Résistance")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Support", f"{analyse['support']:.5f}" if pd.notna(analyse["support"]) else "Indisponible")
                with col2:
                    st.metric("Résistance", f"{analyse['resistance']:.5f}" if pd.notna(analyse["resistance"]) else "Indisponible")
                st.subheader("📋 Tableau Confirmations")
                confirmations = pd.DataFrame({
                    "Indicateur": ["EMA 9/21/50","RSI 14","WCCI 14","CFO 14","MACD","Bollinger","3 Bougies"],
                    "HAUSSE": [c["EMA9"] > c["EMA21"] > c["EMA50"], 50 < c["RSI"] < 70, c["WCCI"] > 0, c["CFO"] > 0, c["MACD_HIST"] > 0, c["Close"] > c["BB_MID"], analyse["direction"] == "HAUSSE"],
                    "BAISSE": [c["EMA9"] < c["EMA21"] < c["EMA50"], 30 < c["RSI"] < 50, c["WCCI"] < 0, c["CFO"] < 0, c["MACD_HIST"] < 0, c["Close"] < c["BB_MID"], analyse["direction"] == "BAISSE"]
                })
                st.dataframe(confirmations, use_container_width=True, hide_index=True)
                st.subheader("📈 Graphique")
                st.line_chart(df[["Close","BB_UPPER","BB_MID","BB_LOWER","EMA5","EMA9","EMA21"]].tail(100))

# ================= 7. HISTORIQUE ET STATISTIQUES =================
st.divider()
st.header("📊 7. Historique et Statistiques de Tes Signaux")
if len(st.session_state.historique) == 0:
    st.info("Aucun signal encore. Clique sur ANALYSER MAINTENANT, et il sera enregistré ici.")
else:
    df_hist = pd.DataFrame(st.session_state.historique)
    # Statistiques
    total = len(df_hist)
    nb_call = len(df_hist[df_hist["Signal"] == "CALL / HAUSSE"])
    nb_put = len(df_hist[df_hist["Signal"] == "PUT / BAISSE"])
    nb_att = len(df_hist[df_hist["Signal"] == "ATTENDRE"])
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("Total Signaux", total)
    with col_s2:
        st.metric("🟢 CALL", nb_call)
    with col_s3:
        st.metric("🔴 PUT", nb_put)
    with col_s4:
        st.metric("⏳ ATTENDRE", nb_att)
    # Pourcentage CALL vs PUT
    if total > 0:
        st.write(f"**Répartition :** CALL {nb_call/total*100:.1f}% | PUT {nb_put/total*100:.1f}% | ATTENDRE {nb_att/total*100:.1f}%")
        # Par paire
        st.subheader("📈 Par Paire")
        st.dataframe(df_hist.groupby("Paire").size().reset_index(name="Nombre de signaux"), use_container_width=True, hide_index=True)
    st.subheader("📜 Tous tes signaux")
    # Tu peux modifier Résultat manuellement : tu copies, tu notes GAGNÉ ou PERDU dans ta tête, ou tu effaces
    st.dataframe(df_hist, use_container_width=True, hide_index=True)
    st.caption("Astuce : Après ton trade, note si c'était GAGNÉ ou PERDU. Si tu as beaucoup de PERDU sur une paire ou à une heure, arrête de trader cette paire à cette heure.")
    if st.button("🗑️ Effacer l'historique"):
        st.session_state.historique = []
        st.rerun()

# ================= 📸 CAPTURE V3 =================
st.divider()
st.header(f"📸 Analyser ma capture V3 - {paire} - {expiration} mn")
st.caption("L'IA va aussi vérifier MTF, Faux Cassure, Volume, Volatilité, Chandeliers Avancés.")
if CLE_ACTIVE:
    st.success("✅ AUTO IA active")
    mode_capture = st.radio("Mode capture :", ["🤖 AUTO IA V3", "✍️ MANUEL"], index=0, horizontal=True)
else:
    mode_capture = st.radio("Mode capture :", ["✍️ MANUEL", "🤖 AUTO IA V3"], index=0, horizontal=True)
uploaded = st.file_uploader("Envoie ta capture", type=["png","jpg","jpeg","webp"], key="capture_v3")
if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)
    if mode_capture.startswith("🤖"):
        if not CLE_ACTIVE:
            st.error("❌ Mets ta clé dans Secrets ou utilise MANUEL.")
        else:
            if st.button("🧠 ANALYSER MA CAPTURE V3 ULTIME", type="primary", use_container_width=True):
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"
                    prompt = f"Tu es un analyste PRO V3 ULTIME IQ Option. Actif : {paire}. Expiration : {expiration} mn. Analyse : 1) Multi-Timeframe : regarde si 1m, 5m, 15m sont d'accord. 2) Faux Cassure : le prix a-t-il cassé Support/Résistance puis est revenu ? Si oui, c'est un piège. 3) Chandeliers Avancés : Étoile du Matin/Soir, Harami, Englobante, Marteau, Pendu, 3 Soldats, 3 Corbeaux, Doji, sur les 3 dernières bougies FERMÉES. 4) Volatilité Intelligente : Bollinger Squeeze ? ATR trop haut/bas ? 5) Horaire : est-ce une mauvaise heure / news ? 6) Volume : fort ou faible ? Donne : tableau 3 bougies, MTF, Faux Cassure Oui/Non, Volatilité, Volume, Score /6, CONCLUSION CALL/PUT/ATTENDRE avec raison. Ne garantis jamais un gain. Si illisible, dis ILLISIBLE."
                    with st.spinner("🧠 L'IA analyse ta capture V3..."):
                        resp = client_auto.responses.create(model="gpt-5.5", input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":data_url,"detail":"high"}]}])
                        st.markdown(resp.output_text)
                except Exception as e:
                    st.error(f"Erreur IA : {e}")
    else:
        st.success("✅ MANUEL V3")
        c1, c2, c3 = st.columns(3)
        b3_m = c1.selectbox("Bougie -3", ["Verte","Rouge","Doji"], key="b3_v3")
        b2_m = c2.selectbox("Bougie -2", ["Verte","Rouge","Doji"], key="b2_v3")
        b1_m = c3.selectbox("Bougie -1", ["Verte","Rouge","Doji"], key="b1_v3")
        vol_m = st.selectbox("Volume sur ta capture", ["Fort","Normal","Faible","Je ne vois pas"], key="vol_v3")
        mtf_m = st.selectbox("5m et 15m disent ?", ["HAUSSE comme 1m","BAISSE comme 1m","Contraire à 1m","Je ne sais pas"], key="mtf_v3")
        if st.button("🔎 ANALYSER V3 - SANS CLÉ", type="primary", use_container_width=True):
            nb_v = [b3_m, b2_m, b1_m].count("Verte")
            nb_r = [b3_m, b2_m, b1_m].count("Rouge")
            if mtf_m == "Contraire à 1m":
                st.warning("⏳ ATTENDRE - MTF Conflit : 1m dit une chose, 5m/15m disent l'inverse")
            elif vol_m == "Faible" and nb_v < 3 and nb_r < 3:
                st.warning("⏳ ATTENDRE - Volume faible + pas 3 bougies d'accord")
            elif nb_v == 3:
                st.success(f"🟢 CALL {paire} - 3 Soldats Blancs + Volume {vol_m} + MTF {mtf_m}")
            elif nb_r == 3:
                st.error(f"🔴 PUT {paire} - 3 Corbeaux Noirs + Volume {vol_m} + MTF {mtf_m}")
            elif nb_v == 2 and b1_m == "Verte":
                st.success(f"🟢 CALL {paire} - 2 Vertes + dernière verte")
            elif nb_r == 2 and b1_m == "Rouge":
                st.error(f"🔴 PUT {paire} - 2 Rouges + dernière rouge")
            else:
                st.warning(f"🟡 ATTENDRE {paire} - Pas clair")

st.caption("V3 ULTIME | MTF + Faux Cassure + Chandeliers Avancés + Volatilité Intelligente + Horaire/News + Volume + Historique | Ne trade jamais tout ton capital.")
