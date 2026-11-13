import os
import base64
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, date

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

st.set_page_config(page_title="IQ OPTION AI TRADER V6.5 - TOUS ACTIFS", page_icon="📈", layout="wide")
st.title("📈 IQ OPTION AI TRADER V6.5 - TOUS ACTIFS IQ OPTION")
st.caption("⚠️ BOUGIES 2 MIN | Expiration 1 à 19 min au choix | DOUBLE FILTRE DXY PRO MAX | Tous actifs IQ Option")

# ================= TOUS LES ACTIFS IQ OPTION =================
ACTIFS_IQ_OPTION = {
    "💵 DOLLAR INDEX": [
        "Dollar Index (DXY)",
    ],
    "💱 FOREX - MAJEURES": [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD",
    ],
    "💱 FOREX - MINEURES": [
        "EUR/GBP", "EUR/JPY", "EUR/CHF", "EUR/AUD", "EUR/CAD", "EUR/NZD",
        "GBP/JPY", "GBP/CHF", "GBP/AUD", "GBP/CAD", "GBP/NZD",
        "AUD/JPY", "AUD/CHF", "AUD/CAD", "AUD/NZD",
        "NZD/JPY", "NZD/CHF", "NZD/CAD",
        "CAD/JPY", "CAD/CHF", "CHF/JPY",
        "EUR/SEK", "EUR/NOK", "EUR/DKK", "EUR/PLN", "EUR/HUF", "EUR/CZK",
        "GBP/SEK", "GBP/NOK", "USD/SEK", "USD/NOK", "USD/DKK", "USD/PLN",
        "USD/SGD", "USD/HKD", "USD/CNH", "USD/TRY", "USD/ZAR", "USD/MXN", "USD/BRL",
        "USD/THB", "USD/IDR", "USD/PHP", "USD/MYR", "USD/INR", "USD/KRW",
        "AUD/SGD", "EUR/SGD", "GBP/SGD", "EUR/TRY", "GBP/TRY", "EUR/ZAR", "GBP/ZAR",
        "EUR/MXN", "GBP/MXN", "EUR/BRL", "GBP/BRL", "USD/COP", "USD/CLP", "USD/PEN",
        "EUR/THB", "GBP/THB", "JPY/THB", "NOK/JPY", "SEK/JPY",
    ],
    "💱 FOREX - OTC (Week-end)": [
        "EUR/USD OTC", "GBP/USD OTC", "USD/JPY OTC", "USD/CHF OTC", "AUD/USD OTC", "NZD/USD OTC", "USD/CAD OTC",
        "EUR/GBP OTC", "EUR/JPY OTC", "GBP/JPY OTC", "AUD/JPY OTC", "EUR/AUD OTC", "GBP/AUD OTC",
        "EUR/CAD OTC", "GBP/CAD OTC", "AUD/CAD OTC", "EUR/CHF OTC", "GBP/CHF OTC",
        "USD/MXN OTC", "USD/BRL OTC", "USD/ZAR OTC", "USD/TRY OTC", "USD/THB OTC",
        "EUR/ZAR OTC", "GBP/ZAR OTC", "EUR/SGD OTC", "USD/SGD OTC", "USD/NOK OTC", "USD/SEK OTC",
        "EUR/NZD OTC", "GBP/NZD OTC", "AUD/NZD OTC", "NZD/JPY OTC", "NZD/CAD OTC",
        "EUR/USD OTC 2", "GBP/USD OTC 2",
    ],
    "₿ CRYPTO": [
        "BTC/USD", "ETH/USD", "LTC/USD", "XRP/USD", "ADA/USD", "SOL/USD", "DOT/USD", "DOGE/USD",
        "AVAX/USD", "LINK/USD", "MATIC/USD", "TRX/USD", "BNB/USD", "ATOM/USD", "NEAR/USD",
        "BTC/EUR", "ETH/EUR", "BTC/JPY",
    ],
    "₿ CRYPTO - OTC": [
        "BTC/USD OTC", "ETH/USD OTC", "LTC/USD OTC", "XRP/USD OTC", "DOGE/USD OTC", "SOL/USD OTC",
    ],
    "🏢 ACTIONS - USA": [
        "AAPL - Apple", "TSLA - Tesla", "AMZN - Amazon", "MSFT - Microsoft", "GOOGL - Google",
        "META - Meta", "NVDA - Nvidia", "NFLX - Netflix", "AMD - AMD", "INTC - Intel",
        "BA - Boeing", "DIS - Disney", "PYPL - PayPal", "UBER - Uber", "COIN - Coinbase",
        "JPM - JPMorgan", "BAC - Bank of America", "V - Visa", "MA - Mastercard",
        "PFE - Pfizer", "XOM - Exxon", "WMT - Walmart", "NKE - Nike",
    ],
    "🏢 ACTIONS - OTC": [
        "AAPL OTC", "TSLA OTC", "AMZN OTC", "MSFT OTC", "GOOGL OTC", "META OTC", "NVDA OTC",
    ],
    "📊 INDICES": [
        "S&P 500", "NASDAQ 100", "DOW JONES", "DAX 40", "CAC 40", "FTSE 100",
        "NIKKEI 225", "EURO STOXX 50", "ASX 200", "Hang Seng",
    ],
    "🥇 MATIÈRES PREMIÈRES": [
        "GOLD - Or", "SILVER - Argent", "OIL WTI - Pétrole", "OIL BRENT - Pétrole Brent",
        "NATURAL GAS - Gaz", "COPPER - Cuivre", "PLATINUM - Platine",
    ],
    "📦 ETF / AUTRES": [
        "SPY - S&P ETF", "QQQ - Nasdaq ETF", "GLD - Or ETF", "SLV - Argent ETF", "USO - Pétrole ETF",
    ],
}

