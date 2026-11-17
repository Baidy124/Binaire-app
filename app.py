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

# ================= ⚙️ NIVEAU FILTRE =================
NIVEAU_FILTRE = "DOUX"  # "TRES_DOUX" / "DOUX" / "MOYEN"

if NIVEAU_FILTRE == "TRES_DOUX":
    SEUIL_V2PRO = 3
    SEUIL_SCALPING = 2
    MTF_MIN_ACCORD = 2
    BLOQUER_FAUX_CASSURE = False
    BLOQUER_SQUEEZE = False
    BLOQUER_VOL_TROP_HAUTE = False
    BLOQUER_VOLUME_FAIBLE = False
    NB_DOJI_POUR_BLOQUER = 4
    SEUIL_VOLATILITE = 0.000005
    DISTANCE_SUPPORT = 0.05
    SEUIL_CORPS_BOUGIE = 0.05
elif NIVEAU_FILTRE == "MOYEN":
    SEUIL_V2PRO = 5
    SEUIL_SCALPING = 4
    MTF_MIN_ACCORD = 3
    BLOQUER_FAUX_CASSURE = True
    BLOQUER_SQUEEZE = True
    BLOQUER_VOL_TROP_HAUTE = True
    BLOQUER_VOLUME_FAIBLE = True
    NB_DOJI_POUR_BLOQUER = 2
    SEUIL_VOLATILITE = 0.00002
    DISTANCE_SUPPORT = 0.20
    SEUIL_CORPS_BOUGIE = 0.12
else:  # DOUX
    SEUIL_V2PRO = 3
    SEUIL_SCALPING = 2
    MTF_MIN_ACCORD = 2
    BLOQUER_FAUX_CASSURE = False
    BLOQUER_SQUEEZE = False
    BLOQUER_VOL_TROP_HAUTE = True
    BLOQUER_VOLUME_FAIBLE = False
    NB_DOJI_POUR_BLOQUER = 3
    SEUIL_VOLATILITE = 0.000008
    DISTANCE_SUPPORT = 0.08
    SEUIL_CORPS_BOUGIE = 0.06

st.set_page_config(page_title="BINAIRE V3.1 + ICHIMOKU + MTF", page_icon="📈", layout="wide")
st.title("📈 BINAIRE V3.1 + ICHIMOKU + MTF")
st.caption(f"Niveau : {NIVEAU_FILTRE} | V2 PRO {SEUIL_V2PRO}/6 | Scalping {SEUIL_SCALPING}/6 | MTF {MTF_MIN_ACCORD}/3")

if CLE_ACTIVE:
    st.success("✅ Clé OpenAI AUTOMATIQUE active")
else:
    st.info("ℹ️ Pas de clé. Capture en MANUEL.")

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
    "USD/BRL": "USDBRL=X", "EUR/BRL": "EURBRL=X", "USD/MXN": "USDMXN=X", "USD/ZAR": "USDZAR=X",
    "USD/TRY": "USDTRY=X", "USD/INR": "USDINR=X",
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "LTC/USD": "LTC-USD", "XRP/USD": "XRP-USD",
    "Dollar Index (DXY)": "DX-Y.NYB"
}

col_m1, col_m2 = st.columns(2)
with col_m1:
    mode = st.radio("Mode :", [f"📊 V2 PRO - {SEUIL_V2PRO}/6", f"⚡ SCALPING - {SEUIL_SCALPING}/6"], index=0)
with col_m2:
    use_mtf = st.checkbox("✅ 1. Multi-Timeframe + Ichimoku", value=True)
    use_faux = st.checkbox("✅ 2. Faux Cassure", value=True)
    use_vol_intel = st.checkbox("✅ 4. Volatilité Intelligente", value=True)
    use_volume = st.checkbox("✅ 6. Volume", value=True)
    use_horaire = st.checkbox("✅ 5. Horaire / News", value=True)
    use_ichi = st.checkbox("✅ 7. Ichimoku", value=True)

col1, col2 = st.columns(2)
with col1:
    paire = st.selectbox("Choisir un actif", list(PAIRES.keys()))
with col2:
    expiration = st.slider("Expiration SCALPING", 1, 5, 2) if mode.startswith("⚡") else st.slider("Expiration V2 PRO", 1, 19, 5)

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
        if not all(c in df.columns for c in cols[:4]):
            return pd.DataFrame()
        df = df[cols].copy()
        df = df.dropna(subset=["Open","High","Low","Close"])
        return df
    except Exception:
        return pd.DataFrame()

