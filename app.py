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

st.set_page_config(page_title="IQ OPTION BINAIRE V2 PRO + SCALPING + 3 BOUGIES - SANS FILTRE", page_icon="📈", layout="wide")
st.title("📈 IQ OPTION BINAIRE - V2 PRO + ⚡ SCALPING + 🕯️ 3 BOUGIES")
st.caption("SANS filtre anti-faux signaux - Plus de signaux, plus de risque")

if CLE_ACTIVE:
    st.success("✅ Clé OpenAI AUTOMATIQUE active")
else:
    st.info("ℹ️ Pas de clé automatique. Capture en MANUEL.")

st.warning("⚠️ FILTRE ANTI-FAUX SIGNAUX SUPPRIMÉ : Le robot donne maintenant un signal même si la volatilité est faible, même si c'est un Doji, même si le Support/Résistance est proche. Tu auras plus de signaux, mais plus de pertes possibles. Utilise un petit montant.")

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
mode = st.radio("Mode :", ["📊 V2 PRO - Normal (1 à 19 mn, 6/6)", "⚡ SCALPING - Rapide (1 à 5 mn, 4/6)"], index=0)

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

# ================= 🕯️ ANALYSE DES 3 DERNIÈRES BOUGIES =================
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
        {"Bougie": "Bougie -3 (la plus ancienne)", "Type": desc3, "Direction": dir3, "Open": round(float(b3["Open"]),5), "Close": round(float(b3["Close"]),5), "Corps %": round(ratio3*100,1)},
        {"Bougie": "Bougie -2 (au milieu)", "Type": desc2, "Direction": dir2, "Open": round(float(b2["Open"]),5), "Close": round(float(b2["Close"]),5), "Corps %": round(ratio2*100,1)},
        {"Bougie": "Bougie -1 (la plus récente)", "Type": desc1, "Direction": dir1, "Open": round(float(b1["Open"]),5), "Close": round(float(b1["Close"]),5), "Corps %": round(ratio1*100,1)},
    ]
    nb_hausse = sum([1 for d in [dir3, dir2, dir1] if d == "HAUSSE"])
    nb_baisse = sum([1 for d in [dir3, dir2, dir1] if d == "BAISSE"])
    nb_doji = sum([1 for d in [dir3, dir2, dir1] if d == "NEUTRE"])
    figure_3 = "Aucune figure spéciale"; direction_3 = "NEUTRE"; force_3 = "Faible"
    if nb_hausse == 3:
        if b1["Close"] > b2["Close"] > b3["Close"]:
            figure_3 = "🟢 3 Soldats Blancs - 3 vertes qui montent"; direction_3 = "HAUSSE"; force_3 = "Forte"
        else:
            figure_3 = "🟢 3 Bougies Vertes"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
    elif nb_baisse == 3:
        if b1["Close"] < b2["Close"] < b3["Close"]:
            figure_3 = "🔴 3 Corbeaux Noirs - 3 rouges qui descendent"; direction_3 = "BAISSE"; force_3 = "Forte"
        else:
            figure_3 = "🔴 3 Bougies Rouges"; direction_3 = "BAISSE"; force_3 = "Moyenne"
    elif nb_hausse == 2 and nb_baisse == 1:
        if dir1 == "HAUSSE":
            figure_3 = "🟢 2 Vertes / 1 Rouge - La dernière est verte"; direction_3 = "HAUSSE"; force_3 = "Moyenne"
        else:
            figure_3 = "🟡 2 Vertes / 1 Rouge - Mais la dernière est rouge"; direction_3 = "NEUTRE"; force_3 = "Faible"
    elif nb_baisse == 2 and nb_hausse == 1:
        if dir1 == "BAISSE":
            figure_3 = "🔴 2 Rouges / 1 Verte - La dernière est rouge"; direction_3 = "BAISSE"; force_3 = "Moyenne"
        else:
            figure_3 = "🟡 2 Rouges / 1 Verte - Mais la dernière est verte"; direction_3 = "NEUTRE"; force_3 = "Faible"
    elif nb_doji >= 2:
        figure_3 = "🟡 Beaucoup de Doji - Marché indécis"; direction_3 = "NEUTRE"; force_3 = "Faible"
    elif nb_doji == 1:
        figure_3 = "🟡 1 Doji sur 3 bougies - Petite hésitation"
        if nb_hausse == 2:
            direction_3 = "HAUSSE"; force_3 = "Faible"
        elif nb_baisse == 2:
            direction_3 = "BAISSE"; force_3 = "Faible"
    return {"liste": liste, "figure_3": figure_3, "direction_3": direction_3, "force_3": force_3, "nb_hausse": nb_hausse, "nb_baisse": nb_baisse, "nb_doji": nb_doji, "chandelier": figure_3, "direction": direction_3}