# Aplatir pour le selectbox, avec groupes visibles
LISTE_POUR_SELECT = []
for groupe, liste in ACTIFS_IQ_OPTION.items():
    LISTE_POUR_SELECT.append(f"--- {groupe} ---")
    LISTE_POUR_SELECT.extend(liste)

TICKER_YAHOO = {
    "Dollar Index (DXY)": "DX-Y.NYB",
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X",
    "USD/CAD": "USDCAD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "AUD/JPY": "AUDJPY=X", "USD/BRL": "USDBRL=X",
    "USD/MXN": "USDMXN=X", "USD/ZAR": "USDZAR=X",
    "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "LTC/USD": "LTC-USD", "XRP/USD": "XRP-USD",
    "DOGE/USD": "DOGE-USD", "SOL/USD": "SOL-USD", "ADA/USD": "ADA-USD", "BNB/USD": "BNB-USD",
    "AAPL - Apple": "AAPL", "TSLA - Tesla": "TSLA", "AMZN - Amazon": "AMZN", "MSFT - Microsoft": "MSFT",
    "GOOGL - Google": "GOOGL", "META - Meta": "META", "NVDA - Nvidia": "NVDA", "NFLX - Netflix": "NFLX",
    "S&P 500": "^GSPC", "NASDAQ 100": "^NDX", "DOW JONES": "^DJI", "DAX 40": "^GDAXI",
    "CAC 40": "^FCHI", "FTSE 100": "^FTSE", "NIKKEI 225": "^N225",
    "GOLD - Or": "GC=F", "SILVER - Argent": "SI=F", "OIL WTI - Pétrole": "CL=F", "OIL BRENT - Pétrole Brent": "BZ=F",
}

if "mes_paires" not in st.session_state:
    st.session_state.mes_paires = []
if "risk_journal" not in st.session_state:
    st.session_state.risk_journal = []
if "dxy_cache" not in st.session_state:
    st.session_state.dxy_cache = None