# ================= 🆕 ICHIMOKU =================
def calculer_ichimoku(df):
    df = df.copy()
    high = df["High"]; low = df["Low"]; close = df["Close"]
    # Tenkan = (plus haut 9 + plus bas 9) / 2
    df["TENKAN"] = (high.rolling(9).max() + low.rolling(9).min()) / 2
    # Kijun = (plus haut 26 + plus bas 26) / 2
    df["KIJUN"] = (high.rolling(26).max() + low.rolling(26).min()) / 2
    # Senkou A = (Tenkan + Kijun) / 2, décalé 26 en avant
    df["SENKOU_A"] = ((df["TENKAN"] + df["KIJUN"]) / 2).shift(26)
    # Senkou B = (plus haut 52 + plus bas 52) / 2, décalé 26
    df["SENKOU_B"] = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    # Chikou = Close décalé 26 en arrière
    df["CHIKOU"] = close.shift(-26)
    return df

def analyser_ichimoku(df):
    """Retourne CALL / PUT / NEUTRE + texte comme sur ta photo : 'Ichimoku CALL - DESSUS nuage'"""
    if len(df) < 60:
        return {"direction": "NEUTRE", "texte": "Ichimoku - Pas assez de données", "position": "NEUTRE", "tenkan_kijun": "NEUTRE"}
    c = df.iloc[-1]
    prix = c["Close"]
    sa = c["SENKOU_A"]; sb = c["SENKOU_B"]
    tenkan = c["TENKAN"]; kijun = c["KIJUN"]
    if pd.isna(sa) or pd.isna(sb) or pd.isna(tenkan) or pd.isna(kijun):
        return {"direction": "NEUTRE", "texte": "Ichimoku - En calcul...", "position": "NEUTRE", "tenkan_kijun": "NEUTRE"}
    nuage_haut = max(sa, sb)
    nuage_bas = min(sa, sb)
    # Position prix vs nuage
    if prix > nuage_haut:
        position = "DESSUS nuage"
        score_pos = 1
    elif prix < nuage_bas:
        position = "DESSOUS nuage"
        score_pos = -1
    else:
        position = "DANS nuage"
        score_pos = 0
    # Tenkan vs Kijun
    if tenkan > kijun:
        tk = "Tenkan > Kijun (HAUSSE)"
        score_tk = 1
    elif tenkan < kijun:
        tk = "Tenkan < Kijun (BAISSE)"
        score_tk = -1
    else:
        tk = "Tenkan = Kijun"
        score_tk = 0
    # Prix vs Tenkan / Kijun
    if prix > tenkan and prix > kijun:
        score_prix = 1
    elif prix < tenkan and prix < kijun:
        score_prix = -1
    else:
        score_prix = 0
    total = score_pos + score_tk + score_prix
    if total >= 2:
        direction = "CALL"
        texte = f"Ichimoku CALL - {position}"
    elif total <= -2:
        direction = "PUT"
        texte = f"Ichimoku PUT - {position}"
    else:
        direction = "NEUTRE"
        texte = f"Ichimoku NEUTRE - {position}"
    return {"direction": direction, "texte": texte, "position": position, "tenkan_kijun": tk,
            "prix": prix, "tenkan": tenkan, "kijun": kijun, "senkou_a": sa, "senkou_b": sb,
            "nuage_haut": nuage_haut, "nuage_bas": nuage_bas, "score": total}

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
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / df["BB_MID"]
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
    if "Volume" in df.columns:
        df["VOL_MOYEN"] = df["Volume"].rolling(20).mean()
    # 🆕 Ajout Ichimoku dans les indicateurs
    df = calculer_ichimoku(df)
    return df

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
    if nb_hausse == 3:
        figure_3 = "🟢 3 Soldats Blancs" if b1["Close"] > b2["Close"] > b3["Close"] else "🟢 3 Bougies Vertes"; direction_3 = "HAUSSE"; force_3 = "Forte"
    elif nb_baisse == 3:
        figure_3 = "🔴 3 Corbeaux Noirs" if b1["Close"] < b2["Close"] < b3["Close"] else "🔴 3 Bougies Rouges"; direction_3 = "BAISSE"; force_3 = "Forte"
    elif nb_hausse == 2 and dir1 == "HAUSSE":
        figure_3 = "🟢 2 Vertes / 1 Rouge - Dernière verte"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
    elif nb_baisse == 2 and dir1 == "BAISSE":
        figure_3 = "🔴 2 Rouges / 1 Verte - Dernière rouge"; direction_3 = "BAISSE"; force_3 = "Moyenne"
    elif nb_doji >= 2:
        figure_3 = "🟡 Beaucoup de Doji"; direction_3 = "NEUTRE"; force_3 = "Faible"
    return {"liste": liste, "figure_3": figure_3, "direction_3": direction_3, "force_3": force_3, "nb_hausse": nb_hausse, "nb_baisse": nb_baisse, "nb_doji": nb_doji, "chandelier": figure_3, "direction": direction_3}

