import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
import base64

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

# ================= ⚙️ RÉGLAGES DU FILTRE ANTI-SIGNAL - DOUX =================
# C'EST ICI QUE TU BAISSES LES CRITIQUES. Change les chiffres si tu veux encore plus doux ou plus strict.
# Plus le chiffre est BAS, plus tu as de signaux, mais plus de risque.
SEUIL_V2PRO = 4          # Avant : 6. Maintenant : 4/6 suffit pour CALL/PUT. Mets 5 si tu veux un peu plus strict, 3 si tu veux encore plus de signaux.
SEUIL_SCALPING = 3       # Avant : 4. Maintenant : 3/6 suffit pour Scalping.
SEUIL_VOLATILITE = 0.00001  # Avant : 0.00002. Maintenant : on bloque seulement si vraiment aucune volatilité. Mets 0.000005 si tu veux encore plus doux.
DISTANCE_SUPPORT = 0.10     # Avant : 0.30. Maintenant : on bloque seulement si prix collé à 0.10 x ATR du Support/Résistance. Mets 0.05 si tu veux presque jamais bloquer.
SEUIL_CORPS_BOUGIE = 0.08   # Avant : 0.15. Maintenant : on accepte les bougies avec corps > 8%. Mets 0.05 si tu veux accepter même les très petites.
NB_DOJI_POUR_BLOQUER = 3    # Avant : 2. Maintenant : il faut 3 Doji sur 3 pour bloquer. Mets 2 si tu veux re-bloquer plus vite.

st.set_page_config(page_title="IQ OPTION V2 PRO + SCALPING + FILTRE DOUX", page_icon="📈", layout="wide")
st.title("📈 IQ OPTION BINAIRE - V2 PRO + ⚡ SCALPING + 🕯️ 3 BOUGIES + FILTRE DOUX")
st.caption(f"Filtre anti-signal BAISSÉ : V2 PRO {SEUIL_V2PRO}/6 | Scalping {SEUIL_SCALPING}/6 | Plus de signaux")

if CLE_ACTIVE:
    st.success("✅ Clé OpenAI AUTOMATIQUE active")
else:
    st.info("ℹ️ Pas de clé automatique. Capture en MANUEL.")

st.info(f"⚙️ Filtre DOUX activé : V2 PRO = {SEUIL_V2PRO}/6 | Scalping = {SEUIL_SCALPING}/6 | Volatilité min = {SEUIL_VOLATILITE} | Distance Support = {DISTANCE_SUPPORT} x ATR | Corps bougie min = {SEUIL_CORPS_BOUGIE*100:.0f}% | Doji pour bloquer = {NB_DOJI_POUR_BLOQUER}/3. Tu peux changer ces chiffres en haut du code.")

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

st.subheader("🎯 Choisis ton mode")
mode = st.radio("Mode :", [f"📊 V2 PRO - Normal (1 à 19 mn, {SEUIL_V2PRO}/6)", f"⚡ SCALPING - Rapide (1 à 5 mn, {SEUIL_SCALPING}/6)"], index=0)

col1, col2 = st.columns(2)
with col1:
    paire = st.selectbox("Choisir un actif", list(PAIRES.keys()))
with col2:
    if mode.startswith("⚡"):
        expiration = st.slider("Expiration SCALPING (minutes)", 1, 5, 2)
    else:
        expiration = st.slider("Expiration V2 PRO (minutes)", 1, 19, 5)

st.info(f"Actif : {paire} | Mode : {mode} | Expiration : {expiration} minutes")

@st.cache_data(ttl=30)
def recuperer_donnees(ticker):
    df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    colonnes = ["Open", "High", "Low", "Close"]
    if not all(c in df.columns for c in colonnes):
        return pd.DataFrame()
    df = df[colonnes].copy()
    df = df.dropna()
    return df

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
    df["SUPPORT"] = low.rolling(30).min().shift(1)
    df["RESISTANCE"] = high.rolling(30).max().shift(1)
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
        if ratio > 0.60:
            return "Verte Forte", "HAUSSE", ratio
        return "Verte", "HAUSSE", ratio
    else:
        if ratio > 0.60:
            return "Rouge Forte", "BAISSE", ratio
        return "Rouge", "BAISSE", ratio