# ================= FONCTIONS DXY PRO MAX =================
def calcul_rsi_series(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calcul_adx_dxy(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff(); minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    tr = pd.concat([high-low, (high-close.shift(1)).abs(), (low-close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return float(adx.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])

def obtenir_analyse_dxy():
    try:
        data = yf.download("DX-Y.NYB", period="5d", interval="2m", progress=False, auto_adjust=False)
        if data.empty: return None, None
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        close = data["Close"]
        prix_dxy = float(close.iloc[-1])
        ema9 = float(close.ewm(span=9).mean().iloc[-1]); ema21 = float(close.ewm(span=21).mean().iloc[-1])
        rsi_dxy = float(calcul_rsi_series(close).iloc[-1])
        adx_dxy, pdi, mdi = calcul_adx_dxy(data)
        if ema9 > ema21 and rsi_dxy > 50: tendance = "DXY monte - Dollar FORT"
        elif ema9 < ema21 and rsi_dxy < 50: tendance = "DXY descend - Dollar FAIBLE"
        else: tendance = "DXY neutre / range"
        if adx_dxy >= 25: force = f"FORTE (ADX {adx_dxy:.1f})"
        elif adx_dxy >= 20: force = f"MODÉRÉE (ADX {adx_dxy:.1f})"
        else: force = f"FAIBLE (ADX {adx_dxy:.1f})"
        tendance_dxy = {"tendance": tendance, "rsi": round(rsi_dxy, 1), "force": force, "prix": round(prix_dxy, 2), "ema9": ema9, "ema21": ema21, "adx": round(adx_dxy, 1)}
        if adx_dxy >= 25 and ((tendance == "DXY monte - Dollar FORT" and pdi > mdi) or (tendance == "DXY descend - Dollar FAIBLE" and mdi > pdi)):
            confirmation = "CONFIRMÉ - Tendance DXY forte et validée"
        elif adx_dxy >= 20 and tendance != "DXY neutre / range":
            confirmation = "CONFIRMÉ FAIBLE - Tendance modérée, prudence"
        elif tendance == "DXY neutre / range":
            confirmation = "NON CONFIRMÉ - DXY en range"
        else:
            confirmation = "NON CONFIRMÉ - ADX faible, pas de tendance"
        confirmation_dxy = {"confirmation": confirmation, "adx": round(adx_dxy, 1), "plus_di": round(pdi, 1), "moins_di": round(mdi, 1)}
        return tendance_dxy, confirmation_dxy
    except Exception:
        return None, None

def evaluer_double_filtre_dxy(actif_choisi, tendance_txt, confirmation_txt):
    # Pour les actifs NON-USD (Or, Actions, Crypto, Indices), le DXY est un filtre secondaire, pas bloquant
    a = actif_choisi.upper()
    est_forex_usd = "USD" in a and ("EUR" in a or "GBP" in a or "AUD" in a or "NZD" in a or "JPY" in a or "CHF" in a or "CAD" in a or "MXN" in a or "BRL" in a or "ZAR" in a or a.startswith("USD"))
    if actif_choisi == "Dollar Index (DXY)":
        return {"autorisation": True, "message": "✅ Tu trades le DXY lui-même, pas besoin de filtre DXY.", "sens": "NEUTRE"}
    if not est_forex_usd:
        # Or, Actions, Crypto, Indices : DXY donne juste une info, ne bloque pas
        return {"autorisation": True, "message": f"ℹ️ Actif non-USD ({actif_choisi}) : DXY = {tendance_txt} / {confirmation_txt}. Filtre informatif, pas bloquant.", "sens": "NEUTRE"}
    usd_en_deuxieme = "USD" in a and a.endswith("USD")
    usd_en_premier = a.startswith("USD")
    if "NON CONFIRMÉ" in confirmation_txt:
        return {"autorisation": False, "message": "🚫 DOUBLE FILTRE DXY : NON CONFIRMÉ. DXY en range ou ADX faible. ATTENDS.", "sens": "ATTENDRE"}
    if tendance_txt == "DXY monte - Dollar FORT":
        if usd_en_deuxieme: return {"autorisation": True, "message": "✅ DOUBLE FILTRE VALIDÉ : DXY FORT confirmé → Paire risque de BAISSER. Privilégie PUT.", "sens": "PUT"}
        if usd_en_premier: return {"autorisation": True, "message": "✅ DOUBLE FILTRE VALIDÉ : DXY FORT confirmé → Paire risque de MONTER. Privilégie CALL.", "sens": "CALL"}
        return {"autorisation": True, "message": "✅ DOUBLE FILTRE VALIDÉ : DXY FORT confirmé.", "sens": "DXY FORT"}
    if tendance_txt == "DXY descend - Dollar FAIBLE":
        if usd_en_deuxieme: return {"autorisation": True, "message": "✅ DOUBLE FILTRE VALIDÉ : DXY FAIBLE confirmé → Paire risque de MONTER. Privilégie CALL.", "sens": "CALL"}
        if usd_en_premier: return {"autorisation": True, "message": "✅ DOUBLE FILTRE VALIDÉ : DXY FAIBLE confirmé → Paire risque de BAISSER. Privilégie PUT.", "sens": "PUT"}
        return {"autorisation": True, "message": "✅ DOUBLE FILTRE VALIDÉ : DXY FAIBLE confirmé.", "sens": "DXY FAIBLE"}
    return {"autorisation": False, "message": "🟡 DOUBLE FILTRE DXY : DXY NEUTRE / RANGE. ATTENDRE.", "sens": "ATTENDRE"}

# ================= SIDEBAR - 1. CHOISIR TON ACTIF =================
st.sidebar.header("⚙️ 1. TON ACTIF IQ OPTION")
st.sidebar.caption("Tous les actifs IQ Option sont là. Choisis celui que tu trades.")
# Recherche rapide
recherche = st.sidebar.text_input("🔍 Rechercher un actif (ex: EUR, BTC, AAPL, GOLD)", placeholder="Tape EUR, BTC, GOLD...")
if recherche:
    liste_filtree = [x for x in LISTE_POUR_SELECT if recherche.upper() in x.upper()]
    if not liste_filtree:
        st.sidebar.warning(f"Aucun actif trouvé pour '{recherche}'. Utilise Ajouter MA paire ci-dessous.")
        liste_filtree = LISTE_POUR_SELECT
else:
    liste_filtree = LISTE_POUR_SELECT

# Ajouter mes paires perso en bas
liste_finale = liste_filtree + ["--- MES ACTIFS PERSO ---"] + st.session_state.mes_paires
actif_brut = st.sidebar.selectbox("Choisir l'actif", liste_finale, index=2 if not recherche else 0)
# Si c'est un titre de groupe, on prend EUR/USD par défaut
if actif_brut.startswith("---"):
    actif = "EUR/USD"
    st.sidebar.warning("Choisis un actif, pas un titre de groupe.")
else:
    actif = actif_brut

st.sidebar.subheader("➕ Ajouter MON actif (si pas dans la liste)")
nouvel_actif = st.sidebar.text_input("Ex: USD/THB, SHIB/USD, EUR/USD OTC 3", placeholder="Tape ton actif ici...")
if st.sidebar.button("➕ Ajouter cet actif"):
    nouvel_actif = nouvel_actif.strip().upper()
    if nouvel_actif == "":
        st.sidebar.warning("Tape d'abord ton actif.")
    elif nouvel_actif in liste_finale:
        st.sidebar.info(f"{nouvel_actif} déjà dans la liste.")
    else:
        st.session_state.mes_paires.append(nouvel_actif)
        st.sidebar.success(f"✅ {nouvel_actif} ajouté !")
        st.rerun()
if st.session_state.mes_paires:
    st.sidebar.write("**Mes actifs perso :** " + ", ".join(st.session_state.mes_paires))
    if st.sidebar.button("🗑️ Effacer mes actifs perso"):
        st.session_state.mes_paires = []
        st.rerun()

# ================= SIDEBAR - 2. PÉRIODE 2 MIN + 3. EXPIRATION 1-19 =================
st.sidebar.header("⏱️ 2. PÉRIODE - FIXE 2 MIN")
periode_bougie = "2 min"
st.sidebar.success("✅ Bougies : **2 MIN** - Mets IQ Option en 2 min")
st.sidebar.header("⏳ 3. EXPIRATION - 1 À 19 MIN")
expiration = st.sidebar.slider("Choisis ton expiration (minutes)", min_value=1, max_value=19, value=5, step=1)
st.sidebar.success(f"✅ Expiration choisie : **{expiration} min** (de 1 à 19 min)")
# Aide expiration
if expiration == 1:
    st.sidebar.caption("⚡ 1 min = Très rapide, très risqué. Seulement si signal 12/12 + DXY confirmé.")
elif expiration <= 3:
    st.sidebar.caption("⚡ 1-3 min = Scalping rapide. Bougies 2 min, expiration courte.")
elif expiration <= 6:
    st.sidebar.caption("✅ 4-6 min = Ton réglage idéal avec bougies 2 min. Le plus stable.")
elif expiration <= 10:
    st.sidebar.caption("🕐 7-10 min = Moyen terme, laisse le temps au trade de respirer.")
else:
    st.sidebar.caption("🕐 11-19 min = Long, pour tendance forte ADX > 25.")
st.sidebar.info(f"🎯 Tu trades : **{actif}** | Bougie **2 MIN** | Expiration **{expiration} min**")
mode = st.sidebar.radio("4. Mode", ["SANS capture - Je tape les chiffres", "AVEC capture - Photo graphique", "ENTRAÎNEMENT - Yahoo Finance"])

# ================= DOUBLE FILTRE DXY =================
st.sidebar.divider()
st.subheader("💵 DOUBLE FILTRE DXY PRO MAX")
choix_dxy = st.sidebar.radio("Source DXY :", ["AUTO - Yahoo Finance (recommandé)", "MANUEL - Je tape sur IQ Option"], index=0)
filtre_dxy_resultat = None; alerte_dxy = None; sens_dxy = None
if choix_dxy.startswith("AUTO"):
    if st.sidebar.button("🔄 Actualiser DXY AUTO"):
        st.session_state.dxy_cache = None; st.rerun()
    if st.session_state.dxy_cache is None:
        with st.spinner("Récupération DXY..."):
            tendance_dxy, confirmation_dxy = obtenir_analyse_dxy()
            st.session_state.dxy_cache = (tendance_dxy, confirmation_dxy)
    else:
        tendance_dxy, confirmation_dxy = st.session_state.dxy_cache
    if tendance_dxy and confirmation_dxy:
        filtre_dxy_resultat = evaluer_double_filtre_dxy(actif, tendance_dxy["tendance"], confirmation_dxy["confirmation"])
        st.write("Filtre 1 :", tendance_dxy["tendance"])
        st.write("Filtre 2 :", confirmation_dxy["confirmation"])
        st.write("RSI DXY :", tendance_dxy["rsi"])
        st.write("ADX DXY :", tendance_dxy["force"])
        st.write(f"Prix DXY : {tendance_dxy['prix']} | +DI {confirmation_dxy['plus_di']} / -DI {confirmation_dxy['moins_di']}")
        if filtre_dxy_resultat["autorisation"]: st.success(filtre_dxy_resultat["message"])
        else: st.warning(filtre_dxy_resultat["message"])
        alerte_dxy = filtre_dxy_resultat["message"]; sens_dxy = filtre_dxy_resultat["sens"]
    else:
        filtre_dxy_resultat = None; st.warning("Données DXY indisponibles : aucune confirmation. Passe en MANUEL."); alerte_dxy = "DXY indisponible"
else:
    dxy_manuel = st.sidebar.selectbox("Tendance DXY sur IQ Option :", ["Je ne sais pas", "DXY monte - Dollar FORT", "DXY descend - Dollar FAIBLE", "DXY neutre / range"])
    adx_manuel = st.sidebar.number_input("ADX DXY sur IQ Option", value=22.0)
    if dxy_manuel == "Je ne sais pas": confirmation_manuel = "NON CONFIRMÉ - Je ne sais pas"
    elif adx_manuel < 20: confirmation_manuel = "NON CONFIRMÉ - ADX faible"
    elif adx_manuel >= 25: confirmation_manuel = "CONFIRMÉ - Tendance DXY forte"
    else: confirmation_manuel = "CONFIRMÉ FAIBLE - Tendance modérée"
    st.write("Filtre 1 :", dxy_manuel); st.write("Filtre 2 :", confirmation_manuel)
    st.write("RSI DXY : Non renseigné en manuel"); st.write(f"ADX DXY : {adx_manuel}")
    filtre_dxy_resultat = evaluer_double_filtre_dxy(actif, dxy_manuel, confirmation_manuel)
    if filtre_dxy_resultat["autorisation"]: st.success(filtre_dxy_resultat["message"])
    else: st.warning(filtre_dxy_resultat["message"])
    alerte_dxy = filtre_dxy_resultat["message"]; sens_dxy = filtre_dxy_resultat["sens"]

# ================= RISQUE =================
st.sidebar.divider()
st.sidebar.header("🛡️ Gestion du Risque")
capital = st.sidebar.number_input("Ton capital ($)", value=100.0, min_value=10.0, step=10.0)
risque_pct = st.sidebar.slider("Risque par trade %", 1, 5, 2)
mise_conseillee = capital * risque_pct / 100
st.sidebar.write(f"💰 Mise conseillée : **${mise_conseillee:.2f}**")
today = str(date.today())
journal_today = [x for x in st.session_state.risk_journal if x.get("date") == today]
pertes_today = sum(1 for x in journal_today if x.get("resultat") == "PERTE")
gains_today = sum(1 for x in journal_today if x.get("resultat") == "GAIN")
pertes_consecutives = 0
for x in reversed(st.session_state.risk_journal):
    if x.get("resultat") == "PERTE": pertes_consecutives += 1
    elif x.get("resultat") == "GAIN": break
    else: break
blocage_raison = None
if pertes_consecutives >= 3: blocage_raison = f"🚫 BLOCAGE : 3 pertes d'affilée. STOP 30 min."
elif pertes_today >= 5: blocage_raison = f"🚫 BLOCAGE JOURNALIER : {pertes_today} pertes. ARRÊTE."
if blocage_raison:
    st.sidebar.error(blocage_raison); st.error(blocage_raison)
    if st.button("🔓 Débloquer pour démo"):
        st.session_state.risk_journal = st.session_state.risk_journal[:-3] if len(st.session_state.risk_journal) >= 3 else []; st.rerun()
else:
    st.sidebar.success(f"Aujourd'hui : ✅ {gains_today} | ❌ {pertes_today} | Série : {pertes_consecutives}/3")
with st.sidebar.expander("📓 Journal du jour"):
    if not journal_today: st.write("Aucun trade aujourd'hui.")
    else:
        for j in reversed(journal_today[-10:]): st.write(f"{j['heure']} - {j['actif']} → {j['resultat']}")

# ================= INDICATEURS =================
def calcul_wcci_woodie(df, period=14):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    sma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    return (tp - sma) / (0.015 * md.replace(0, np.nan))
def interprete_wcci(v):
    if v > 200: return "🔴 WCCI > 200 SURACHAT EXTRÊME"
    if v > 100: return "🟠 WCCI > 100 Surachat"
    if v < -200: return "🟢 WCCI < -200 SURVENTE EXTRÊME"
    if v < -100: return "🟡 WCCI < -100 Survente"
    return "WCCI > 0 haussier" if v > 0 else "WCCI < 0 baissier"
def calcul_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean(); ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26; signal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1]), float((macd-signal).iloc[-1])
def calcul_adx(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff(); minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    tr = pd.concat([high-low, (high-close.shift(1)).abs(), (low-close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    dx = 100 * (plus_di-minus_di).abs() / (plus_di+minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return float(adx.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])
def analyse_chandelier_corrige(o, h, l, c, o_prev, h_prev, l_prev, c_prev, o_prev2=None, c_prev2=None):
    patterns=[]; sh=0; sb=0
    corps=abs(c-o); rng=h-l if h!=l else 0.00001; mh=h-max(o,c); mb=min(o,c)-l
    corps_prev=abs(c_prev-o_prev)
    est_verte=c>o; est_rouge=c<o; est_verte_prev=c_prev>o_prev; est_rouge_prev=c_prev<o_prev
    if corps < rng*0.10: patterns.append("➖ Doji")
    if mb > corps*2 and mh < corps*0.5 and min(o,c) > l+rng*0.6:
        patterns.append("🔨 Marteau Haussier"); sh+=2
    if mh > corps*2 and mb < corps*0.5 and max(o,c) < h-rng*0.6:
        patterns.append("⭐ Étoile Filante"); sb+=2
    if est_rouge_prev and est_verte and o < c_prev and c > o_prev and corps > corps_prev*1.1:
        patterns.append("🟢 Englobante Haussière FORTE"); sh+=2
    if est_verte_prev and est_rouge and o > c_prev and c < o_prev and corps > corps_prev*1.1:
        patterns.append("🔴 Englobante Baissière FORTE"); sb+=2
    if est_rouge_prev and est_verte and o > c_prev and c < o_prev:
        patterns.append("🟡 Harami Haussier"); sh+=1
    if est_verte_prev and est_rouge and o < c_prev and c > o_prev:
        patterns.append("🟡 Harami Baissier"); sb+=1
    if o_prev2 is not None and c_prev2 is not None:
        if c_prev2>o_prev2 and c_prev>o_prev and est_verte: patterns.append("🟢 3 Soldats Blancs"); sh+=2
        if c_prev2<o_prev2 and c_prev<o_prev and est_rouge: patterns.append("🔴 3 Corbeaux Noirs"); sb+=2
    if c > h-rng*0.10 and est_verte: patterns.append("⬆️ Clôture proche haut"); sh+=1
    if c < l+rng*0.10 and est_rouge: patterns.append("⬇️ Clôture proche bas"); sb+=1
    if not patterns: patterns.append("Bougie normale")
    return patterns, sh, sb
def decision_pro(bull, bear, macd_hist, adx, plus_di, minus_di, rsi, wcci):
    contradictions=[]
    if rsi > 55 and macd_hist < 0: contradictions.append("RSI haussier mais MACD baissier")
    if rsi < 45 and macd_hist > 0: contradictions.append("RSI baissier mais MACD haussier")
    if adx < 20: contradictions.append(f"ADX {adx:.1f} < 20 = pas de tendance")
    if abs(plus_di-minus_di) < 3: contradictions.append("+DI et -DI trop proches")
    if bull >= 6 and wcci < -100: contradictions.append("Signal haussier mais WCCI <-100")
    if bear >= 6 and wcci > 100: contradictions.append("Signal baissier mais WCCI >100")
    if abs(bull-bear) <= 1: contradictions.append(f"Score serré {bull} vs {bear}")
    if sens_dxy == "CALL" and bear >= 6: contradictions.append("DXY dit CALL mais indicateurs disent PUT")
    if sens_dxy == "PUT" and bull >= 6: contradictions.append("DXY dit PUT mais indicateurs disent CALL")
    if sens_dxy == "ATTENDRE": contradictions.append("DOUBLE FILTRE DXY dit ATTENDRE")
    return contradictions

def donner_position(bull, bear, prix, support, resistance, bb_up, bb_low, bougie, macd_hist, adx, plus_di, minus_di, rsi, wcci, ch_h, ch_b):
    contradictions = decision_pro(bull, bear, macd_hist, adx, plus_di, minus_di, rsi, wcci)
    bull_total = bull + ch_h; bear_total = bear + ch_b
    if len(contradictions) >= 2 or adx < 18 or (filtre_dxy_resultat and not filtre_dxy_resultat["autorisation"]):
        return {"signal": f"🟡 ATTENDRE FORCÉ sur {actif} - DOUBLE FILTRE DXY / Contradictions", "type": "warning", "entree": "NE PAS ENTRER", "condition": f"Attendre que DXY + indicateurs s'alignent. Support {support:.5f} / Résistance {resistance:.5f}", "objectif": "Pas d'objectif", "invalidation": "Pas de signal", "conseil": f"Contradictions : {'; '.join(contradictions)} | DXY : {alerte_dxy}", "contradictions": contradictions}
    if bull_total >= 7 and bougie == "Verte" and not contradictions:
        return {"signal": f"🟢 CALL FORT sur {actif} ({bull_total}/12) - Bougie 2 MIN / Exp {expiration} min - DXY OK", "type": "success", "entree": f"Autour de {prix:.5f}", "condition": f"Après rejet sur {bb_low:.5f} ou Support {support:.5f}", "objectif": f"{resistance:.5f} / Bollinger Haute {bb_up:.5f}", "invalidation": f"Casse Support {support:.5f}", "conseil": f"Expiration {expiration} min. Mise ${mise_conseillee:.2f} | DXY : {alerte_dxy}", "contradictions": []}
    if bear_total >= 7 and bougie == "Rouge" and not contradictions:
        return {"signal": f"🔴 PUT FORT sur {actif} ({bear_total}/12) - Bougie 2 MIN / Exp {expiration} min - DXY OK", "type": "error", "entree": f"Autour de {prix:.5f}", "condition": f"Après rejet sur {bb_up:.5f} ou Résistance {resistance:.5f}", "objectif": f"{support:.5f} / Bollinger Basse {bb_low:.5f}", "invalidation": f"Casse Résistance {resistance:.5f}", "conseil": f"Expiration {expiration} min. Mise ${mise_conseillee:.2f} | DXY : {alerte_dxy}", "contradictions": []}
    return {"signal": f"🟡 ATTENDRE sur {actif} - Hausse {bull_total}/12 | Baisse {bear_total}/12", "type": "warning", "entree": "NE PAS ENTRER", "condition": f"Attendre Support {support:.5f} OU Résistance {resistance:.5f}", "objectif": "Pas d'objectif", "invalidation": "Pas de signal", "conseil": f"{'; '.join(contradictions) if contradictions else 'Score insuffisant'}", "contradictions": contradictions}

def afficher_position(pos, actif_nom):
    if pos["type"] == "success": st.success(pos["signal"])
    elif pos["type"] == "error": st.error(pos["signal"])
    else: st.warning(pos["signal"])
    st.write(f"**📍 ENTRÉE :** {pos['entree']}")
    st.write(f"**🎯 CONDITION :** {pos['condition']}")
    st.write(f"**🏁 OBJECTIF :** {pos['objectif']}")
    st.write(f"**❌ INVALIDATION :** {pos['invalidation']}")
    st.write(f"**💡 CONSEIL :** {pos['conseil']}")
    if pos.get("contradictions"): st.error(f"⚠️ CONTRADICTIONS : {'; '.join(pos['contradictions'])}")
    if alerte_dxy: st.write(f"**💵 DOUBLE FILTRE DXY :** {alerte_dxy}")
    c1, c2, c3 = st.columns(3)
    if c1.button("✅ J'ai GAGNÉ", key=f"win_{actif_nom}_{datetime.now().timestamp()}"):
        st.session_state.risk_journal.append({"date": today, "heure": datetime.now().strftime("%H:%M"), "actif": actif_nom, "signal": pos["signal"], "resultat": "GAIN"}); st.rerun()
    if c2.button("❌ J'ai PERDU", key=f"lose_{actif_nom}_{datetime.now().timestamp()}"):
        st.session_state.risk_journal.append({"date": today, "heure": datetime.now().strftime("%H:%M"), "actif": actif_nom, "signal": pos["signal"], "resultat": "PERTE"}); st.rerun()
    if c3.button("⏭️ PAS pris"): st.info("Bien joué, ne pas trader c'est aussi trader.")

# ================= MODE 1 =================
if mode.startswith("SANS"):
    if blocage_raison: st.stop()
    st.header(f"1. SANS capture - {actif} - BOUGIES 2 MIN - Exp {expiration} min (1 à 19)")
    st.write("Sur IQ Option, mets ton graphique en **2 MIN** : RSI 14, WCCI 14, CFO 14, Bollinger 20,2, EMA 9/21, MACD 12,26,9, ADX 14")
    st.info(f"💰 Mise : ${mise_conseillee:.2f} | Actif : {actif} | Bougies 2 MIN | Expiration {expiration} min | Série pertes : {pertes_consecutives}/3")
    c1, c2, c3, c4 = st.columns(4)
    rsi = c1.number_input("RSI 14", value=50.0, min_value=0.0, max_value=100.0)
    cfo_val = c2.number_input("CFO 14", value=0.0, format="%.3f")
    wcci_val = c3.number_input("WCCI Woodie 14", value=0.0, format="%.1f")
    adx_val = c4.number_input("ADX 14", value=20.0, min_value=0.0, max_value=100.0)
    c5, c6, c7, c8 = st.columns(4)
    macd_val = c5.number_input("MACD Hist", value=0.0, format="%.5f")
    di_plus = c6.number_input("+DI", value=20.0); di_minus = c7.number_input("-DI", value=20.0)
    prix = c8.number_input("Prix actuel", value=1.10950, format="%.5f")
    c9, c10, c11 = st.columns(3)
    ema9 = c9.number_input("EMA 9", value=1.10950, format="%.5f")
    ema21 = c10.number_input("EMA 21", value=1.10940, format="%.5f")
    bougie = c11.selectbox("Dernière bougie 2 MIN", ["Verte", "Rouge"])
    b1, b2, b3, b4, b5 = st.columns(5)
    bb_up = b1.number_input("Bollinger Haute", value=1.11000, format="%.5f")
    bb_mid = b2.number_input("Bollinger Moyenne", value=1.10950, format="%.5f")
    bb_low = b3.number_input("Bollinger Basse", value=1.10900, format="%.5f")
    support = b4.number_input("Support", value=1.10880, format="%.5f")
    resistance = b5.number_input("Résistance", value=1.11020, format="%.5f")
    st.subheader("🕯️ Chandeliers - 3 dernières bougies 2 MIN")
    ch1, ch2, ch3, ch4 = st.columns(4)
    o_prev2 = ch1.number_input("Ouv. Bougie -2", value=1.10930, format="%.5f")
    c_prev2 = ch2.number_input("Clôt. Bougie -2", value=1.10940, format="%.5f")
    o_prev = ch3.number_input("Ouv. Bougie -1", value=1.10940, format="%.5f")
    c_prev = ch4.number_input("Clôt. Bougie -1", value=1.10930, format="%.5f")
    ch5, ch6, ch7, ch8 = st.columns(4)
    o_curr = ch5.number_input("Ouv. Bougie actuelle", value=1.10940, format="%.5f")
    h_curr = ch6.number_input("Plus haut actuelle", value=1.10980, format="%.5f")
    l_curr = ch7.number_input("Plus bas actuelle", value=1.10920, format="%.5f")
    h_prev = ch8.number_input("Plus haut bougie -1", value=1.10970, format="%.5f")
    l_prev = st.number_input("Plus bas bougie -1", value=1.10910, format="%.5f")
    if st.button("🔎 ANALYSE PRO+ - OÙ JE PRENDS POSITION ?", type="primary", use_container_width=True):
        patterns, ch_h, ch_b = analyse_chandelier_corrige(o_curr, h_curr, l_curr, prix, o_prev, h_prev, l_prev, c_prev, o_prev2, c_prev2)
        st.write(f"**🕯️ :** {', '.join(patterns)} | **WCCI :** {interprete_wcci(wcci_val)}")
        bullish = {"EMA 9 > EMA 21": ema9 > ema21, "RSI > 50": rsi > 50, "CFO > 0": cfo_val > 0, "WCCI > 0": wcci_val > 0, "Prix > BB Moyenne": prix > bb_mid, "Bougie Verte": bougie=="Verte", "MACD Hist > 0": macd_val > 0, "ADX > 20 + +DI > -DI": adx_val > 20 and di_plus > di_minus, "Prix > BB Basse": prix > bb_low, "WCCI < 200": wcci_val < 200}
        bearish = {"EMA 9 < EMA 21": ema9 < ema21, "RSI < 50": rsi < 50, "CFO < 0": cfo_val < 0, "WCCI < 0": wcci_val < 0, "Prix < BB Moyenne": prix < bb_mid, "Bougie Rouge": bougie=="Rouge", "MACD Hist < 0": macd_val < 0, "ADX > 20 + -DI > +DI": adx_val > 20 and di_minus > di_plus, "Prix < BB Haute": prix < bb_up, "WCCI > -200": wcci_val > -200}
        pos = donner_position(sum(bullish.values()), sum(bearish.values()), prix, support, resistance, bb_up, bb_low, bougie, macd_val, adx_val, di_plus, di_minus, rsi, wcci_val, ch_h, ch_b)
        afficher_position(pos, actif)

# ================= MODE 2 =================
elif mode.startswith("AVEC"):
    if blocage_raison: st.stop()
    st.header(f"2. AVEC capture - {actif} - BOUGIES 2 MIN - Exp {expiration} min (1 à 19)")
    st.warning("📸 Avant ta capture, vérifie : IQ Option est bien en 2 MIN.")
    uploaded = st.file_uploader("Ta capture IQ Option en 2 MIN", type=["png","jpg","jpeg","webp"])
    if uploaded:
        st.image(uploaded, caption="Ta capture 2 MIN", use_container_width=True)
        colA, colB, colC = st.columns(3)
        voir_rsi = colA.checkbox("Je vois RSI", value=True); voir_wcci = colA.checkbox("Je vois WCCI", value=True)
        voir_macd = colB.checkbox("Je vois MACD", value=False); voir_adx = colB.checkbox("Je vois ADX", value=False)
        voir_boll = colC.checkbox("Je vois Bollinger", value=True); voir_ema = colC.checkbox("Je vois EMA 9/21", value=True)
        colD, colE = st.columns(2)
        support2 = colD.number_input("Support visible", value=1.10880, format="%.5f", key="s2")
        resistance2 = colE.number_input("Résistance visible", value=1.11020, format="%.5f", key="r2")
        qualite = st.selectbox("Qualité capture", ["Bonne - tout est lisible", "Moyenne - un peu flou", "Mauvaise - flou / petit"])
        if st.button("🧠 ANALYSER LA CAPTURE - 2 MIN + DOUBLE DXY", type="primary", use_container_width=True):
            api_key = None
            try: api_key = st.secrets.get("OPENAI_API_KEY", None)
            except Exception: pass
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key or OpenAI is None:
                st.warning("Pas de clé OpenAI. Utilise Mode SANS capture.")
            else:
                try:
                    mime = uploaded.type or "image/png"; encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8"); data_url = f"data:{mime};base64,{encoded}"
                    client = OpenAI(api_key=api_key)
                    prompt = f"""
Tu es un analyste PRO IQ Option. Actif : {actif}. BOUGIES 2 MIN. Expiration : {expiration} min (de 1 à 19). Support : {support2}. Résistance : {resistance2}.
DOUBLE FILTRE DXY : {alerte_dxy}
Qualité : {qualite}. Vu : RSI={voir_rsi}, WCCI={voir_wcci}, MACD={voir_macd}, ADX={voir_adx}, Bollinger={voir_boll}, EMA={voir_ema}.
Lis zone par zone : PRIX, BOUGIES 2 MIN, BOLLINGER, RSI, WCCI WOODIE (ne jamais inventer), MACD, ADX, EMA.
Si contradiction avec DXY -> ATTENDRE FORCÉ. Si ADX<20 -> ATTENDRE.
Donne : tableau lecture, contradictions, OÙ ENTRER, CONDITION, OBJECTIF, INVALIDATION, RISQUE, CONCLUSION CALL/PUT/ATTENDRE + score /12.
Ne garantis jamais un gain. Si illisible, dis ILLISIBLE.
"""
                    resp = client.responses.create(model=os.getenv("OPENAI_VISION_MODEL","gpt-5.5"), input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":data_url,"detail":"high"}]}])
                    st.markdown(resp.output_text)
                except Exception as e: st.error(f"Erreur IA : {e}")

# ================= MODE 3 =================
else:
    st.header(f"3. ENTRAÎNEMENT - {actif} - BOUGIES 2 MIN - Yahoo Finance")
    if actif in TICKER_YAHOO:
        if st.button("Analyser - Bougies 2 MIN"):
            data = yf.download(TICKER_YAHOO[actif], period="5d", interval="2m", progress=False, auto_adjust=False)
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            close = data["Close"]; prix_v = float(close.iloc[-1])
            ema9_v = float(close.ewm(span=9).mean().iloc[-1]); ema21_v = float(close.ewm(span=21).mean().iloc[-1])
            delta = close.diff(); gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
            rsi_v = float((100 - (100/(1+gain/loss.replace(0,np.nan)))).iloc[-1])
            wcci_v = float(calcul_wcci_woodie(data).iloc[-1])
            bb_mid_v = float(close.rolling(20).mean().iloc[-1]); bb_std = float(close.rolling(20).std(ddof=0).iloc[-1]); bb_up_v = bb_mid_v+2*bb_std; bb_low_v = bb_mid_v-2*bb_std
            macd_v, sig_v, hist_v = calcul_macd(close); adx_v, pdi_v, mdi_v = calcul_adx(data)
            o_v=float(data["Open"].iloc[-1]); h_v=float(data["High"].iloc[-1]); l_v=float(data["Low"].iloc[-1]); c_v=prix_v
            o_p=float(data["Open"].iloc[-2]); h_p=float(data["High"].iloc[-2]); l_p=float(data["Low"].iloc[-2]); c_p=float(data["Close"].iloc[-2])
            o_p2=float(data["Open"].iloc[-3]); c_p2=float(data["Close"].iloc[-3])
            patterns, ch_h, ch_b = analyse_chandelier_corrige(o_v, h_v, l_v, c_v, o_p, h_p, l_p, c_p, o_p2, c_p2)
            support_v=float(data["Low"].tail(30).min()); resistance_v=float(data["High"].tail(30).max())
            st.success(f"Prix : {prix_v:.5f} | RSI : {rsi_v:.1f} | WCCI : {wcci_v:.1f} | EMA9 : {ema9_v:.5f} | EMA21 : {ema21_v:.5f}")
            st.write(f"Bollinger : Haute {bb_up_v:.5f} / Moy {bb_mid_v:.5f} / Basse {bb_low_v:.5f}")
            st.write(f"MACD : {macd_v:.5f} | Hist {hist_v:.5f} | ADX : {adx_v:.1f} | +DI {pdi_v:.1f} | -DI {mdi_v:.1f}")
            st.write(f"WCCI : {interprete_wcci(wcci_v)} | 🕯️ : {', '.join(patterns)}")
            st.write(f"Support : {support_v:.5f} | Résistance : {resistance_v:.5f}")
            st.info("Recopie ces chiffres dans Mode SANS capture + ajoute CFO.")
    else:
        st.warning(f"{actif} n'existe pas sur Yahoo (OTC / Actions OTC). Utilise Mode SANS capture avec les vrais chiffres IQ Option en 2 MIN. C'est normal pour OTC.")

st.divider()
st.warning("⚠️ BOUGIES 2 MIN OBLIGATOIRE. Expiration 1-19 min au choix. Tous actifs IQ Option inclus. Outil d'analyse seulement. 2% max par trade, STOP après 3 pertes, JAMAIS de Martingale. Teste TOUJOURS en DÉMO.")