# ================= 🆕 MTF + ICHIMOKU =================
def analyser_mtf(ticker):
    resultats = {}
    resultats_ichi = {}
    for interval, period in [("1m","1d"), ("5m","5d"), ("15m","5d")]:
        df = recuperer_donnees(ticker, interval=interval, period=period)
        if df.empty or len(df) < 50:
            resultats[interval] = "NEUTRE"; resultats_ichi[interval] = "NEUTRE"; continue
        df = calculer_indicateurs(df)
        df = df.iloc[:-1].copy()
        df = df.dropna(subset=["RSI","EMA50"])
        if df.empty:
            resultats[interval] = "NEUTRE"; resultats_ichi[interval] = "NEUTRE"; continue
        c = df.iloc[-1]
        # MTF classique EMA + RSI
        if c["EMA9"] > c["EMA21"] and c["RSI"] > 50:
            resultats[interval] = "HAUSSE"
        elif c["EMA9"] < c["EMA21"] and c["RSI"] < 50:
            resultats[interval] = "BAISSE"
        else:
            resultats[interval] = "NEUTRE"
        # 🆕 MTF Ichimoku sur chaque timeframe
        ichi = analyser_ichimoku(df)
        if ichi["direction"] == "CALL":
            resultats_ichi[interval] = "HAUSSE"
        elif ichi["direction"] == "PUT":
            resultats_ichi[interval] = "BAISSE"
        else:
            resultats_ichi[interval] = "NEUTRE"
    nb_h = list(resultats.values()).count("HAUSSE"); nb_b = list(resultats.values()).count("BAISSE")
    nb_h_ichi = list(resultats_ichi.values()).count("HAUSSE"); nb_b_ichi = list(resultats_ichi.values()).count("BAISSE")
    # On combine EMA + Ichimoku : si les 2 disent pareil, c'est plus fort
    if nb_h >= MTF_MIN_ACCORD and nb_h_ichi >= MTF_MIN_ACCORD:
        accord = f"✅ MTF HAUSSE FORT ({nb_h}/3 EMA + {nb_h_ichi}/3 Ichimoku)"; direction_mtf = "HAUSSE"
    elif nb_b >= MTF_MIN_ACCORD and nb_b_ichi >= MTF_MIN_ACCORD:
        accord = f"✅ MTF BAISSE FORT ({nb_b}/3 EMA + {nb_b_ichi}/3 Ichimoku)"; direction_mtf = "BAISSE"
    elif nb_h >= MTF_MIN_ACCORD:
        accord = f"✅ MTF HAUSSE ({nb_h}/3) - Ichimoku {nb_h_ichi}/3"; direction_mtf = "HAUSSE"
    elif nb_b >= MTF_MIN_ACCORD:
        accord = f"✅ MTF BAISSE ({nb_b}/3) - Ichimoku {nb_b_ichi}/3"; direction_mtf = "BAISSE"
    elif nb_h > 0 and nb_b > 0 and nb_h != nb_b:
        if NIVEAU_FILTRE in ["DOUX","TRES_DOUX"]:
            if nb_h > nb_b:
                accord = f"🟡 MTF Mixte mais HAUSSE plus forte ({nb_h} vs {nb_b})"; direction_mtf = "HAUSSE"
            else:
                accord = f"🟡 MTF Mixte mais BAISSE plus forte ({nb_b} vs {nb_h})"; direction_mtf = "BAISSE"
        else:
            accord = "🔴 CONFLIT MTF"; direction_mtf = "CONFLIT"
    elif nb_h == nb_b and nb_h > 0:
        accord = "🔴 CONFLIT MTF Égal"; direction_mtf = "CONFLIT"
    else:
        accord = "🟡 MTF Neutre"; direction_mtf = "NEUTRE"
    return {"details": resultats, "details_ichi": resultats_ichi, "accord": accord, "direction": direction_mtf, "nb_h": nb_h, "nb_b": nb_b, "nb_h_ichi": nb_h_ichi, "nb_b_ichi": nb_b_ichi}

