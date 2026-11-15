import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os, base64, uuid
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="IQ OPTION AI TRADER V7.3 CORRIGÉ", page_icon="📈", layout="wide")

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

SEUIL_V2PRO = 5; SEUIL_SCALPING = 4
BLOQUER_FAUX_CASSURE = True; BLOQUER_SQUEEZE = True; BLOQUER_VOL_TROP_HAUTE = True; BLOQUER_VOLUME_FAIBLE = True
NB_DOJI_POUR_BLOQUER = 2; SEUIL_VOLATILITE = 0.00002; SEUIL_CORPS_BOUGIE = 0.12
PAYOUT_IQ_OPTION = 0.85
HEURE_DEBUT = 7; HEURE_FIN = 17; HEURE_PAUSE_DEBUT = 12; HEURE_PAUSE_FIN = 14
MAX_TRADES_PAR_JOUR = 8

st.title("📈 IQ OPTION AI TRADER V7.3 - CORRIGÉ")
st.caption(f"V7.3 CORRIGÉ | 2m signaux | V2 PRO {SEUIL_V2PRO}/6 | MTF STRICT VRAI 5m/15m | ICHIMOKU CORRIGÉ 2/3")
st.warning("⚠️ Mode 1 Précis (1m) ≠ Mode 2 Approximatif (2m). Ne jamais mélanger. Lundi = DÉMO uniquement.")
st.info("💡 Avec payout 85%, il faut 55% minimum pour ne pas perdre.")
st.success("✅ V7.3 : 4 erreurs corrigées - Ichimoku souple, NaN gérés, variable sb_ichi, Chikou propre")

if CLE_ACTIVE:
    st.success("✅ Clé OpenAI active")
else:
    st.info("ℹ️ Pas de clé. Capture en MANUEL.")

FICHIER_HISTORIQUE = "historique_v7.csv"
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
    "Dollar Index (DXY)": "DX-Y.NYB", "Dollar Index (DXY) - Secours": "^DXY",
}

col_m1, col_m2 = st.columns(2)
with col_m1:
    mode = st.radio("Mode :", [f"📊 V2 PRO - {SEUIL_V2PRO}/6", f"⚡ SCALPING - {SEUIL_SCALPING}/6"], index=0)
with col_m2:
    use_mtf = st.checkbox("✅ MTF 2m-5m-15m STRICT VRAI", value=True)
    use_faux = st.checkbox("✅ Faux Cassure", value=True)
    use_vol_intel = st.checkbox("✅ Volatilité Intelligente", value=True)
    use_volume = st.checkbox("✅ Volume", value=True)
    use_horaire = st.checkbox("✅ Horaire / News", value=True)
    use_ichimoku = st.checkbox("✅ Ichimoku - Filtre Nuage CORRIGÉ", value=True)

col1, col2 = st.columns(2)
with col1:
    paire = st.selectbox("Choisir un actif", list(PAIRES.keys()))
with col2:
    expiration = st.slider("Expiration SCALPING", 1, 5, 2) if mode.startswith("⚡") else st.slider("Expiration V2 PRO", 1, 19, 5)

@st.cache_data(ttl=300, show_spinner=False)
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
        df = df[~df.index.duplicated(keep="first")]
        df = df.sort_index()
        return df
    except Exception:
        return pd.DataFrame()

def recuperer_donnees_avec_secours(ticker, interval="2m", period="1d", paire_nom=""):
    df = recuperer_donnees(ticker, interval=interval, period=period)
    if df.empty and paire_nom == "Dollar Index (DXY)":
        df = recuperer_donnees("^DXY", interval=interval, period=period)
    return df

def garder_que_les_bougies_fermees(df, interval="2m"):
    if df is None or df.empty:
        return df
    try:
        if len(df) < 2:
            return df
        last_time = df.index[-1]
        now_server = datetime.now(timezone.utc)
        last_utc = last_time.tz_localize("UTC") if last_time.tzinfo is None else last_time.tz_convert("UTC")
        age = (now_server - last_utc).total_seconds()
        minutes = {"1m": 1, "2m": 2, "5m": 5, "15m": 15}.get(interval, 2)
        if age < minutes * 60 + 5:
            return df.iloc[:-1].copy()
        return df.copy()
    except Exception:
        return df.iloc[:-1].copy() if len(df) > 1 else df

# ✅ V7.3 - ICHIMOKU CORRIGÉ DIRECTEMENT DANS LE CODE
# Erreur 4 corrigée : Chikou NaN propre
# Erreur 1 corrigée : Signal souple 2/3, pas 4/4
# Erreur 3 corrigée : NaN gérés avec ichi_position
def ajouter_ichimoku(df):
    df = df.copy()

    # Tenkan-sen
    high_9 = df["High"].rolling(9).max()
    low_9 = df["Low"].rolling(9).min()
    df["tenkan"] = (high_9 + low_9) / 2

    # Kijun-sen
    high_26 = df["High"].rolling(26).max()
    low_26 = df["Low"].rolling(26).min()
    df["kijun"] = (high_26 + low_26) / 2

    # Senkou Span A
    df["senkou_a"] = (
        (df["tenkan"] + df["kijun"]) / 2
    ).shift(26)

    # Senkou Span B
    high_52 = df["High"].rolling(52).max()
    low_52 = df["Low"].rolling(52).min()

    df["senkou_b"] = (
        (high_52 + low_52) / 2
    ).shift(26)

    # Confirmation Chikou sans anticipation - CORRIGÉE
    # Avant : les 26 premières bougies donnaient False à tort
    # Maintenant : NaN -> 0 -> False, mais on sait que c'est "pas assez de données" via ichi_position
    close_shift26 = df["Close"].shift(26)
    df["chikou_haussier"] = np.where(close_shift26.isna(), 0, (df["Close"] > close_shift26).astype(int)).astype(bool)
    df["chikou_baissier"] = np.where(close_shift26.isna(), 0, (df["Close"] < close_shift26).astype(int)).astype(bool)

    # Nuage Haut / Bas
    nuage_haut = df[["senkou_a", "senkou_b"]].max(axis=1)
    nuage_bas = df[["senkou_a", "senkou_b"]].min(axis=1)
    df["nuage_haut"] = nuage_haut
    df["nuage_bas"] = nuage_bas

    # Position : 1 = Dessus, -1 = Dessous, 0 = Dans, NaN = Pas assez de données
    df["ichi_position"] = np.where(
        df["senkou_a"].isna() | df["senkou_b"].isna(), np.nan,
        np.where(df["Close"] > nuage_haut, 1,
        np.where(df["Close"] < nuage_bas, -1, 0))
    )

    # Score Ichimoku 2/3 - CORRIGÉ, pas 4/4
    score_h_ichi = (
        (df["tenkan"] > df["kijun"]).astype(int) +
        df["chikou_haussier"].astype(int) +
        (df["senkou_a"] > df["senkou_b"]).astype(int)
    )
    score_b_ichi = (
        (df["tenkan"] < df["kijun"]).astype(int) +
        df["chikou_baissier"].astype(int) +
        (df["senkou_a"] < df["senkou_b"]).astype(int)
    )
    df["ichi_score_h"] = score_h_ichi
    df["ichi_score_b"] = score_b_ichi

    df["ichi_signal"] = "ATTENDRE"
    cond_call = (df["ichi_position"] == 1) & (score_h_ichi >= 2)
    cond_put = (df["ichi_position"] == -1) & (score_b_ichi >= 2)
    df.loc[cond_call, "ichi_signal"] = "CALL"
    df.loc[cond_put, "ichi_signal"] = "PUT"
    df.loc[df["ichi_position"] == 0, "ichi_signal"] = "ATTENDRE"

    return df