# ================= ❌ FILTRE ANTI-FAUX SIGNAUX SUPPRIMÉ =================
# AVANT, il y avait ici :
# - if volatilite_faible -> ATTENDRE
# - if bougie_faible / Doji -> ATTENDRE
# - if proche_support / proche_resistance -> ATTENDRE
# MAINTENANT, c'est SUPPRIMÉ. On ne bloque plus.
# On regarde juste : Score + Direction des 3 bougies + EMA5/RSI7 pour Scalping.
# Support / Résistance sont juste affichés pour info, ils ne bloquent plus.

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
    # On calcule proche_support / proche_resistance juste pour AFFICHAGE, pas pour bloquer
    proche_support = (pd.notna(support) and atr > 0 and prix - support <= atr * 0.30)
    proche_resistance = (pd.notna(resistance) and atr > 0 and resistance - prix <= atr * 0.30)

    if is_scalping:
        scalp_haut_rapide = (c["EMA5"] > c["EMA9"] and c["RSI7"] > 50)
        scalp_bas_rapide = (c["EMA5"] < c["EMA9"] and c["RSI7"] < 50)
        # SANS FILTRE : même si volatilité faible ou Doji, on donne un signal si score + 3 bougies sont d'accord
        # Si les 3 bougies sont NEUTRE (que des Doji), on prend la direction du score le plus fort
        if score_haut >= 4 and scalp_haut_rapide:
            # Si 3 bougies HAUSSE ou même NEUTRE mais score fort, on donne CALL
            return {"signal": "CALL / HAUSSE", "raison": f"SCALPING SANS FILTRE : {score_haut}/6 + EMA5 > EMA9 + RSI7 > 50 - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        if score_bas >= 4 and scalp_bas_rapide:
            return {"signal": "PUT / BAISSE", "raison": f"SCALPING SANS FILTRE : {score_bas}/6 + EMA5 < EMA9 + RSI7 < 50 - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        # Si score_haut > score_bas, on donne CALL même si 3 bougies pas parfaites (SANS FILTRE)
        if score_haut > score_bas and score_haut >= 3:
            return {"signal": "CALL / HAUSSE", "raison": f"SCALPING SANS FILTRE : Score HAUSSE {score_haut} > BAISSE {score_bas} - On prend CALL", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        if score_bas > score_haut and score_bas >= 3:
            return {"signal": "PUT / BAISSE", "raison": f"SCALPING SANS FILTRE : Score BAISSE {score_bas} > HAUSSE {score_haut} - On prend PUT", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
        return {"signal": "ATTENDRE", "raison": "SCALPING SANS FILTRE : Scores égaux, impossible de choisir", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}

    # V2 PRO SANS FILTRE
    if score_haut >= 6:
        return {"signal": "CALL / HAUSSE", "raison": f"SANS FILTRE : 6/6 HAUSSE - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    if score_bas >= 6:
        return {"signal": "PUT / BAISSE", "raison": f"SANS FILTRE : 6/6 BAISSE - 3 bougies : {chandelier}", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    # SANS FILTRE : si pas 6/6, on prend quand même le plus fort à partir de 4/6
    if score_haut >= 4 and score_haut > score_bas:
        return {"signal": "CALL / HAUSSE", "raison": f"SANS FILTRE : Score HAUSSE {score_haut}/6 > BAISSE {score_bas}/6 - On prend CALL même sans 6/6", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    if score_bas >= 4 and score_bas > score_haut:
        return {"signal": "PUT / BAISSE", "raison": f"SANS FILTRE : Score BAISSE {score_bas}/6 > HAUSSE {score_haut}/6 - On prend PUT même sans 6/6", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    # Même à 3/6, on choisit le plus fort - SANS FILTRE
    if score_haut > score_bas:
        return {"signal": "CALL / HAUSSE", "raison": f"SANS FILTRE : Score HAUSSE {score_haut} > BAISSE {score_bas} - On prend CALL", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "HAUSSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    if score_bas > score_haut:
        return {"signal": "PUT / BAISSE", "raison": f"SANS FILTRE : Score BAISSE {score_bas} > HAUSSE {score_haut} - On prend PUT", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": "BAISSE", "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}
    return {"signal": "ATTENDRE", "raison": "Scores égaux, impossible de choisir", "score_haut": score_haut, "score_bas": score_bas, "chandelier": chandelier, "direction": direction, "info_3": info_3, "support": support, "resistance": resistance, "proche_support": proche_support, "proche_resistance": proche_resistance}

if st.button("🔍 ANALYSER MAINTENANT", type="primary"):
    is_scalp = mode.startswith("⚡")
    with st.spinner("Analyse SANS filtre..."):
        ticker = PAIRES[paire]
        df = recuperer_donnees(ticker)
        if df.empty or len(df) < 100:
            st.error("Données insuffisantes. Essaie une autre paire.")
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
                if is_scalp:
                    st.subheader("⚡ Résultat SCALPING - SANS FILTRE")
                else:
                    st.subheader("📊 Résultat V2 PRO - SANS FILTRE")
                st.metric("Prix", f"{c['Close']:.5f}")
                st.metric("RSI 14", f"{c['RSI']:.2f}")
                st.metric("RSI 7 - Rapide", f"{c['RSI7']:.2f}")
                st.metric("EMA 5 / 9 / 21", f"{c['EMA5']:.5f} / {c['EMA9']:.5f} / {c['EMA21']:.5f}")
                st.metric("WCCI 14", f"{c['WCCI']:.2f}")
                st.metric("CFO 14", f"{c['CFO']:.4f}")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("MACD", f"{c['MACD']:.5f}")
                with col2:
                    st.metric("MACD Histogramme", f"{c['MACD_HIST']:.5f}")
                st.divider()
                st.subheader("🎯 SIGNAL - SANS FILTRE")
                if analyse["signal"] == "CALL / HAUSSE":
                    st.success(f"🟢 CALL - {expiration} mn")
                elif analyse["signal"] == "PUT / BAISSE":
                    st.error(f"🔴 PUT - {expiration} mn")
                else:
                    st.warning("⏳ ATTENDRE - Scores égaux")
                st.write("**Motif :**", analyse["raison"])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Score HAUSSE", f"{analyse['score_haut']}/6")
                with col2:
                    st.metric("Score BAISSE", f"{analyse['score_bas']}/6")
                st.divider()
                st.subheader("🕯️ Les 3 Dernières Bougies")
                st.info(f"**Figure :** {analyse['info_3']['figure_3']} | **Vertes :** {analyse['info_3']['nb_hausse']} | **Rouges :** {analyse['info_3']['nb_baisse']} | **Doji :** {analyse['info_3']['nb_doji']}")
                df_3 = pd.DataFrame(analyse["info_3"]["liste"])
                st.dataframe(df_3, use_container_width=True, hide_index=True)
                st.divider()
                st.subheader("📍 Support et résistance - Affiché pour info, ne bloque plus")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Support", f"{analyse['support']:.5f}" if pd.notna(analyse["support"]) else "Indisponible")
                    if analyse["proche_support"]:
                        st.caption("⚠️ Prix proche du Support, mais on ne bloque plus (filtre supprimé)")
                with col2:
                    st.metric("Résistance", f"{analyse['resistance']:.5f}" if pd.notna(analyse["resistance"]) else "Indisponible")
                    if analyse["proche_resistance"]:
                        st.caption("⚠️ Prix proche de la Résistance, mais on ne bloque plus (filtre supprimé)")
                st.subheader("📋 Tableau des confirmations")
                confirmations = pd.DataFrame({
                    "Indicateur": ["EMA 9 / 21 / 50", "RSI 14", "WCCI 14", "CFO 14", "MACD", "Bollinger Bands", "3 Bougies"],
                    "HAUSSE": [c["EMA9"] > c["EMA21"] > c["EMA50"], 50 < c["RSI"] < 70, c["WCCI"] > 0, c["CFO"] > 0, c["MACD_HIST"] > 0, c["Close"] > c["BB_MID"], analyse["direction"] == "HAUSSE"],
                    "BAISSE": [c["EMA9"] < c["EMA21"] < c["EMA50"], 30 < c["RSI"] < 50, c["WCCI"] < 0, c["CFO"] < 0, c["MACD_HIST"] < 0, c["Close"] < c["BB_MID"], analyse["direction"] == "BAISSE"]
                })
                st.dataframe(confirmations, use_container_width=True, hide_index=True)
                st.subheader("📈 Graphique")
                graphique = df[["Close", "BB_UPPER", "BB_MID", "BB_LOWER", "EMA5", "EMA9", "EMA21"]].tail(100)
                st.line_chart(graphique)

# ================= 📸 CAPTURE - SANS FILTRE =================
st.divider()
st.header(f"📸 Analyser ma capture - {paire} - {expiration} mn - SANS FILTRE")
st.caption("La capture aussi est SANS filtre. L'IA va donner CALL ou PUT même si c'est pas propre.")

if CLE_ACTIVE:
    st.success("✅ AUTO IA active")
    mode_capture = st.radio("Mode capture :", ["🤖 AUTO IA", "✍️ MANUEL"], index=0, horizontal=True)
else:
    st.warning("⚠️ Pas de clé. Utilise MANUEL.")
    mode_capture = st.radio("Mode capture :", ["✍️ MANUEL", "🤖 AUTO IA"], index=0, horizontal=True)

uploaded = st.file_uploader("Envoie ta capture", type=["png","jpg","jpeg","webp"], key="capture_sans_filtre")
if uploaded:
    st.image(uploaded, caption="Ta capture", use_container_width=True)
    if mode_capture.startswith("🤖"):
        if not CLE_ACTIVE:
            st.error("❌ Mets ta clé dans Secrets ou utilise MANUEL.")
        else:
            if st.button("🧠 ANALYSER MA CAPTURE - SANS FILTRE", type="primary", use_container_width=True):
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"
                    # PROMPT SANS FILTRE : on dit à l'IA de ne pas bloquer
                    prompt = f"Tu es un analyste PRO IQ Option. Actif : {paire}. Analyse les 3 dernières bougies FERMÉES, ignore la bougie en cours. Expiration : {expiration} mn. MODE SANS FILTRE : Ne dis JAMAIS ATTENDRE à cause de volatilité faible, Doji, ou Support/Résistance proche. Donne toujours CALL ou PUT selon le score le plus fort, même si c'est 3/6. Si scores égaux, choisis selon la dernière bougie. Donne : tableau 3 bougies, score /6, OÙ ENTRER, CONCLUSION CALL ou PUT. Ne garantis jamais un gain. Si illisible, dis ILLISIBLE."
                    with st.spinner("🧠 L'IA lit ta capture SANS filtre..."):
                        resp = client_auto.responses.create(model="gpt-5.5", input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":data_url,"detail":"high"}]}])
                        st.markdown(resp.output_text)
                except Exception as e:
                    st.error(f"Erreur IA : {e}")
    else:
        st.success("✅ MANUEL - SANS FILTRE")
        c1, c2, c3 = st.columns(3)
        b3_m = c1.selectbox("Bougie -3", ["Verte","Rouge","Doji"], key="b3_sf")
        b2_m = c2.selectbox("Bougie -2", ["Verte","Rouge","Doji"], key="b2_sf")
        b1_m = c3.selectbox("Bougie -1", ["Verte","Rouge","Doji"], key="b1_sf")
        rsi_m = st.number_input("RSI sur ma capture", value=50.0, min_value=0.0, max_value=100.0, key="rsi_sf")
        if st.button("🔎 ANALYSER - SANS FILTRE - SANS CLÉ", type="primary", use_container_width=True):
            nb_v = [b3_m, b2_m, b1_m].count("Verte")
            nb_r = [b3_m, b2_m, b1_m].count("Rouge")
            # SANS FILTRE : on choisit toujours, même si Doji
            if nb_v >= nb_r and rsi_m >= 50:
                st.success(f"🟢 CALL {paire} pour {expiration} mn - SANS FILTRE : {nb_v} Verte(s) vs {nb_r} Rouge(s)")
            elif nb_r > nb_v and rsi_m < 50:
                st.error(f"🔴 PUT {paire} pour {expiration} mn - SANS FILTRE : {nb_r} Rouge(s) vs {nb_v} Verte(s)")
            elif nb_v > nb_r:
                st.success(f"🟢 CALL {paire} pour {expiration} mn - SANS FILTRE : Plus de vertes")
            elif nb_r > nb_v:
                st.error(f"🔴 PUT {paire} pour {expiration} mn - SANS FILTRE : Plus de rouges")
            else:
                # Même si égal, on prend la dernière bougie - SANS FILTRE
                if b1_m == "Verte":
                    st.success(f"🟢 CALL {paire} - SANS FILTRE : Égalité, dernière bougie verte")
                elif b1_m == "Rouge":
                    st.error(f"🔴 PUT {paire} - SANS FILTRE : Égalité, dernière bougie rouge")
                else:
                    if rsi_m >= 50:
                        st.success(f"🟢 CALL {paire} - SANS FILTRE : Égalité + Doji, RSI >= 50")
                    else:
                        st.error(f"🔴 PUT {paire} - SANS FILTRE : Égalité + Doji, RSI < 50")

st.caption("V2 PRO + SCALPING + 3 BOUGIES - SANS FILTRE ANTI-FAUX SIGNAUX | Plus de signaux, plus de risque.")