def detecter_faux_cassure(df):
    if len(df) < 6:
        return {"faux": False, "texte": "Pas assez de données"}
    c = df.iloc[-1]; res = c["RESISTANCE"]; sup = c["SUPPORT"]
    a_casse_resistance = False; a_casse_support = False
    for i in range(-5, -1):
        row = df.iloc[i]
        if pd.notna(res) and row["Close"] > res:
            a_casse_resistance = True
        if pd.notna(sup) and row["Close"] < sup:
            a_casse_support = True
    prix_actuel = c["Close"]
    if a_casse_resistance and pd.notna(res) and prix_actuel < res:
        return {"faux": True, "texte": "⚠️ FAUX BREAKOUT HAUSSIER - Piège !", "type": "FAUX_HAUSSE"}
    if a_casse_support and pd.notna(sup) and prix_actuel > sup:
        return {"faux": True, "texte": "⚠️ FAUX BREAKOUT BAISSIER - Piège !", "type": "FAUX_BAISSE"}
    return {"faux": False, "texte": "✅ Pas de faux breakout.", "type": "OK"}

def analyser_volatilite_intelligente(df):
    c = df.iloc[-1]; atr = c["ATR"]; atr_moyen = c["ATR_MOYEN"]; bb_width = c["BB_WIDTH"]
    bb_moyen = df["BB_WIDTH"].rolling(50).mean().iloc[-1]
    if pd.isna(atr) or pd.isna(atr_moyen) or pd.isna(bb_width):
        return {"statut": "NEUTRE", "texte": "Volatilité : Données insuffisantes"}
    if bb_width < bb_moyen * 0.7:
        return {"statut": "SQUEEZE", "texte": f"🟡 SQUEEZE : Bandes serrées ({bb_width:.4f} vs {bb_moyen:.4f})"}
    if atr > atr_moyen * 1.8:
        return {"statut": "TROP_HAUTE", "texte": f"🔴 Volatilité TROP HAUTE : ATR {atr:.5f} vs {atr_moyen:.5f}."}
    if atr < atr_moyen * 0.5:
        return {"statut": "TROP_BASSE", "texte": f"🟡 Volatilité TROP BASSE : ATR {atr:.5f} vs {atr_moyen:.5f}."}
    return {"statut": "NORMALE", "texte": f"✅ Volatilité NORMALE : ATR {atr:.5f} vs {atr_moyen:.5f}."}

def analyser_horaire():
    now = datetime.now(timezone.utc); heure = now.hour; jour = now.weekday()
    avertissements = []
    if jour == 6:
        avertissements.append("🔴 DIMANCHE : Marché fermé.")
    if 12 <= heure < 14:
        avertissements.append("🟡 12h-14h GMT : Pause déjeuner - Faux signaux possibles.")
    if heure in [8, 14]:
        avertissements.append("⚠️ HEURE DE NEWS : 8h30 / 14h30 GMT")
    if 0 <= heure < 6:
        avertissements.append("🟡 00h-06h GMT : Session Asie seule.")
    if 7 <= heure < 10:
        avertissements.append("✅ 07h-10h GMT : Ouverture Londres")
    if 13 <= heure < 17:
        avertissements.append("✅ 13h-17h GMT : Londres + New York")
    if not avertissements:
        avertissements.append(f"✅ Heure OK : {now.strftime('%H:%M')} GMT")
    return {"heure_gmt": now.strftime("%H:%M GMT"), "jour": ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][jour], "avertissements": avertissements}

def analyser_volume(df):
    if "Volume" not in df.columns:
        return {"statut": "SANS_VOLUME", "texte": "⚠️ Pas de volume pour cet actif."}
    c = df.iloc[-1]; vol = c["Volume"]; vol_moyen = c["VOL_MOYEN"]
    if pd.isna(vol) or pd.isna(vol_moyen) or vol_moyen == 0:
        return {"statut": "NEUTRE", "texte": "Volume : Données insuffisantes"}
    ratio = vol / vol_moyen
    if ratio > 1.5:
        return {"statut": "FORT", "texte": f"✅ Volume FORT : {ratio:.2f}x", "ratio": ratio}
    if ratio < 0.7:
        return {"statut": "FAIBLE", "texte": f"⚠️ Volume FAIBLE : {ratio:.2f}x", "ratio": ratio}
    return {"statut": "NORMAL", "texte": f"✅ Volume NORMAL : {ratio:.2f}x", "ratio": ratio}