def calculer_position_ichimoku(row):
    try:
        if pd.isna(row.get("senkou_a")) or pd.isna(row.get("senkou_b")) or pd.isna(row.get("tenkan")) or pd.isna(row.get("kijun")):
            return {"position": "PAS ASSEZ DE DONNÉES", "signal": "ATTENDRE", "texte": "Ichimoku : Pas assez de bougies (il faut 78+ bougies)", "nuage_haut": np.nan, "nuage_bas": np.nan, "tenkan": np.nan, "kijun": np.nan, "senkou_a": np.nan, "senkou_b": np.nan}
        prix = float(row["Close"])
        sa = float(row["senkou_a"]); sb_ichi = float(row["senkou_b"])
        tenkan = float(row["tenkan"]); kijun = float(row["kijun"])
        chikou_h = bool(row["chikou_haussier"]); chikou_b = bool(row["chikou_baissier"])
        nuage_haut = max(sa, sb_ichi); nuage_bas = min(sa, sb_ichi)
        pos = row.get("ichi_position", np.nan)
        sig = row.get("ichi_signal", "ATTENDRE")
        if pos == 1:
            position = "DESSUS NUAGE 🟢"
        elif pos == -1:
            position = "DESSOUS NUAGE 🔴"
        elif pos == 0:
            position = "DANS LE NUAGE 🟡 - ATTENDRE"
        else:
            position = "PAS ASSEZ DE DONNÉES"
        if sig == "CALL":
            texte = f"Ichimoku CALL : Prix {position} + Tenkan {tenkan:.5f} > Kijun {kijun:.5f} + Chikou Haussier + Nuage Haussier (2/3 validés)"
        elif sig == "PUT":
            texte = f"Ichimoku PUT : Prix {position} + Tenkan {tenkan:.5f} < Kijun {kijun:.5f} + Chikou Baissier + Nuage Baissier (2/3 validés)"
        elif pos == 0:
            texte = f"Ichimoku ATTENDRE : Prix {position} - Ne jamais trader dans le nuage"
        else:
            texte = f"Ichimoku ATTENDRE : Prix {position} - Tenkan/Kijun/Chikou pas alignés (moins de 2/3)"
        return {"position": position, "signal": sig, "texte": texte, "nuage_haut": nuage_haut, "nuage_bas": nuage_bas, "tenkan": tenkan, "kijun": kijun, "senkou_a": sa, "senkou_b": sb_ichi}
    except Exception as e:
        return {"position": "ERREUR", "signal": "ATTENDRE", "texte": f"Ichimoku erreur : {e}"}

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
    deviation = (typical - moyenne).abs().rolling(14).mean()
    df["WCCI"] = ((typical - moyenne) / (0.015 * deviation.replace(0, np.nan)))
    def _cfo_corrige(close_series, window=14):
        arr = close_series.values.astype(float)
        n = len(arr)
        out = np.full(n, np.nan)
        x = np.arange(window, dtype=float)
        x_mean = x.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return out
        for i in range(window - 1, n):
            y = arr[i - window + 1: i + 1]
            if np.isnan(y).any():
                continue
            y_m = y.mean()
            pente = ((x - x_mean) * (y - y_m)).sum() / denom
            intercept = y_m - pente * x_mean
            forecast_i = pente * (window - 1) + intercept
            if y[-1] != 0:
                out[i] = ((y[-1] - forecast_i) / y[-1]) * 100
        return out
    df["CFO"] = _cfo_corrige(close, 14)
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
    ema9 = df["EMA9"].values; ema21 = df["EMA21"].values; ema50 = df["EMA50"].values
    rsi = df["RSI"].values; wcci = df["WCCI"].values; cfo = df["CFO"].values; macd_hist = df["MACD_HIST"].values; bb_mid = df["BB_MID"].values
    close_v = close.values
    tendance_h = (ema9 > ema21) & (ema21 > ema50)
    tendance_b = (ema9 < ema21) & (ema21 < ema50)
    df["SCORE_H"] = (tendance_h.astype(int) + ((rsi > 50) & (rsi < 70)).astype(int) + (wcci > 0).astype(int) + (cfo > 0).astype(int) + (macd_hist > 0).astype(int) + (close_v > bb_mid).astype(int))
    df["SCORE_B"] = (tendance_b.astype(int) + ((rsi > 30) & (rsi < 50)).astype(int) + (wcci < 0).astype(int) + (cfo < 0).astype(int) + (macd_hist < 0).astype(int) + (close_v < bb_mid).astype(int))
    o = df["Open"].values; c = df["Close"].values; h = df["High"].values; l = df["Low"].values
    corps = np.abs(c - o); amp = h - l
    ratio = np.divide(corps, amp, out=np.zeros_like(corps, dtype=float), where=amp != 0)
    direction = np.where(ratio < 0.10, 0, np.where(c > o, 1, -1))
    df["DIR"] = direction
    df["RATIO_CORPS"] = ratio
    df["CORPS_FAIBLE"] = (amp <= 0) | (ratio < SEUIL_CORPS_BOUGIE)
    df = ajouter_ichimoku(df)
    return df

def decrire_une_bougie(row):
    try:
        o = float(row["Open"]); c = float(row["Close"]); h = float(row["High"]); l = float(row["Low"])
    except Exception:
        return "Invalide", "NEUTRE", 0
    corps = abs(c - o); amplitude = h - l
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
        return {"liste": [], "figure_3": "Pas assez", "direction_3": "NEUTRE", "force_3": "Faible", "nb_hausse": 0, "nb_baisse": 0, "nb_doji": 0, "chandelier": "Pas assez", "direction": "NEUTRE", "derniere_direction": "NEUTRE", "derniere_est_doji": True}
    b3 = df.iloc[-3]; b2 = df.iloc[-2]; b1 = df.iloc[-1]
    desc3, dir3, ratio3 = decrire_une_bougie(b3)
    desc2, dir2, ratio2 = decrire_une_bougie(b2)
    desc1, dir1, ratio1 = decrire_une_bougie(b1)
    def sf(x):
        try:
            return round(float(x), 5)
        except Exception:
            return 0.0
    liste = [
        {"Bougie": "Bougie -3", "Type": desc3, "Direction": dir3, "Open": sf(b3["Open"]), "Close": sf(b3["Close"]), "Corps %": round(ratio3*100,1)},
        {"Bougie": "Bougie -2", "Type": desc2, "Direction": dir2, "Open": sf(b2["Open"]), "Close": sf(b2["Close"]), "Corps %": round(ratio2*100,1)},
        {"Bougie": "Bougie -1", "Type": desc1, "Direction": dir1, "Open": sf(b1["Open"]), "Close": sf(b1["Close"]), "Corps %": round(ratio1*100,1)},
    ]
    nb_h = sum([1 for d in [dir3, dir2, dir1] if d == "HAUSSE"])
    nb_b = sum([1 for d in [dir3, dir2, dir1] if d == "BAISSE"])
    nb_d = sum([1 for d in [dir3, dir2, dir1] if d == "NEUTRE"])
    fig = "Aucune figure"; d3 = "NEUTRE"; f3 = "Faible"
    try:
        b3_o = float(b3["Open"]); b3_c = float(b3["Close"]); b1_c = float(b1["Close"]); b2_c = float(b2["Close"])
        b2_o = float(b2["Open"]); b1_o = float(b1["Open"])
        if dir3 == "BAISSE" and ratio3 > 0.5 and dir2 == "NEUTRE" and dir1 == "HAUSSE" and ratio1 > 0.5 and b1_c > (b3_o + b3_c)/2:
            fig = "🌅 Étoile du Matin"; d3 = "HAUSSE"; f3 = "Forte"
        elif dir3 == "HAUSSE" and ratio3 > 0.5 and dir2 == "NEUTRE" and dir1 == "BAISSE" and ratio1 > 0.5 and b1_c < (b3_o + b3_c)/2:
            fig = "🌇 Étoile du Soir"; d3 = "BAISSE"; f3 = "Forte"
        elif nb_h == 3:
            fig = "🟢 3 Soldats Blancs" if b1_c > b2_c > b3_c else "🟢 3 Bougies Vertes"; d3 = "HAUSSE"; f3 = "Forte" if "Soldats" in fig else "Moyenne"
        elif nb_b == 3:
            fig = "🔴 3 Corbeaux Noirs" if b1_c < b2_c < b3_c else "🔴 3 Bougies Rouges"; d3 = "BAISSE"; f3 = "Forte" if "Corbeaux" in fig else "Moyenne"
        elif nb_h == 2 and nb_b == 1 and dir1 == "HAUSSE":
            fig = "🟢 2 Vertes / 1 Rouge"; d3 = "HAUSSE"; f3 = "Moyenne"
        elif nb_b == 2 and nb_h == 1 and dir1 == "BAISSE":
            fig = "🔴 2 Rouges / 1 Verte"; d3 = "BAISSE"; f3 = "Moyenne"
        elif nb_d >= 2:
            fig = "🟡 Beaucoup de Doji"; d3 = "NEUTRE"; f3 = "Faible"
        elif dir2 == "BAISSE" and dir1 == "HAUSSE" and b1_c >= b2_o and b1_o <= b2_c:
            fig = "🟢 Englobante Haussière"; d3 = "HAUSSE"; f3 = "Moyenne"
        elif dir2 == "HAUSSE" and dir1 == "BAISSE" and b1_c <= b2_o and b1_o >= b2_c:
            fig = "🔴 Englobante Baissière"; d3 = "BAISSE"; f3 = "Moyenne"
    except Exception:
        pass
    return {"liste": liste, "figure_3": fig, "direction_3": d3, "force_3": f3, "nb_hausse": nb_h, "nb_baisse": nb_b, "nb_doji": nb_d, "chandelier": fig, "direction": d3, "derniere_direction": dir1, "derniere_est_doji": (dir1 == "NEUTRE")}