def analyser_trois_bougies(df):
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
        if b1["Close"] > b2["Close"] > b3["Close"]:
            figure_3 = "🟢 3 Soldats Blancs"; direction_3 = "HAUSSE"; force_3 = "Forte"
        else:
            figure_3 = "🟢 3 Bougies Vertes"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
    elif nb_baisse == 3:
        if b1["Close"] < b2["Close"] < b3["Close"]:
            figure_3 = "🔴 3 Corbeaux Noirs"; direction_3 = "BAISSE"; force_3 = "Forte"
        else:
            figure_3 = "🔴 3 Bougies Rouges"; direction_3 = "BAISSE"; force_3 = "Moyenne"
    elif nb_hausse == 2 and nb_baisse == 1:
        if dir1 == "HAUSSE":
            figure_3 = "🟢 2 Vertes / 1 Rouge - Dernière verte"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
        else:
            figure_3 = "🟡 2 Vertes / 1 Rouge - Dernière rouge"; direction_3 = "NEUTRE"; force_3 = "Faible"
    elif nb_baisse == 2 and nb_hausse == 1:
        if dir1 == "BAISSE":
            figure_3 = "🔴 2 Rouges / 1 Verte - Dernière rouge"; direction_3 = "BAISSE"; force_3 = "Moyenne"
        else:
            figure_3 = "🟡 2 Rouges / 1 Verte - Dernière verte"; direction_3 = "NEUTRE"; force_3 = "Faible"
    elif nb_doji >= 2:
        figure_3 = "🟡 Beaucoup de Doji"; direction_3 = "NEUTRE"; force_3 = "Faible"
    elif nb_doji == 1:
        figure_3 = "🟡 1 Doji sur 3"
        if nb_hausse == 2:
            direction_3 = "HAUSSE"; force_3 = "Faible"
        elif nb_baisse == 2:
            direction_3 = "BAISSE"; force_3 = "Faible"
    return {"liste": liste, "figure_3": figure_3, "direction_3": direction_3, "force_3": force_3, "nb_hausse": nb_hausse, "nb_baisse": nb_baisse, "nb_doji": nb_doji, "chandelier": figure_3, "direction": direction_3}