def analyser_signal_v3(df, ticker, is_scalping=False, use_mtf=True, use_faux=True, use_vol_intel=True, use_volume=True, use_ichi=True):
    c = df.iloc[-1]; prix = c["Close"]; atr = c["ATR"]
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
    mtf = analyser_mtf(ticker) if use_mtf else {"direction": "NEUTRE", "accord": "MTF OFF", "details": {}, "details_ichi": {}}
    faux = detecter_faux_cassure(df) if use_faux else {"faux": False, "texte": "Faux OFF"}
    vol_intel = analyser_volatilite_intelligente(df) if use_vol_intel else {"statut": "NEUTRE", "texte": "Volatilité OFF"}
    vol = analyser_volume(df) if use_volume else {"statut": "NEUTRE", "texte": "Volume OFF"}
    # 🆕 Ichimoku sur 1m
    ichi = analyser_ichimoku(df) if use_ichi else {"direction": "NEUTRE", "texte": "Ichimoku OFF", "position": "NEUTRE"}
    # 🆕 Bonus Ichimoku : si Ichimoku dit CALL et score HAUSSE, on booste
    if use_ichi and ichi["direction"] == "CALL" and score_haut >= 2:
        score_haut += 1  # Bonus Ichimoku
    if use_ichi and ichi["direction"] == "PUT" and score_bas >= 2:
        score_bas += 1
    base = {"score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol, "ichi": ichi}
    # FILTRES
    if faux["faux"] and BLOQUER_FAUX_CASSURE:
        return {"signal": "ATTENDRE", "raison": f"FAUX CASSURE : {faux['texte']}", **base}
    if vol_intel["statut"] == "SQUEEZE" and BLOQUER_SQUEEZE:
        return {"signal": "ATTENDRE", "raison": f"SQUEEZE : {vol_intel['texte']}", **base}
    if vol_intel["statut"] == "TROP_HAUTE" and BLOQUER_VOL_TROP_HAUTE:
        return {"signal": "ATTENDRE", "raison": f"VOLATILITÉ TROP HAUTE : {vol_intel['texte']}", **base}
    if mtf["direction"] == "CONFLIT":
        return {"signal": "ATTENDRE", "raison": f"MTF CONFLIT : {mtf['accord']}", **base}
    if volatilite_faible:
        return {"signal": "ATTENDRE", "raison": "Volatilité vraiment trop faible", **base}
    if trop_de_doji:
        return {"signal": "ATTENDRE", "raison": f"{info_3['nb_doji']} Doji", **base}
    if bougie_faible and direction == "NEUTRE":
        return {"signal": "ATTENDRE", "raison": "Bougie trop petite + neutre", **base}
    if vol.get("statut") == "FAIBLE" and BLOQUER_VOLUME_FAIBLE:
        return {"signal": "ATTENDRE", "raison": f"VOLUME : {vol['texte']}", **base}
    # 🆕 Ichimoku contraire TOTAL bloque : ex prix DESSOUS nuage + on veut CALL avec score faible
    if use_ichi and ichi["direction"] == "PUT" and score_haut >= 5 and score_bas <= 1:
        return {"signal": "ATTENDRE", "raison": f"Ichimoku totalement opposé : {ichi['texte']} vs score HAUSSE fort", **base}
    if use_ichi and ichi["direction"] == "CALL" and score_bas >= 5 and score_haut <= 1:
        return {"signal": "ATTENDRE", "raison": f"Ichimoku totalement opposé : {ichi['texte']} vs score BAISSE fort", **base}
    # SIGNAL
    if is_scalping:
        scalp_haut_rapide = (c["EMA5"] > c["EMA9"] and c["RSI7"] > 50)
        scalp_bas_rapide = (c["EMA5"] < c["EMA9"] and c["RSI7"] < 50)
        if score_haut >= seuil and scalp_haut_rapide and not proche_resistance:
            return {"signal": "CALL / HAUSSE", "raison": f"SCALPING : {score_haut}/6 + EMA5 + RSI7 + MTF {mtf['direction']} + {ichi['texte']}", **{**base, "direction": "HAUSSE"}}
        if score_bas >= seuil and scalp_bas_rapide and not proche_support:
            return {"signal": "PUT / BAISSE", "raison": f"SCALPING : {score_bas}/6 + EMA5 + RSI7 + MTF {mtf['direction']} + {ichi['texte']}", **{**base, "direction": "BAISSE"}}
        if score_haut >= seuil - 1 and mtf["direction"] == "HAUSSE":
            return {"signal": "CALL / HAUSSE", "raison": f"Score {score_haut} proche seuil + MTF HAUSSE + {ichi['texte']}", **{**base, "direction": "HAUSSE"}}
        if score_bas >= seuil - 1 and mtf["direction"] == "BAISSE":
            return {"signal": "PUT / BAISSE", "raison": f"Score {score_bas} proche seuil + MTF BAISSE + {ichi['texte']}", **{**base, "direction": "BAISSE"}}
        return {"signal": "ATTENDRE", "raison": f"SCALPING : Pas {seuil}/6 + EMA5/RSI7", **base}
    if score_haut >= seuil and not proche_resistance:
        return {"signal": "CALL / HAUSSE", "raison": f"{score_haut}/6 HAUSSE + MTF {mtf['direction']} + {ichi['texte']} + {chandelier}", **{**base, "direction": "HAUSSE"}}
    if score_bas >= seuil and not proche_support:
        return {"signal": "PUT / BAISSE", "raison": f"{score_bas}/6 BAISSE + MTF {mtf['direction']} + {ichi['texte']} + {chandelier}", **{**base, "direction": "BAISSE"}}
    if score_haut >= seuil and proche_resistance:
        return {"signal": "ATTENDRE", "raison": "Collé à la Résistance", **base}
    if score_bas >= seuil and proche_support:
        return {"signal": "ATTENDRE", "raison": "Collé au Support", **base}
    if mtf["direction"] == "HAUSSE" and score_haut > score_bas and score_haut >= 2:
        return {"signal": "CALL / HAUSSE", "raison": f"MTF HAUSSE + Score {score_haut} > {score_bas} + {ichi['texte']}", **{**base, "direction": "HAUSSE"}}
    if mtf["direction"] == "BAISSE" and score_bas > score_haut and score_bas >= 2:
        return {"signal": "PUT / BAISSE", "raison": f"MTF BAISSE + Score {score_bas} > {score_haut} + {ichi['texte']}", **{**base, "direction": "BAISSE"}}
    # 🆕 Dernier recours Ichimoku : si Ichimoku seul dit CALL/PUT et score >=2, on prend
    if use_ichi and ichi["direction"] == "CALL" and score_haut >= 2 and score_haut > score_bas:
        return {"signal": "CALL / HAUSSE", "raison": f"Ichimoku CALL + Score {score_haut} > {score_bas} : {ichi['texte']}", **{**base, "direction": "HAUSSE"}}
    if use_ichi and ichi["direction"] == "PUT" and score_bas >= 2 and score_bas > score_haut:
        return {"signal": "PUT / BAISSE", "raison": f"Ichimoku PUT + Score {score_bas} > {score_haut} : {ichi['texte']}", **{**base, "direction": "BAISSE"}}
    return {"signal": "ATTENDRE", "raison": f"Pas {seuil}/6 - HAUSSE {score_haut}, BAISSE {score_bas} - {ichi['texte']}", **base}

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

if st.button("🔍 ANALYSER MAINTENANT - V3.1 + ICHIMOKU + MTF", type="primary"):
    is_scalp = mode.startswith("⚡")
    with st.spinner("Analyse V3.1..."):
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
                analyse = analyser_signal_v3(df, ticker, is_scalping=is_scalp, use_mtf=use_mtf, use_faux=use_faux, use_vol_intel=use_vol_intel, use_volume=use_volume, use_ichi=use_ichi)
                c = df.iloc[-1]
                st.session_state.historique.append({"Heure": datetime.now().strftime("%H:%M:%S"), "Paire": paire, "Mode": "SCALPING" if is_scalp else "V2 PRO", "Signal": analyse["signal"], "Prix": round(float(c["Close"]),5), "Score H": analyse["score_haut"], "Score B": analyse["score_bas"], "MTF": analyse["mtf"]["direction"], "Ichimoku": analyse["ichi"]["texte"], "Résultat": "En attente"})
                st.divider()
                st.subheader(f"🎯 SIGNAL V3.1 - {NIVEAU_FILTRE}")
                st.metric("Prix", f"{c['Close']:.5f}")
                st.metric("RSI 14 / RSI 7", f"{c['RSI']:.1f} / {c['RSI7']:.1f}")
                st.metric("EMA 5 / 9 / 21", f"{c['EMA5']:.5f} / {c['EMA9']:.5f} / {c['EMA21']:.5f}")
                if analyse["signal"] == "CALL / HAUSSE":
                    st.success(f"🟢 CALL - {expiration} mn - VALIDÉ")
                elif analyse["signal"] == "PUT / BAISSE":
                    st.error(f"🔴 PUT - {expiration} mn - VALIDÉ")
                else:
                    st.warning("⏳ ATTENDRE")
                st.write("**Motif :**", analyse["raison"])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Score HAUSSE", f"{analyse['score_haut']}/6")
                with col2:
                    st.metric("Score BAISSE", f"{analyse['score_bas']}/6")
                # 🆕 AFFICHAGE ICHIMOKU COMME SUR TA PHOTO
                st.divider()
                st.subheader("7️⃣ Ichimoku - NOUVEAU")
                ichi = analyse["ichi"]
                st.info(f"**{ichi['texte']}** | Tenkan : {ichi.get('tenkan',0):.5f} | Kijun : {ichi.get('kijun',0):.5f} | Nuage : {ichi.get('nuage_bas',0):.5f} - {ichi.get('nuage_haut',0):.5f} | {ichi.get('tenkan_kijun','')}")
                if ichi["direction"] == "CALL":
                    st.success("🟢 Ichimoku dit CALL - Prix DESSUS nuage")
                elif ichi["direction"] == "PUT":
                    st.error("🔴 Ichimoku dit PUT - Prix DESSOUS nuage")
                else:
                    st.warning("🟡 Ichimoku NEUTRE - Prix DANS nuage ou Tenkan/Kijun mélangés")
                st.divider()
                st.subheader("1️⃣ Multi-Timeframe + Ichimoku - NOUVEAU")
                st.info(analyse["mtf"]["accord"])
                st.write("**MTF EMA+RSI :**", analyse["mtf"]["details"])
                st.write("**MTF Ichimoku :**", analyse["mtf"].get("details_ichi", {}))
                st.dataframe(pd.DataFrame([analyse["mtf"]["details"], analyse["mtf"].get("details_ichi", {})], index=["EMA+RSI", "Ichimoku"]), use_container_width=True)
                st.subheader("2️⃣ Faux Cassure")
                if analyse["faux"]["faux"]:
                    st.warning(analyse["faux"]["texte"])
                else:
                    st.success(analyse["faux"]["texte"])
                st.subheader("4️⃣ Volatilité")
                st.info(analyse["vol_intel"]["texte"])
                st.subheader("6️⃣ Volume")
                st.info(analyse["vol"]["texte"])
                st.divider()
                st.subheader("🕯️ 3. Chandeliers")
                st.info(f"**Figure :** {analyse['info_3']['figure_3']} | **Vertes :** {analyse['info_3']['nb_hausse']} | **Rouges :** {analyse['info_3']['nb_baisse']} | **Doji :** {analyse['info_3']['nb_doji']}")
                st.dataframe(pd.DataFrame(analyse["info_3"]["liste"]), use_container_width=True, hide_index=True)
                st.subheader("📈 Graphique + Ichimoku")
                st.line_chart(df[["Close","BB_UPPER","BB_MID","BB_LOWER","EMA5","EMA9","EMA21","TENKAN","KIJUN"]].tail(100))

st.divider()
st.header("📊 7. Historique")
if len(st.session_state.historique) == 0:
    st.info("Aucun signal encore.")
else:
    df_hist = pd.DataFrame(st.session_state.historique)
    st.dataframe(df_hist, use_container_width=True, hide_index=True)
    if st.button("🗑️ Effacer l'historique"):
        st.session_state.historique = []
        st.rerun()

st.caption(f"V3.1 + ICHIMOKU + MTF | Niveau {NIVEAU_FILTRE} | Pour changer, modifie NIVEAU_FILTRE en haut.")