def analyser_volume(df):
    if "Volume" not in df.columns:
        return {"statut": "SANS_VOLUME", "texte": "Volume indisponible"}
    try:
        c = df.iloc[-1]
        vol = float(c["Volume"]); vol_moyen = float(c["VOL_MOYEN"])
        if (not np.isfinite(vol) or not np.isfinite(vol_moyen) or vol <= 0 or vol_moyen <= 0):
            return {"statut": "SANS_VOLUME", "texte": "Volume non exploitable"}
        ratio = vol / vol_moyen
        if ratio > 1.5:
            return {"statut": "FORT", "texte": f"Volume fort : {ratio:.2f}x", "ratio": ratio}
        if ratio < 0.7:
            return {"statut": "FAIBLE", "texte": f"Volume faible : {ratio:.2f}x", "ratio": ratio}
        return {"statut": "NORMAL", "texte": f"Volume normal : {ratio:.2f}x", "ratio": ratio}
    except Exception:
        return {"statut": "SANS_VOLUME", "texte": "Erreur de lecture du volume"}

def calculer_mtf_vectorise(df2, df5, df15):
    n = len(df2)
    dir_2m = np.full(n, "NEUTRE", dtype=object)
    dir_5m = np.full(n, "NEUTRE", dtype=object)
    dir_15m = np.full(n, "NEUTRE", dtype=object)
    try:
        ema9 = df2["EMA9"].values; ema21 = df2["EMA21"].values; rsi = df2["RSI"].values
        dir_2m = np.where((ema9 > ema21) & (rsi > 50), "HAUSSE", np.where((ema9 < ema21) & (rsi < 50), "BAISSE", "NEUTRE"))
    except Exception:
        pass
    def _map_mtf_vrai(df_small, dir_array):
        if df_small is None or df_small.empty or len(df_small) < 20:
            return
        try:
            e9 = df_small["EMA9"].values; e21 = df_small["EMA21"].values; r = df_small["RSI"].values
            dir_small = np.where((e9 > e21) & (r > 50), "HAUSSE", np.where((e9 < e21) & (r < 50), "BAISSE", "NEUTRE"))
        except Exception:
            return
        idx2 = pd.DatetimeIndex([x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC") for x in df2.index])
        idx_small = pd.DatetimeIndex([x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC") for x in df_small.index])
        pos = idx_small.searchsorted(idx2, side="right") - 1
        mask = pos >= 0
        pos_clipped = np.clip(pos, 0, len(dir_small) - 1)
        dir_array[mask] = dir_small[pos_clipped[mask]]
    _map_mtf_vrai(df5, dir_5m)
    _map_mtf_vrai(df15, dir_15m)
    mtf_final = np.full(n, "NEUTRE", dtype=object)
    for i in range(n):
        vals = [dir_2m[i], dir_5m[i], dir_15m[i]]
        nb_h = vals.count("HAUSSE"); nb_b = vals.count("BAISSE")
        if nb_h > 0 and nb_b > 0:
            mtf_final[i] = "CONFLIT"
        elif nb_h == 3 or (nb_h == 2 and nb_b == 0):
            mtf_final[i] = "HAUSSE"
        elif nb_b == 3 or (nb_b == 2 and nb_h == 0):
            mtf_final[i] = "BAISSE"
        else:
            mtf_final[i] = "NEUTRE"
    return {"2m": dir_2m, "5m": dir_5m, "15m": dir_15m, "final": mtf_final}

def analyser_horaire():
    now = datetime.now(timezone.utc); heure = now.hour; jour = now.weekday()
    av = []
    if jour == 6:
        av.append("🔴 DIMANCHE : Marché fermé.")
    if jour == 5 and heure >= 20:
        av.append("🟡 SAMEDI SOIR GMT : Marché va fermer.")
    if 12 <= heure < 14:
        av.append("🟡 12h-14h GMT : Pause déjeuner.")
    if heure in [8, 14] or (heure == 13 and now.minute >= 30):
        av.append("⚠️ HEURE DE NEWS : 8h30 / 14h30 GMT.")
    if 0 <= heure < 6:
        av.append("🟡 00h-06h GMT : Session Asie seule.")
    if 7 <= heure < 10:
        av.append("✅ 07h-10h GMT : Ouverture Londres.")
    if 13 <= heure < 17:
        av.append("✅ 13h-17h GMT : Londres + New York.")
    if not av:
        av.append(f"✅ Heure OK : {now.strftime('%H:%M')} GMT")
    return {"heure_gmt": now.strftime("%H:%M GMT"), "jour": ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"][jour], "avertissements": av}

def _normaliser_index_utc(idx):
    try:
        if idx.tzinfo is None:
            return idx.tz_localize("UTC")
        return idx.tz_convert("UTC")
    except Exception:
        return idx

def _filtre_heure_realiste(idx_utc):
    h = idx_utc.hour; js = idx_utc.weekday()
    if js == 6:
        return False
    if js == 5 and h >= 20:
        return False
    if h < HEURE_DEBUT or h >= HEURE_FIN:
        return False
    if HEURE_PAUSE_DEBUT <= h < HEURE_PAUSE_FIN:
        return False
    return True

def _calcul_resultat(nb_g, nb_p, profit, details, nb_att, trades_jour, label):
    total = nb_g + nb_p
    taux = (nb_g / total * 100) if total > 0 else 0
    esp = (taux/100 * PAYOUT_IQ_OPTION - (1 - taux/100) * 1) * 100 if total > 0 else 0
    return {"nb_gagne": nb_g, "nb_perdu": nb_p, "nb_attendre": nb_att, "total_trades": total, "taux": taux, "details": details, "profit_total": profit, "esperance_100": esp, "trades_par_jour": trades_jour, "mode_label": label}

def faire_backtest_precis_1m_performant(ticker, is_scalping=False, expiration_min=3, use_ichimoku_bt=True):
    if expiration_min not in [1, 3, 5]:
        return None, f"Mode 1 Précis : Expiration {expiration_min} min interdite. Utilise 1, 3 ou 5 min uniquement. Pour 2, 4, 6 min, utilise le Mode 2 Approximatif."
    try:
        df2 = recuperer_donnees(ticker, interval="2m", period="5d")
        df1 = recuperer_donnees(ticker, interval="1m", period="5d")
        df5 = recuperer_donnees(ticker, interval="5m", period="5d")
        df15 = recuperer_donnees(ticker, interval="15m", period="5d")
        if df2.empty or len(df2) < 200:
            return None, "Mode 1 Précis : Pas assez de données 2m."
        if df1.empty or len(df1) < 500:
            return None, "Mode 1 Précis : Pas assez de données 1m. Utilise Mode 2."
        df2 = calculer_indicateurs(df2)
        df5 = calculer_indicateurs(df5) if not df5.empty else df5
        df15 = calculer_indicateurs(df15) if not df15.empty else df15
        df2 = df2.iloc[100:].copy()
        df2 = df2.dropna(subset=["RSI","WCCI","CFO","MACD_HIST","ATR","BB_MID","EMA50","tenkan","kijun"])
        if len(df2) < 50:
            return None, "Mode 1 : Pas assez de données après calcul."
        mtf_data = calculer_mtf_vectorise(df2, df5, df15)
        mtf_final = mtf_data["final"]
        score_h = df2["SCORE_H"].values; score_b = df2["SCORE_B"].values
        dir_arr = df2["DIR"].values
        atr = df2["ATR"].values; atr_moy = df2["ATR_MOYEN"].values; bb_w = df2["BB_WIDTH"].values
        bb_w_moy = df2["BB_WIDTH"].rolling(50).mean().values
        prix_close_2m = df2["Close"].values
        support = df2["SUPPORT"].values; resistance = df2["RESISTANCE"].values
        vol = df2["Volume"].values if "Volume" in df2.columns else np.full(len(df2), np.nan)
        vol_moy = df2["VOL_MOYEN"].values if "VOL_MOYEN" in df2.columns else np.full(len(df2), np.nan)
        ema5 = df2["EMA5"].values; ema9 = df2["EMA9"].values; rsi7 = df2["RSI7"].values
        senkou_a_v = df2["senkou_a"].values; senkou_b_v = df2["senkou_b"].values
        ichi_signal_v = df2["ichi_signal"].values
        ichi_pos_v = df2["ichi_position"].values
        idx1_utc = pd.DatetimeIndex([_normaliser_index_utc(x) for x in df1.index])
        close1 = df1["Close"].values
        doji_3 = pd.Series((dir_arr == 0).astype(int)).rolling(3).sum().values
        faux_arr = np.zeros(len(df2), dtype=bool)
        for i in range(6, len(df2)):
            for j in range(i-6, i):
                if j < 0 or j+1 >= len(df2):
                    continue
                res_j = resistance[j]; sup_j = support[j]; c_j = prix_close_2m[j]; c_next = prix_close_2m[j+1]
                if np.isfinite(res_j) and c_j > res_j and c_next < res_j:
                    faux_arr[i] = True
                    break
                if np.isfinite(sup_j) and c_j < sup_j and c_next > sup_j:
                    faux_arr[i] = True
                    break
        seuil = SEUIL_SCALPING if is_scalping else SEUIL_V2PRO
        nb_g = 0; nb_p = 0; nb_att = 0; details = []; trades_jour = {}; derniere_heure = None; profit = 0.0; mise = 1.0
        deja_vus = set()
        for i in range(60, len(df2) - 2):
            idx2 = df2.index[i]
            idx2_utc = _normaliser_index_utc(idx2)
            cle = idx2_utc.strftime("%Y-%m-%d %H:%M")
            if cle in deja_vus:
                continue
            deja_vus.add(cle)
            if not _filtre_heure_realiste(idx2_utc):
                nb_att += 1
                continue
            jour_str = idx2_utc.strftime("%Y-%m-%d"); heure_str = idx2_utc.strftime("%Y-%m-%d %H")
            if derniere_heure == heure_str:
                continue
            if trades_jour.get(jour_str, 0) >= MAX_TRADES_PAR_JOUR:
                continue
            mtf_dir = mtf_final[i]
            sh = int(score_h[i]); sb = int(score_b[i])
            if sh >= seuil and mtf_dir != "HAUSSE":
                nb_att += 1
                continue
            if sb >= seuil and mtf_dir != "BAISSE":
                nb_att += 1
                continue
            # ✅ FILTRE ICHIMOKU BACKTEST V7.3 CORRIGÉ - Erreur 1 + 2 corrigées
            if use_ichimoku_bt:
                try:
                    sa_ichi = senkou_a_v[i]; sb_ichi = senkou_b_v[i]
                    if np.isfinite(sa_ichi) and np.isfinite(sb_ichi):
                        # Prix DANS le nuage = ATTENDRE (seule règle dure)
                        if ichi_pos_v[i] == 0:
                            nb_att += 1
                            continue
                        # Bloque seulement si Ichimoku dit l'INVERSE, pas si neutre
                        ichi_sig = ichi_signal_v[i]
                        if sh >= seuil and ichi_sig == "PUT":
                            nb_att += 1
                            continue
                        if sb >= seuil and ichi_sig == "CALL":
                            nb_att += 1
                            continue
                    # Si NaN, on ne bloque pas
                except Exception:
                    pass
            if faux_arr[i] and BLOQUER_FAUX_CASSURE:
                nb_att += 1
                continue
            atr_i = atr[i]; atr_m = atr_moy[i]; bbw = bb_w[i]; bbw_m = bb_w_moy[i]
            if np.isfinite(bbw) and np.isfinite(bbw_m) and bbw < bbw_m * 0.7 and BLOQUER_SQUEEZE:
                nb_att += 1
                continue
            if np.isfinite(atr_i) and np.isfinite(atr_m) and atr_i > atr_m * 1.8 and BLOQUER_VOL_TROP_HAUTE:
                nb_att += 1
                continue
            prix_i = prix_close_2m[i]
            if not np.isfinite(atr_i) or atr_i <= 0 or (prix_i != 0 and atr_i / prix_i < SEUIL_VOLATILITE):
                nb_att += 1
                continue
            if doji_3[i] >= NB_DOJI_POUR_BLOQUER:
                nb_att += 1
                continue
            v = vol[i]; vm = vol_moy[i]
            if BLOQUER_VOLUME_FAIBLE and np.isfinite(v) and np.isfinite(vm) and vm > 0 and (v / vm) < 0.7:
                nb_att += 1
                continue
            signal = "ATTENDRE"
            sup_i = support[i]; res_i = resistance[i]
            proche_sup = np.isfinite(sup_i) and atr_i > 0 and abs(prix_i - sup_i) <= atr_i * 0.20
            proche_res = np.isfinite(res_i) and atr_i > 0 and abs(res_i - prix_i) <= atr_i * 0.20
            derniere_dir = dir_arr[i]
            if is_scalping:
                scalp_h = (ema5[i] > ema9[i] and rsi7[i] > 50)
                scalp_b = (ema5[i] < ema9[i] and rsi7[i] < 50)
                if sh >= seuil and scalp_h and not proche_res and derniere_dir == 1:
                    signal = "CALL / HAUSSE"
                elif sb >= seuil and scalp_b and not proche_sup and derniere_dir == -1:
                    signal = "PUT / BAISSE"
                else:
                    nb_att += 1
                    continue
            else:
                if sh >= seuil and not proche_res and derniere_dir == 1:
                    signal = "CALL / HAUSSE"
                elif sb >= seuil and not proche_sup and derniere_dir == -1:
                    signal = "PUT / BAISSE"
                else:
                    nb_att += 1
                    continue
            fermeture_2m = idx2_utc + timedelta(minutes=2)
            pos_entree = idx1_utc.searchsorted(fermeture_2m, side="right")
            if pos_entree >= len(df1):
                continue
            pos_sortie = pos_entree + expiration_min
            if pos_sortie >= len(df1):
                continue
            heure_entree = idx1_utc[pos_entree]; heure_sortie = idx1_utc[pos_sortie]
            ecart = (heure_sortie - heure_entree).total_seconds() / 60.0
            if abs(ecart - expiration_min) > 2:
                continue
            prix_entree = float(close1[pos_entree]); prix_sortie = float(close1[pos_sortie])
            if signal == "CALL / HAUSSE":
                gagne = prix_sortie > prix_entree
            elif signal == "PUT / BAISSE":
                gagne = prix_sortie < prix_entree
            else:
                continue
            if gagne:
                nb_g += 1
                profit += mise * PAYOUT_IQ_OPTION
            else:
                nb_p += 1
                profit -= mise
            derniere_heure = heure_str
            trades_jour[jour_str] = trades_jour.get(jour_str, 0) + 1
            if len(details) < 30:
                details.append({"Heure Signal 2m": idx2_utc.strftime("%d/%m %H:%M"), "Heure Entrée 1m": heure_entree.strftime("%H:%M"), "Heure Sortie 1m": heure_sortie.strftime("%H:%M"), "Expiration": f"{expiration_min} min", "Signal": signal, "Entrée": round(prix_entree,5), "Sortie": round(prix_sortie,5), "Résultat": "GAGNÉ" if gagne else "PERDU", "MTF": mtf_dir, "Score H": sh, "Score B": sb})
        return _calcul_resultat(nb_g, nb_p, profit, details, nb_att, trades_jour, f"MODE 1 PRÉCIS 1m + ICHIMOKU CORRIGÉ - Expiration {expiration_min} min"), None
    except Exception as e:
        return None, f"Erreur backtest Mode 1 : {e}"

def faire_backtest_approximatif_2m_performant(ticker, is_scalping=False, expiration_min=4, use_ichimoku_bt=True):
    if expiration_min not in [2, 4, 6]:
        return None, f"Mode 2 Approximatif : Expiration {expiration_min} min interdite. Utilise 2, 4 ou 6 min uniquement. Pour 1, 3, 5 min, utilise le Mode 1 Précis."
    try:
        df = recuperer_donnees(ticker, interval="2m", period="5d")
        df5 = recuperer_donnees(ticker, interval="5m", period="5d")
        df15 = recuperer_donnees(ticker, interval="15m", period="5d")
        if df.empty or len(df) < 200:
            return None, "Mode 2 : Pas assez de données 2m."
        df = calculer_indicateurs(df)
        df5 = calculer_indicateurs(df5) if not df5.empty else df5
        df15 = calculer_indicateurs(df15) if not df15.empty else df15
        df = df.iloc[100:].copy()
        df = df.dropna(subset=["RSI","WCCI","CFO","MACD_HIST","ATR","BB_MID","EMA50","tenkan","kijun"])
        if len(df) < 50:
            return None, "Mode 2 : Pas assez de données."
        mtf_data = calculer_mtf_vectorise(df, df5, df15)
        mtf_final = mtf_data["final"]
        score_h = df["SCORE_H"].values; score_b = df["SCORE_B"].values; dir_arr = df["DIR"].values
        atr = df["ATR"].values; atr_moy = df["ATR_MOYEN"].values; bb_w = df["BB_WIDTH"].values; bb_w_moy = df["BB_WIDTH"].rolling(50).mean().values
        prix_c = df["Close"].values; support = df["SUPPORT"].values; resistance = df["RESISTANCE"].values
        vol = df["Volume"].values if "Volume" in df.columns else np.full(len(df), np.nan)
        vol_moy = df["VOL_MOYEN"].values if "VOL_MOYEN" in df.columns else np.full(len(df), np.nan)
        ema5 = df["EMA5"].values; ema9 = df["EMA9"].values; rsi7 = df["RSI7"].values
        senkou_a_v = df["senkou_a"].values; senkou_b_v = df["senkou_b"].values
        ichi_signal_v = df["ichi_signal"].values; ichi_pos_v = df["ichi_position"].values
        doji_3 = pd.Series((dir_arr == 0).astype(int)).rolling(3).sum().values
        faux_arr = np.zeros(len(df), dtype=bool)
        for i in range(6, len(df)):
            for j in range(i-6, i):
                if j < 0 or j+1 >= len(df):
                    continue
                if np.isfinite(resistance[j]) and prix_c[j] > resistance[j] and prix_c[j+1] < resistance[j]:
                    faux_arr[i] = True
                    break
                if np.isfinite(support[j]) and prix_c[j] < support[j] and prix_c[j+1] > support[j]:
                    faux_arr[i] = True
                    break
        seuil = SEUIL_SCALPING if is_scalping else SEUIL_V2PRO
        pas_exp = max(1, int(round(expiration_min / 2)))
        nb_g = 0; nb_p = 0; nb_att = 0; details = []; trades_jour = {}; derniere_heure = None; profit = 0.0; mise = 1.0
        deja_vus = set()
        for i in range(60, len(df) - 2):
            if i + pas_exp >= len(df):
                break
            idx = df.index[i]; idx_utc = _normaliser_index_utc(idx)
            cle = idx_utc.strftime("%Y-%m-%d %H:%M")
            if cle in deja_vus:
                continue
            deja_vus.add(cle)
            if not _filtre_heure_realiste(idx_utc):
                nb_att += 1
                continue
            jour_str = idx_utc.strftime("%Y-%m-%d"); heure_str = idx_utc.strftime("%Y-%m-%d %H")
            if derniere_heure == heure_str:
                continue
            if trades_jour.get(jour_str, 0) >= MAX_TRADES_PAR_JOUR:
                continue
            mtf_dir = mtf_final[i]; sh = int(score_h[i]); sb = int(score_b[i])
            if sh >= seuil and mtf_dir != "HAUSSE":
                nb_att += 1
                continue
            if sb >= seuil and mtf_dir != "BAISSE":
                nb_att += 1
                continue
            if use_ichimoku_bt:
                try:
                    sa_ichi = senkou_a_v[i]; sb_ichi = senkou_b_v[i]
                    if np.isfinite(sa_ichi) and np.isfinite(sb_ichi):
                        if ichi_pos_v[i] == 0:
                            nb_att += 1
                            continue
                        ichi_sig = ichi_signal_v[i]
                        if sh >= seuil and ichi_sig == "PUT":
                            nb_att += 1
                            continue
                        if sb >= seuil and ichi_sig == "CALL":
                            nb_att += 1
                            continue
                except Exception:
                    pass
            if faux_arr[i] and BLOQUER_FAUX_CASSURE:
                nb_att += 1
                continue
            atr_i = atr[i]; atr_m = atr_moy[i]; bbw = bb_w[i]; bbw_m = bb_w_moy[i]
            if np.isfinite(bbw) and np.isfinite(bbw_m) and bbw < bbw_m * 0.7 and BLOQUER_SQUEEZE:
                nb_att += 1
                continue
            if np.isfinite(atr_i) and np.isfinite(atr_m) and atr_i > atr_m * 1.8 and BLOQUER_VOL_TROP_HAUTE:
                nb_att += 1
                continue
            prix_i = prix_c[i]
            if not np.isfinite(atr_i) or atr_i <= 0 or (prix_i != 0 and atr_i / prix_i < SEUIL_VOLATILITE):
                nb_att += 1
                continue
            if doji_3[i] >= NB_DOJI_POUR_BLOQUER:
                nb_att += 1
                continue
            v = vol[i]; vm = vol_moy[i]
            if BLOQUER_VOLUME_FAIBLE and np.isfinite(v) and np.isfinite(vm) and vm > 0 and (v / vm) < 0.7:
                nb_att += 1
                continue
            sup_i = support[i]; res_i = resistance[i]
            proche_sup = np.isfinite(sup_i) and atr_i > 0 and abs(prix_i - sup_i) <= atr_i * 0.20
            proche_res = np.isfinite(res_i) and atr_i > 0 and abs(res_i - prix_i) <= atr_i * 0.20
            derniere_dir = dir_arr[i]
            signal = "ATTENDRE"
            if is_scalping:
                scalp_h = (ema5[i] > ema9[i] and rsi7[i] > 50)
                scalp_b = (ema5[i] < ema9[i] and rsi7[i] < 50)
                if sh >= seuil and scalp_h and not proche_res and derniere_dir == 1:
                    signal = "CALL / HAUSSE"
                elif sb >= seuil and scalp_b and not proche_sup and derniere_dir == -1:
                    signal = "PUT / BAISSE"
                else:
                    nb_att += 1
                    continue
            else:
                if sh >= seuil and not proche_res and derniere_dir == 1:
                    signal = "CALL / HAUSSE"
                elif sb >= seuil and not proche_sup and derniere_dir == -1:
                    signal = "PUT / BAISSE"
                else:
                    nb_att += 1
                    continue
            prix_entree = float(prix_c[i]); prix_sortie = float(prix_c[i + pas_exp])
            if signal == "CALL / HAUSSE":
                gagne = prix_sortie > prix_entree
            elif signal == "PUT / BAISSE":
                gagne = prix_sortie < prix_entree
            else:
                continue
            if gagne:
                nb_g += 1
                profit += mise * PAYOUT_IQ_OPTION
            else:
                nb_p += 1
                profit -= mise
            derniere_heure = heure_str
            trades_jour[jour_str] = trades_jour.get(jour_str, 0) + 1
            if len(details) < 30:
                details.append({"Heure Signal 2m": idx_utc.strftime("%d/%m %H:%M"), "Expiration": f"{expiration_min} min (approx)", "Signal": signal, "Entrée": round(prix_entree,5), "Sortie": round(prix_sortie,5), "Résultat": "GAGNÉ" if gagne else "PERDU", "MTF": mtf_dir})
        return _calcul_resultat(nb_g, nb_p, profit, details, nb_att, trades_jour, f"MODE 2 APPROXIMATIF 2m + ICHIMOKU CORRIGÉ - Expiration {expiration_min} min"), None
    except Exception as e:
        return None, f"Erreur backtest Mode 2 : {e}"

def analyser_signal_live(df, ticker, is_scalping=False, use_mtf=True, use_faux=True, use_vol_intel=True, use_volume=True, use_ichimoku=True):
    c = df.iloc[-1]
    prix = float(c["Close"]); atr = float(c["ATR"]) if pd.notna(c["ATR"]) else 0.0
    support = float(c["SUPPORT"]) if pd.notna(c["SUPPORT"]) else np.nan
    resistance = float(c["RESISTANCE"]) if pd.notna(c["RESISTANCE"]) else np.nan
    proche_sup = (pd.notna(support) and atr > 0 and abs(prix - support) <= atr * 0.20)
    proche_res = (pd.notna(resistance) and atr > 0 and abs(resistance - prix) <= atr * 0.20)
    info_3 = analyser_trois_bougies_avance(df)
    sh = int(c["SCORE_H"]) if "SCORE_H" in c else 0
    sb = int(c["SCORE_B"]) if "SCORE_B" in c else 0
    derniere_dir_str = info_3.get("derniere_direction", "NEUTRE")
    derniere_doji = info_3.get("derniere_est_doji", True)
    ichi = calculer_position_ichimoku(c)
    try:
        df5 = recuperer_donnees(ticker, interval="5m", period="5d")
        df15 = recuperer_donnees(ticker, interval="15m", period="5d")
        df5 = calculer_indicateurs(df5) if not df5.empty else df5
        df15 = calculer_indicateurs(df15) if not df15.empty else df15
        mtf_data = calculer_mtf_vectorise(df, df5, df15)
        mtf_dir = mtf_data["final"][-1]
        mtf_details = {"2m": mtf_data["2m"][-1], "5m": mtf_data["5m"][-1], "15m": mtf_data["15m"][-1]}
    except Exception:
        mtf_dir = "NEUTRE"; mtf_details = {"2m": "NEUTRE", "5m": "NEUTRE", "15m": "NEUTRE"}
    mtf = {"direction": mtf_dir, "accord": f"MTF {mtf_dir} - Vrai 5m/15m", "details": mtf_details}
    vol = analyser_volume(df)
    try:
        bb_w = float(c["BB_WIDTH"]); bb_w_moy = float(df["BB_WIDTH"].rolling(50).mean().iloc[-1])
        atr_m = float(c["ATR_MOYEN"])
        if bb_w < bb_w_moy * 0.7:
            vol_intel = {"statut": "SQUEEZE", "texte": f"SQUEEZE : {bb_w:.4f} vs {bb_w_moy:.4f}"}
        elif atr > atr_m * 1.8:
            vol_intel = {"statut": "TROP_HAUTE", "texte": f"Vol TROP HAUTE : {atr:.5f} vs {atr_m:.5f}"}
        else:
            vol_intel = {"statut": "NORMALE", "texte": f"Vol NORMALE : {atr:.5f} vs {atr_m:.5f}"}
    except Exception:
        vol_intel = {"statut": "NEUTRE", "texte": "Volatilité : Erreur"}
    faux = {"faux": False, "texte": "✅ Pas de faux breakout."}
    try:
        for j in range(-6, -1):
            row = df.iloc[j]; res_j = float(row["RESISTANCE"]) if pd.notna(row["RESISTANCE"]) else np.nan; sup_j = float(row["SUPPORT"]) if pd.notna(row["SUPPORT"]) else np.nan; c_j = float(row["Close"]); c_next = float(df.iloc[j+1]["Close"])
            if pd.notna(res_j) and c_j > res_j and c_next < res_j:
                faux = {"faux": True, "texte": "⚠️ FAUX BREAKOUT HAUSSIER"}
                break
            if pd.notna(sup_j) and c_j < sup_j and c_next > sup_j:
                faux = {"faux": True, "texte": "⚠️ FAUX BREAKOUT BAISSIER"}
                break
    except Exception:
        pass
    base = {"score_haut": sh, "score_bas": sb, "chandelier": info_3["chandelier"], "direction": info_3["direction"], "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_sup, "proche_resistance": proche_res, "mtf": mtf, "faux": faux, "vol_intel": vol_intel, "vol": vol, "derniere_direction": derniere_dir_str, "derniere_est_doji": derniere_doji, "ichimoku": ichi}
    seuil = SEUIL_SCALPING if is_scalping else SEUIL_V2PRO
    if use_mtf:
        if sh >= seuil and mtf_dir != "HAUSSE":
            return {"signal": "ATTENDRE", "raison": f"MTF non haussier : {mtf_dir}", **base}
        if sb >= seuil and mtf_dir != "BAISSE":
            return {"signal": "ATTENDRE", "raison": f"MTF non baissier : {mtf_dir}", **base}
    if use_ichimoku:
        if ichi["position"] == "PAS ASSEZ DE DONNÉES":
            pass
        elif ichi["position"].startswith("DANS"):
            return {"signal": "ATTENDRE", "raison": f"ICHIMOKU : {ichi['texte']}", **base}
        elif sh >= seuil and ichi["signal"] == "PUT":
            return {"signal": "ATTENDRE", "raison": f"ICHIMOKU contraire : V2 PRO dit CALL mais Ichimoku dit PUT - {ichi['texte']}", **base}
        elif sb >= seuil and ichi["signal"] == "CALL":
            return {"signal": "ATTENDRE", "raison": f"ICHIMOKU contraire : V2 PRO dit PUT mais Ichimoku dit CALL - {ichi['texte']}", **base}
    if faux["faux"] and BLOQUER_FAUX_CASSURE:
        return {"signal": "ATTENDRE", "raison": f"FAUX CASSURE : {faux['texte']}", **base}
    if vol_intel["statut"] == "SQUEEZE" and BLOQUER_SQUEEZE:
        return {"signal": "ATTENDRE", "raison": f"SQUEEZE : {vol_intel['texte']}", **base}
    if vol_intel["statut"] == "TROP_HAUTE" and BLOQUER_VOL_TROP_HAUTE:
        return {"signal": "ATTENDRE", "raison": f"VOL TROP HAUTE : {vol_intel['texte']}", **base}
    if vol.get("statut") == "FAIBLE" and BLOQUER_VOLUME_FAIBLE:
        return {"signal": "ATTENDRE", "raison": f"VOLUME : {vol['texte']}", **base}
    if info_3["nb_doji"] >= NB_DOJI_POUR_BLOQUER:
        return {"signal": "ATTENDRE", "raison": f"Filtre : {info_3['nb_doji']} Doji", **base}
    if is_scalping:
        scalp_h = (float(c["EMA5"]) > float(c["EMA9"]) and float(c["RSI7"]) > 50)
        scalp_b = (float(c["EMA5"]) < float(c["EMA9"]) and float(c["RSI7"]) < 50)
        if sh >= seuil and scalp_h and not proche_res and derniere_dir_str == "HAUSSE" and not derniere_doji:
            return {"signal": "CALL / HAUSSE", "raison": f"SCALPING : {sh}/6 + MTF {mtf_dir} + Ichimoku {ichi['signal']} + Dernière HAUSSE + {info_3['chandelier']}", **{**base, "direction": "HAUSSE"}}
        if sb >= seuil and scalp_b and not proche_sup and derniere_dir_str == "BAISSE" and not derniere_doji:
            return {"signal": "PUT / BAISSE", "raison": f"SCALPING : {sb}/6 + MTF {mtf_dir} + Ichimoku {ichi['signal']} + Dernière BAISSE + {info_3['chandelier']}", **{**base, "direction": "BAISSE"}}
        return {"signal": "ATTENDRE", "raison": f"SCALPING : Pas {seuil}/6 + Confirmation.", **base}
    if sh >= seuil and not proche_res and derniere_dir_str == "HAUSSE" and not derniere_doji:
        return {"signal": "CALL / HAUSSE", "raison": f"V2 PRO : {sh}/6 HAUSSE + MTF {mtf_dir} + Ichimoku {ichi['signal']} + Dernière HAUSSE + {info_3['chandelier']}", **{**base, "direction": "HAUSSE"}}
    if sb >= seuil and not proche_sup and derniere_dir_str == "BAISSE" and not derniere_doji:
        return {"signal": "PUT / BAISSE", "raison": f"V2 PRO : {sb}/6 BAISSE + MTF {mtf_dir} + Ichimoku {ichi['signal']} + Dernière BAISSE + {info_3['chandelier']}", **{**base, "direction": "BAISSE"}}
    return {"signal": "ATTENDRE", "raison": f"Filtre : Pas {seuil}/6 - H {sh}, B {sb}", **base}

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

st.divider()
st.header("🧪 BACKTEST V7.3 - ICHIMOKU CORRIGÉ - 2 MODES SÉPARÉS")
mode_backtest = st.radio("Choisis ton mode :", ["✅ Mode 1 — PRÉCIS à la minute (Recommandé)", "⚠️ Mode 2 — APPROXIMATIF (2m seulement)"], index=0)
if mode_backtest.startswith("✅"):
    st.success("**Mode 1 PRÉCIS :** Signaux 2m + Entrée/Sortie 1m + Ichimoku corrigé. Expirations : 1, 3, 5 min.")
    expiration_precis = st.selectbox("Expiration Mode 1 Précis :", [1, 3, 5], index=1)
else:
    st.error("**Mode 2 APPROXIMATIF :** Uniquement 2m. Résultat approximatif. Ne pas utiliser pour décider du réel.")
    expiration_approx = st.selectbox("Expiration Mode 2 Approximatif :", [2, 4, 6], index=1)

if st.button("🧪 LANCER LE BACKTEST V7.3 CORRIGÉ", type="secondary"):
    is_scalp_bt = mode.startswith("⚡")
    ticker_bt = PAIRES[paire]
    if paire == "Dollar Index (DXY)":
        df_test = recuperer_donnees(ticker_bt, interval="2m", period="1d")
        if df_test.empty:
            ticker_bt = "^DXY"
    start_time = datetime.now()
    if mode_backtest.startswith("✅"):
        with st.spinner(f"Backtest Mode 1 Précis + Ichimoku corrigé..."):
            resultat_bt, erreur_bt = faire_backtest_precis_1m_performant(ticker_bt, is_scalping=is_scalp_bt, expiration_min=expiration_precis, use_ichimoku_bt=use_ichimoku)
    else:
        with st.spinner(f"Backtest Mode 2 Approximatif + Ichimoku corrigé..."):
            resultat_bt, erreur_bt = faire_backtest_approximatif_2m_performant(ticker_bt, is_scalping=is_scalp_bt, expiration_min=expiration_approx, use_ichimoku_bt=use_ichimoku)
    duree = (datetime.now() - start_time).total_seconds()
    if erreur_bt:
        st.error(erreur_bt)
    else:
        st.caption(f"⏱️ Durée : {duree:.1f} secondes")
        if "PRÉCIS" in resultat_bt["mode_label"]:
            st.success(f"✅ {resultat_bt['mode_label']} - RÉSULTAT PRÉCIS À LA MINUTE")
        else:
            st.error(f"⚠️ {resultat_bt['mode_label']} - ⚠️ RÉSULTAT APPROXIMATIF - NE PAS MÉLANGER")
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        with col_b1:
            st.metric("Trades", resultat_bt["total_trades"])
        with col_b2:
            st.metric("✅ GAGNÉ", resultat_bt["nb_gagne"])
        with col_b3:
            st.metric("❌ PERDU", resultat_bt["nb_perdu"])
        with col_b4:
            st.metric("🏆 Taux", f"{resultat_bt['taux']:.1f}%")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.metric("💰 Profit si 1$ / trade", f"{resultat_bt['profit_total']:.2f}$ sur {resultat_bt['total_trades']} trades")
        with col_p2:
            st.metric("📈 Espérance / 100 trades (1$)", f"{resultat_bt['esperance_100']:.2f}$")
        if "PRÉCIS" in resultat_bt["mode_label"]:
            if resultat_bt["taux"] >= 60:
                st.success(f"✅ Mode 1 Précis + Ichimoku Excellent : {resultat_bt['taux']:.1f}% - Tu peux tester en démo lundi.")
            elif resultat_bt["taux"] >= 55:
                st.warning(f"🟡 Mode 1 Précis + Ichimoku Rentable mais juste : {resultat_bt['taux']:.1f}% - Teste en démo d'abord.")
            elif resultat_bt["taux"] >= 50:
                st.error(f"🔴 Mode 1 Précis + Ichimoku Non rentable : {resultat_bt['taux']:.1f}% - Tu perds {resultat_bt['profit_total']:.2f}$. NE PASSE PAS EN RÉEL.")
            else:
                st.error(f"🔴 Mode 1 Précis + Ichimoku Très faible : {resultat_bt['taux']:.1f}% - Change de paire.")
        else:
            st.warning(f"⚠️ Ce taux {resultat_bt['taux']:.1f}% est APPROXIMATIF. Relance en Mode 1 Précis pour décider.")
        st.write(f"ATTENDRE : {resultat_bt['nb_attendre']} fois.")
        if len(resultat_bt["trades_par_jour"]) > 0:
            st.write("**Trades par jour :**", resultat_bt["trades_par_jour"])
        if len(resultat_bt["details"]) > 0:
            st.dataframe(pd.DataFrame(resultat_bt["details"]), use_container_width=True, hide_index=True)

if st.button("🔍 ANALYSER MAINTENANT - V7.3", type="primary"):
    is_scalp = mode.startswith("⚡")
    with st.spinner("Analyse V7.3 + Ichimoku corrigé..."):
        ticker = PAIRES[paire]
        df = recuperer_donnees_avec_secours(ticker, interval="2m", period="1d", paire_nom=paire)
        if df.empty or len(df) < 100:
            st.error("Données insuffisantes. Il faut 100+ bougies pour Ichimoku (52 + 26).")
        else:
            df = calculer_indicateurs(df)
            df = garder_que_les_bougies_fermees(df, interval="2m")
            df = df.dropna(subset=["RSI", "WCCI", "CFO", "MACD_HIST", "ATR", "BB_MID", "EMA50", "tenkan", "kijun"])
            if len(df) < 4:
                st.error("Pas assez de données.")
            else:
                analyse = analyser_signal_live(df, ticker, is_scalping=is_scalp, use_mtf=use_mtf, use_faux=use_faux, use_vol_intel=use_vol_intel, use_volume=use_volume, use_ichimoku=use_ichimoku)
                c = df.iloc[-1]
                nouvel_id = str(uuid.uuid4())[:8]
                st.session_state.historique.append({"ID": nouvel_id, "Heure": datetime.now().strftime("%H:%M:%S"), "Paire": paire, "Mode": "SCALPING" if is_scalp else "V2 PRO", "Signal": analyse["signal"], "Prix": round(float(c["Close"]),5), "Score H": analyse["score_haut"], "Score B": analyse["score_bas"], "MTF": analyse["mtf"]["direction"], "Dernière Bougie": analyse.get("derniere_direction","?"), "Volume": analyse["vol"].get("statut","-"), "Résultat": "En attente"})
                sauvegarder_historique()
                st.divider()
                st.subheader(f"🎯 SIGNAL V7.3 - Graphique 2m + Ichimoku CORRIGÉ")
                st.metric("Prix", f"{float(c['Close']):.5f}")
                st.metric("RSI 14 / RSI 7", f"{float(c['RSI']):.1f} / {float(c['RSI7']):.1f}")
                st.metric("EMA 5 / 9 / 21", f"{float(c['EMA5']):.5f} / {float(c['EMA9']):.5f} / {float(c['EMA21']):.5f}")
                st.metric("WCCI / CFO", f"{float(c['WCCI']):.1f} / {float(c['CFO']):.4f}")
                st.metric("Dernière bougie fermée (2m)", f"{analyse.get('derniere_direction','?')} - Doji ? {analyse.get('derniere_est_doji','?')}")
                if analyse["signal"] == "CALL / HAUSSE":
                    st.success(f"🟢 CALL - {expiration} mn - V7.3 VALIDÉ")
                    st.warning("⚠️ Vérifie sur IQ Option. Attends 5s après fermeture.")
                elif analyse["signal"] == "PUT / BAISSE":
                    st.error(f"🔴 PUT - {expiration} mn - V7.3 VALIDÉ")
                    st.warning("⚠️ Vérifie sur IQ Option. Attends 5s après fermeture.")
                else:
                    st.warning("⏳ ATTENDRE - V7.3 a bloqué")
                st.write("**Motif :**", analyse["raison"])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Score HAUSSE", f"{analyse['score_haut']}/6")
                with col2:
                    st.metric("Score BAISSE", f"{analyse['score_bas']}/6")
                st.divider()
                st.subheader("☁️ Ichimoku - CORRIGÉ")
                ichi = analyse["ichimoku"]
                st.info(ichi["texte"])
                if "nuage_haut" in ichi and pd.notna(ichi["nuage_haut"]):
                    col_ichi1, col_ichi2, col_ichi3, col_ichi4 = st.columns(4)
                    with col_ichi1:
                        st.metric("Tenkan (9)", f"{ichi['tenkan']:.5f}")
                    with col_ichi2:
                        st.metric("Kijun (26)", f"{ichi['kijun']:.5f}")
                    with col_ichi3:
                        st.metric("Senkou A", f"{ichi['senkou_a']:.5f}")
                    with col_ichi4:
                        st.metric("Senkou B", f"{ichi['senkou_b']:.5f}")
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        st.metric("Nuage Haut", f"{ichi['nuage_haut']:.5f}")
                    with col_n2:
                        st.metric("Nuage Bas", f"{ichi['nuage_bas']:.5f}")
                    st.metric("Position Prix vs Nuage", ichi["position"])
                    st.metric("Signal Ichimoku", ichi["signal"])
                    st.metric("Chikou Haussier ?", f"{bool(c['chikou_haussier'])} | Chikou Baissier ? {bool(c['chikou_baissier'])}")
                st.divider()
                st.subheader("1️⃣ MTF STRICT VRAI - 2m, 5m, 15m")
                st.info(analyse["mtf"]["accord"])
                st.dataframe(pd.DataFrame([analyse["mtf"]["details"]]), use_container_width=True)
                st.subheader("2️⃣ Faux Cassure")
                if analyse["faux"]["faux"]:
                    st.error(analyse["faux"]["texte"])
                else:
                    st.success(analyse["faux"]["texte"])
                st.subheader("4️⃣ Volatilité")
                if analyse["vol_intel"]["statut"] in ["SQUEEZE","TROP_HAUTE","TROP_BASSE"]:
                    st.warning(analyse["vol_intel"]["texte"])
                else:
                    st.success(analyse["vol_intel"]["texte"])
                st.subheader("6️⃣ Volume")
                if analyse["vol"].get("statut") == "FORT":
                    st.success(analyse["vol"]["texte"])
                elif analyse["vol"].get("statut") == "FAIBLE":
                    st.warning(analyse["vol"]["texte"])
                elif analyse["vol"].get("statut") == "SANS_VOLUME":
                    st.warning(analyse["vol"]["texte"])
                else:
                    st.info(analyse["vol"]["texte"])
                st.divider()
                st.subheader("🕯️ 3. Chandeliers - 3 Bougies 2m")
                if len(analyse["info_3"]["liste"]) > 0:
                    st.info(f"**Figure :** {analyse['info_3']['figure_3']} | **Force :** {analyse['info_3']['force_3']} | **Vertes :** {analyse['info_3']['nb_hausse']} | **Rouges :** {analyse['info_3']['nb_baisse']} | **Doji :** {analyse['info_3']['nb_doji']} | **Dernière :** {analyse.get('derniere_direction')}")
                    st.dataframe(pd.DataFrame(analyse["info_3"]["liste"]), use_container_width=True, hide_index=True)
                st.divider()
                st.subheader("📍 Support / Résistance")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Support", f"{float(analyse['support']):.5f}" if pd.notna(analyse["support"]) else "Indisponible")
                with col2:
                    st.metric("Résistance", f"{float(analyse['resistance']):.5f}" if pd.notna(analyse["resistance"]) else "Indisponible")
                st.subheader("📈 Graphique 2m + Ichimoku")
                st.line_chart(df[["Close","BB_UPPER","BB_MID","BB_LOWER","EMA5","EMA9","EMA21","tenkan","kijun","senkou_a","senkou_b"]].tail(100))

st.divider()
st.header("📊 7. Historique - SAUVEGARDÉ")
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
        st.write(f"**Vrai taux :** {nb_gagne} GAGNÉ / {nb_gagne + nb_perdu} = **{taux:.1f}%**")
    for idx, row in df_hist.iterrows():
        col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 2])
        with col_a:
            st.write(f"**{row['Heure']} - {row['Paire']} - {row['Signal']}** - Prix {row['Prix']} - MTF {row.get('MTF','?')}")
        with col_b:
            st.write(f"Score H {row['Score H']} / B {row['Score B']} - Mode {row['Mode']}")
        with col_c:
            st.write(f"Résultat : **{row['Résultat']}**")
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
                st.write("— ATTENDRE")
    try:
        csv_data = pd.DataFrame(st.session_state.historique).to_csv(index=False).encode("utf-8")
        st.download_button("📥 Télécharger historique (CSV)", data=csv_data, file_name="historique_v7.csv", mime="text/csv")
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
st.header(f"📸 Capture V7.3 - {paire} - {expiration} mn")
if CLE_ACTIVE:
    mode_capture = st.radio("Mode capture :", ["🤖 AUTO IA V7.3", "✍️ MANUEL"], index=0, horizontal=True)
else:
    mode_capture = st.radio("Mode capture :", ["✍️ MANUEL", "🤖 AUTO IA V7.3"], index=0, horizontal=True)
uploaded = st.file_uploader("Envoie ta capture", type=["png","jpg","jpeg","webp"], key="capture_v7_3")
if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)
    if mode_capture.startswith("🤖"):
        if not CLE_ACTIVE:
            st.error("❌ Mets ta clé dans Secrets ou utilise MANUEL.")
        else:
            if st.button("🧠 ANALYSER MA CAPTURE V7.3", type="primary", use_container_width=True):
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"
                    prompt = f"Tu es analyste PRO V7.3 IQ Option. Actif : {paire}. Expiration : {expiration} mn. Graphique 2m. Règles STRICTES : MTF doit être HAUSSE pour CALL, BAISSE pour PUT, NEUTRE = ATTENDRE, Ichimoku : Prix DANS le nuage = ATTENDRE, Prix DESSUS + 2/3 (Tenkan>Kijun, Chikou haussier, Nuage haussier) = CALL, Prix DESSOUS + 2/3 = PUT, Faux cassure, Confirmation dernière bougie, Minimum 5/6 V2 PRO, 4/6 Scalping, Heures 07h-17h GMT, pas 12h-14h. Donne tableau 3 bougies, MTF, Ichimoku, Faux cassure, Score /6, CONCLUSION CALL/PUT/ATTENDRE. Ne garantis jamais un gain."
                    with st.spinner("🧠 L'IA analyse..."):
                        resp = client_auto.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}]}], max_tokens=1200)
                        st.markdown(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"Erreur IA : {e}")
    else:
        c1, c2, c3 = st.columns(3)
        b3_m = c1.selectbox("Bougie -3 (2m)", ["Verte","Rouge","Doji"], key="b3_v7_3")
        b2_m = c2.selectbox("Bougie -2 (2m)", ["Verte","Rouge","Doji"], key="b2_v7_3")
        b1_m = c3.selectbox("Bougie -1 (2m) - Dernière fermée", ["Verte","Rouge","Doji"], key="b1_v7_3")
        mtf_m = st.selectbox("5m et 15m ?", ["HAUSSE comme 2m","BAISSE comme 2m","Contraire à 2m (CONFLIT)","Je ne sais pas"], key="mtf_v7_3")
        ichi_m = st.selectbox("Prix par rapport au nuage Ichimoku ?", ["DESSUS du nuage (Vert)","DESSOUS du nuage (Rouge)","DANS le nuage","Je ne sais pas"], key="ichi_v7_3")
        if st.button("🔎 ANALYSER V7.3 - SANS CLÉ", type="primary", use_container_width=True):
            nb_v = [b3_m, b2_m, b1_m].count("Verte")
            nb_r = [b3_m, b2_m, b1_m].count("Rouge")
            if mtf_m == "Contraire à 2m (CONFLIT)":
                st.warning("⏳ ATTENDRE - MTF CONFLIT.")
            elif ichi_m == "DANS le nuage":
                st.warning("⏳ ATTENDRE - Prix DANS le nuage Ichimoku - Ne jamais trader dans le nuage.")
            elif b1_m == "Doji":
                st.warning("⏳ ATTENDRE - Dernière bougie Doji.")
            elif nb_v == 3 and b1_m == "Verte" and ichi_m == "DESSUS du nuage (Vert)":
                st.success(f"🟢 CALL {paire} - 3 Soldats Blancs + Dernière verte + Prix DESSUS nuage")
            elif nb_r == 3 and b1_m == "Rouge" and ichi_m == "DESSOUS du nuage (Rouge)":
                st.error(f"🔴 PUT {paire} - 3 Corbeaux Noirs + Dernière rouge + Prix DESSOUS nuage")
            elif nb_v == 2 and b1_m == "Verte" and ichi_m == "DESSUS du nuage (Vert)":
                st.success(f"🟢 CALL {paire} - 2 Vertes + Dernière verte + Prix DESSUS nuage")
            elif nb_r == 2 and b1_m == "Rouge" and ichi_m == "DESSOUS du nuage (Rouge)":
                st.error(f"🔴 PUT {paire} - 2 Rouges + Dernière rouge + Prix DESSOUS nuage")
            else:
                st.warning(f"🟡 ATTENDRE {paire} - Dernière bougie / Ichimoku ne confirme pas.")

st.caption("V7.3 CORRIGÉ - Ichimoku 2/3 + NaN gérés + sb_ichi | Lundi = DÉMO uniquement.")