# ================= 🛡️ FILTRE DOUX - BAISSÉ =================
def analyser_signal(df, is_scalping=False):
    c = df.iloc[-1]
    prix = c["Close"]; atr = c["ATR"]
    tendance_haussiere = (c["EMA9"] > c["EMA21"] > c["EMA50"])
    tendance_baissiere = (c["EMA9"] < c["EMA21"] < c["EMA50"])
    indicateurs_haut = [tendance_haussiere, 50 < c["RSI"] < 70, c["WCCI"] > 0, c["CFO"] > 0, c["MACD_HIST"] > 0, prix > c["BB_MID"]]
    indicateurs_bas = [tendance_baissiere, 30 < c["RSI"] < 50, c["WCCI"] < 0, c["CFO"] < 0, c["MACD_HIST"] < 0, prix < c["BB_MID"]]
    info_3 = analyser_trois_bougies(df)
    chandelier = info_3["chandelier"]; direction = info_3["direction"]
    score_haut = sum(indicateurs_haut); score_bas = sum(indicateurs_bas)
    support = c["SUPPORT"]; resistance = c["RESISTANCE"]

    # --- Filtre DOUX : on utilise les réglages du haut ---
    proche_support = (pd.notna(support) and atr > 0 and prix - support <= atr * DISTANCE_SUPPORT)
    proche_resistance = (pd.notna(resistance) and atr > 0 and resistance - prix <= atr * DISTANCE_SUPPORT)
    volatilite_faible = (pd.isna(atr) or atr <= 0 or atr / prix < SEUIL_VOLATILITE)
    # Bougie faible DOUCE : on regarde la dernière bougie, mais seuil baissé à 8%
    derniere = df.iloc[-1]
    amp_der = derniere["High"] - derniere["Low"]
    corps_der = abs(derniere["Close"] - derniere["Open"])
    bougie_faible = (amp_der <= 0 or corps_der / amp_der < SEUIL_CORPS_BOUGIE)
    trop_de_doji = (info_3["nb_doji"] >= NB_DOJI_POUR_BLOQUER)

    seuil = SEUIL_SCALPING if is_scalping else SEUIL_V2PRO

    # 1. Volatilité vraiment trop faible -> on bloque encore, mais c'est rare maintenant
    if volatilite_faible:
        return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Volatilité vraiment trop faible (< {SEUIL_VOLATILITE})", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    # 2. Trop de Doji -> on bloque, mais il faut 3 Doji maintenant
    if trop_de_doji:
        return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : {info_3['nb_doji']} Doji sur 3 - Marché vraiment indécis", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    # 3. Bougie vraiment trop petite -> on bloque, mais seuil baissé
    if bougie_faible and direction == "NEUTRE":
        return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Dernière bougie trop petite (< {SEUIL_CORPS_BOUGIE*100:.0f}% de corps) + direction neutre", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}

    if is_scalping:
        scalp_haut_rapide = (c["EMA5"] > c["EMA9"] and c["RSI7"] > 50)
        scalp_bas_rapide = (c["EMA5"] < c["EMA9"] and c["RSI7"] < 50)
        if score_haut >= seuil and scalp_haut_rapide and not proche_resistance:
            return {"signal": "CALL / HAUSSE", "raison": f"SCALPING FILTRE DOUX : {score_haut}/6 + EMA5 > EMA9 + RSI7 > 50 - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        if score_bas >= seuil and scalp_bas_rapide and not proche_support:
            return {"signal": "PUT / BAISSE", "raison": f"SCALPING FILTRE DOUX : {score_bas}/6 + EMA5 < EMA9 + RSI7 < 50 - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        # Si Support/Résistance bloque, on l'explique, mais comme la distance est petite, ça arrive rarement
        if score_haut >= seuil and proche_resistance:
            return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Score HAUSSE {score_haut} bon, mais vraiment collé à la Résistance", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        if score_bas >= seuil and proche_support:
            return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Score BAISSE {score_bas} bon, mais vraiment collé au Support", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        return {"signal": "ATTENDRE", "raison": f"SCALPING FILTRE DOUX : Pas {seuil}/6 + EMA5/RSI7 - Attends 1 bougie", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}

    # V2 PRO FILTRE DOUX
    if score_haut >= seuil and not proche_resistance:
        return {"signal": "CALL / HAUSSE", "raison": f"FILTRE DOUX : {score_haut}/6 HAUSSE - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    if score_bas >= seuil and not proche_support:
        return {"signal": "PUT / BAISSE", "raison": f"FILTRE DOUX : {score_bas}/6 BAISSE - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    if score_haut >= seuil and proche_resistance:
        return {"signal": "ATTENDRE", "raison": "Filtre DOUX : Score bon mais vraiment collé à la Résistance", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    if score_bas >= seuil and proche_support:
        return {"signal": "ATTENDRE", "raison": "Filtre DOUX : Score bon mais vraiment collé au Support", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    return {"signal": "ATTENDRE", "raison": f"Filtre DOUX : Pas {seuil}/6 - Score HAUSSE {score_haut}, BAISSE {score_bas}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}

if st.button("🔍 ANALYSER MAINTENANT", type="primary"):
    is_scalp = mode.startswith("⚡")
    with st.spinner("Analyse avec filtre doux..."):
        ticker = PAIRES[paire]
        df = recuperer_donnees(ticker)
        if df.empty or len(df) < 100:
            st.error("Données insuffisantes.")
        else:
            df = calculer_indicateurs(df)
            df = df.iloc[:-1].copy()
            df = df.dropna(subset=["RSI", "WCCI", "CFO", "MACD_HIST", "ATR", "BB_MID", "EMA50"])
            if len(df) < 4:
                st.error("Pas assez de données pour 3 bougies.")
            else:
                analyse = analyser_signal(df, is_scalping=is_scalp)
                c = df.iloc[-1]
                st.divider()
                st.subheader(f"🎯 SIGNAL - FILTRE DOUX ({SEUIL_V2PRO}/6 V2 PRO, {SEUIL_SCALPING}/6 Scalping)")
                st.metric("Prix", f"{c['Close']:.5f}")
                st.metric("RSI 14", f"{c['RSI']:.2f}")
                st.metric("RSI 7", f"{c['RSI7']:.2f}")
                st.metric("EMA 5 / 9 / 21", f"{c['EMA5']:.5f} / {c['EMA9']:.5f} / {c['EMA21']:.5f}")
                st.metric("WCCI 14", f"{c['WCCI']:.2f}")
                st.metric("CFO 14", f"{c['CFO']:.4f}")
                if analyse["signal"] == "CALL / HAUSSE":
                    st.success(f"🟢 CALL - {expiration} mn")
                elif analyse["signal"] == "PUT / BAISSE":
                    st.error(f"🔴 PUT - {expiration} mn")
                else:
                    st.warning("⏳ ATTENDRE")
                st.write("**Motif :**", analyse["raison"])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Score HAUSSE", f"{analyse['score_haut']}/6")
                with col2:
                    st.metric("Score BAISSE", f"{analyse['score_bas']}/6")
                st.divider()
                st.subheader("🕯️ Les 3 Dernières Bougies")
                st.info(f"**Figure :** {analyse['info_3']['figure_3']} | **Vertes :** {analyse['info_3']['nb_hausse']} | **Rouges :** {analyse['info_3']['nb_baisse']} | **Doji :** {analyse['info_3']['nb_doji']}")
                st.dataframe(pd.DataFrame(analyse["info_3"]["liste"]), use_container_width=True, hide_index=True)
                st.divider()
                st.subheader("📍 Support et résistance - Filtre DOUX")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Support", f"{analyse['support']:.5f}" if pd.notna(analyse["support"]) else "Indisponible")
                    if analyse["proche_support"]:
                        st.caption(f"⚠️ Collé au Support (< {DISTANCE_SUPPORT} x ATR) - Filtre doux bloque")
                with col2:
                    st.metric("Résistance", f"{analyse['resistance']:.5f}" if pd.notna(analyse["resistance"]) else "Indisponible")
                    if analyse["proche_resistance"]:
                        st.caption(f"⚠️ Collé à la Résistance (< {DISTANCE_SUPPORT} x ATR) - Filtre doux bloque")
                st.subheader("📋 Tableau des confirmations")
                confirmations = pd.DataFrame({
                    "Indicateur": ["EMA 9 / 21 / 50", "RSI 14", "WCCI 14", "CFO 14", "MACD", "Bollinger", "3 Bougies"],
                    "HAUSSE": [c["EMA9"] > c["EMA21"] > c["EMA50"], 50 < c["RSI"] < 70, c["WCCI"] > 0, c["CFO"] > 0, c["MACD_HIST"] > 0, c["Close"] > c["BB_MID"], analyse["direction"] == "HAUSSE"],
                    "BAISSE": [c["EMA9"] < c["EMA21"] < c["EMA50"], 30 < c["RSI"] < 50, c["WCCI"] < 0, c["CFO"] < 0, c["MACD_HIST"] < 0, c["Close"] < c["BB_MID"], analyse["direction"] == "BAISSE"]
                })
                st.dataframe(confirmations, use_container_width=True, hide_index=True)
                st.subheader("📈 Graphique")
                st.line_chart(df[["Close", "BB_UPPER", "BB_MID", "BB_LOWER", "EMA5", "EMA9", "EMA21"]].tail(100))

# ================= 📸 CAPTURE - FILTRE DOUX =================
st.divider()
st.header(f"📸 Analyser ma capture - {paire} - {expiration} mn - FILTRE DOUX")
if CLE_ACTIVE:
    st.success("✅ AUTO IA active")
    mode_capture = st.radio("Mode capture :", ["🤖 AUTO IA", "✍️ MANUEL"], index=0, horizontal=True)
else:
    mode_capture = st.radio("Mode capture :", ["✍️ MANUEL", "🤖 AUTO IA"], index=0, horizontal=True)
uploaded = st.file_uploader("Envoie ta capture", type=["png","jpg","jpeg","webp"], key="capture_doux")
if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)
    if mode_capture.startswith("🤖"):
        if not CLE_ACTIVE:
            st.error("❌ Mets ta clé dans Secrets ou utilise MANUEL.")
        else:
            if st.button("🧠 ANALYSER MA CAPTURE - FILTRE DOUX", type="primary", use_container_width=True):
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"
                    prompt = f"Tu es un analyste PRO IQ Option avec FILTRE DOUX. Actif : {paire}. Analyse les 3 dernières bougies FERMÉES. Expiration : {expiration} mn. Règles FILTRE DOUX : Il faut {SEUIL_V2PRO}/6 pour V2 PRO, {SEUIL_SCALPING}/6 pour Scalping. Ne bloque que si : 3 Doji sur 3, ou volatilité vraiment nulle, ou prix VRAIMENT collé au Support/Résistance (<0.10 x ATR). Sinon donne CALL ou PUT selon le score le plus fort. Donne : tableau 3 bougies, score /6, OÙ ENTRER, CONCLUSION CALL/PUT/ATTENDRE. Ne garantis jamais un gain. Si illisible, dis ILLISIBLE."
                    with st.spinner("🧠 L'IA lit ta capture..."):
                        resp = client_auto.responses.create(model="gpt-5.5", input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":data_url,"detail":"high"}]}])
                        st.markdown(resp.output_text)
                except Exception as e:
                    st.error(f"Erreur IA : {e}")
    else:
        c1, c2, c3 = st.columns(3)
        b3_m = c1.selectbox("Bougie -3", ["Verte","Rouge","Doji"], key="b3_doux")
        b2_m = c2.selectbox("Bougie -2", ["Verte","Rouge","Doji"], key="b2_doux")
        b1_m = c3.selectbox("Bougie -1", ["Verte","Rouge","Doji"], key="b1_doux")
        rsi_m = st.number_input("RSI sur ma capture", value=50.0, min_value=0.0, max_value=100.0, key="rsi_doux")
        if st.button("🔎 ANALYSER - FILTRE DOUX - SANS CLÉ", type="primary", use_container_width=True):
            nb_v = [b3_m, b2_m, b1_m].count("Verte")
            nb_r = [b3_m, b2_m, b1_m].count("Rouge")
            nb_d = [b3_m, b2_m, b1_m].count("Doji")
            if nb_d >= 3:
                st.warning("🟡 ATTENDRE - 3 Doji, filtre doux bloque quand même")
            elif nb_v == 3 and rsi_m > 50:
                st.success(f"🟢 CALL {paire} - 3 Soldats Blancs")
            elif nb_r == 3 and rsi_m < 50:
                st.error(f"🔴 PUT {paire} - 3 Corbeaux Noirs")
            elif nb_v >= 2 and b1_m == "Verte":
                st.success(f"🟢 CALL {paire} - Filtre doux : 2 vertes + dernière verte")
            elif nb_r >= 2 and b1_m == "Rouge":
                st.error(f"🔴 PUT {paire} - Filtre doux : 2 rouges + dernière rouge")
            else:
                st.warning(f"🟡 ATTENDRE {paire} - Pas assez clair même avec filtre doux")

st.caption("V2 PRO + SCALPING + 3 BOUGIES + FILTRE DOUX | Change les réglages en haut du code pour plus ou moins de signaux.")
