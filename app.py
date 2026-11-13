
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

st.set_page_config(page_title="IQ OPTION AI TRADER V6.2 - PRO+", page_icon="📈", layout="wide")
st.title("📈 IQ OPTION AI TRADER V6.2 - PRO+")
st.caption("WCCI Woodie + Chandeliers corrigés + Capture PRO + Gestion Risque + ATTENDRE si contradiction | 1 à 19 min")

# ================= PAIRES =================
PAIRES_IQ_OPTION = [
    "Dollar Index (DXY)",
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "NZD/USD", "USD/CAD",
    "EUR/JPY", "GBP/JPY", "AUD/JPY", "EUR/AUD", "GBP/AUD", "AUD/CAD",
    "EUR/CAD", "GBP/CAD", "AUD/CHF", "EUR/CHF", "GBP/CHF", "CAD/CHF",
    "EUR/NZD", "GBP/NZD", "AUD/NZD", "EUR/THB", "NZD/CAD", "NZD/CHF",
    "NZD/JPY", "CAD/JPY", "CHF/JPY", "NOK/JPY", "JPY/THB", "EUR/GBP",
    "USD/MXN", "USD/BRL", "USD/ZAR", "USD/TRY", "USD/THB", "USD/NOK",
    "USD/SEK", "USD/SGD", "USD/HKD", "USD/COP", "PEN/USD",
    "EUR/ZAR", "GBP/ZAR", "EUR/SGD"
]
TICKER_YAHOO = {
    "Dollar Index (DXY)": "DX-Y.NYB",
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X",
    "USD/CAD": "USDCAD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "AUD/JPY": "AUDJPY=X", "USD/BRL": "USDBRL=X",
    "USD/MXN": "USDMXN=X", "USD/ZAR": "USDZAR=X",
}

# ================= SESSION RISQUE =================
if "risk_journal" not in st.session_state:
    st.session_state.risk_journal = []  # liste dict {date, actif, signal, resultat}
if "risk_blocked" not in st.session_state:
    st.session_state.risk_blocked = False

# ================= SIDEBAR =================
st.sidebar.header("⚙️ Paramètres")
actif = st.sidebar.selectbox("1. Choisir la paire", PAIRES_IQ_OPTION, index=1)
expiration = st.sidebar.slider("2. Expiration (minutes)", 1, 19, 5)
mode = st.sidebar.radio("3. Mode", ["SANS capture - Je tape les chiffres", "AVEC capture - Photo graphique", "ENTRAÎNEMENT - Yahoo Finance"])

# ================= GESTION DU RISQUE - SIDEBAR =================
st.sidebar.divider()
st.sidebar.header("🛡️ Gestion du Risque")
capital = st.sidebar.number_input("Ton capital démo / réel ($)", value=100.0, min_value=10.0, step=10.0)
risque_pct = st.sidebar.slider("Risque par trade %", 1, 5, 2)
mise_conseillee = capital * risque_pct / 100
st.sidebar.write(f"💰 Mise conseillée : **${mise_conseillee:.2f}** par trade ( {risque_pct}% de ${capital:.0f} )")
st.sidebar.caption("Règle d'or : Jamais plus de 2% par trade. Jamais de Martingale.")

# Calcul pertes
today = str(date.today())
journal_today = [x for x in st.session_state.risk_journal if x.get("date") == today]
pertes_today = sum(1 for x in journal_today if x.get("resultat") == "PERTE")
gains_today = sum(1 for x in journal_today if x.get("resultat") == "GAIN")
# 3 pertes d'affilée ?
pertes_consecutives = 0
for x in reversed(st.session_state.risk_journal):
    if x.get("resultat") == "PERTE":
        pertes_consecutives += 1
    elif x.get("resultat") == "GAIN":
        break
    else:
        break

# BLOCAGES
blocage_raison = None
if pertes_consecutives >= 3:
    blocage_raison = f"🚫 BLOCAGE : 3 pertes d'affilée ({pertes_consecutives}). STOP 30 min. Va marcher, reviens plus tard."
elif pertes_today >= 5:
    blocage_raison = f"🚫 BLOCAGE JOURNALIER : {pertes_today} pertes aujourd'hui. ARRÊTE pour aujourd'hui. Demain c'est un autre jour."
elif gains_today >= 5 and pertes_today == 0:
    blocage_raison = None

if blocage_raison:
    st.sidebar.error(blocage_raison)
    st.error(blocage_raison)
    st.warning("L'app est bloquée pour te protéger. Tu peux débloquer manuellement ci-dessous si tu es en DÉMO et calme, mais c'est déconseillé.")
    if st.button("🔓 Je comprends le risque, débloquer pour la démo (1 trade)"):
        st.session_state.risk_journal = st.session_state.risk_journal[:-3] if len(st.session_state.risk_journal) >= 3 else []
        st.rerun()
else:
    st.sidebar.success(f"Aujourd'hui : ✅ {gains_today} gains | ❌ {pertes_today} pertes | Série pertes : {pertes_consecutives}")

# Journal affichage
with st.sidebar.expander("📓 Mon journal du jour"):
    if not journal_today:
        st.write("Aucun trade noté aujourd'hui.")
    else:
        for j in reversed(journal_today[-10:]):
            st.write(f"{j['heure']} - {j['actif']} - {j['signal']} → {j['resultat']}")

# ================= FILTRE DXY =================
st.sidebar.divider()
st.sidebar.subheader("💵 Filtre Dollar Index (DXY)")
dxy_tendance = st.sidebar.selectbox("Tendance DXY :", ["Je ne sais pas", "DXY monte - Dollar FORT", "DXY descend - Dollar FAIBLE", "DXY neutre / range"])
def filtre_dxy(actif_choisi, dxy):
    usd_en_deuxieme = ["EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "EUR/GBP"]
    usd_en_premier = ["USD/JPY", "USD/CHF", "USD/CAD", "USD/MXN", "USD/BRL", "USD/ZAR", "USD/TRY", "USD/THB", "USD/NOK", "USD/SEK", "USD/SGD", "USD/HKD", "USD/COP"]
    if actif_choisi == "Dollar Index (DXY)": return None
    if dxy in ["Je ne sais pas", "DXY neutre / range"]: return None
    if dxy == "DXY monte - Dollar FORT":
        if actif_choisi in usd_en_deuxieme: return "⚠️ DXY FORT → Paire risque de BAISSER. Privilégie PUT."
        if actif_choisi in usd_en_premier: return "✅ DXY FORT confirme : Paire risque de MONTER. Privilégie CALL."
        return "⚠️ DXY monte = Dollar FORT."
    if dxy == "DXY descend - Dollar FAIBLE":
        if actif_choisi in usd_en_deuxieme: return "✅ DXY FAIBLE confirme : Paire risque de MONTER. Privilégie CALL."
        if actif_choisi in usd_en_premier: return "⚠️ DXY FAIBLE → Paire risque de BAISSER. Privilégie PUT."
        return "⚠️ DXY descend = Dollar FAIBLE."
    return None
alerte_dxy = filtre_dxy(actif, dxy_tendance)
if alerte_dxy:
    st.info(alerte_dxy)

# ================= 1. WCCI WOODIE COHÉRENT =================
def calcul_wcci_woodie(df, period=14):
    """
    Vrai WCCI Woodie comme sur IQ Option :
    - Typical Price = (H+L+C)/3
    - SMA 14 sur Typical Price
    - Mean Deviation avec moyenne, pas EMA
    - CCI = (TP - SMA) / (0.015 * MeanDev)
    - Seuils Woodie : +100 / -100 surachat/survente, 0 = ligne zéro
    """
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    sma = tp.rolling(period).mean()
    # Mean Deviation : moyenne des écarts absolus par rapport à SMA
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    wcci = (tp - sma) / (0.015 * md.replace(0, np.nan))
    return wcci

def interprete_wcci(wcci_val):
    if wcci_val > 200: return "🔴 WCCI > 200 = SURACHAT EXTRÊME, retournement baissier probable"
    if wcci_val > 100: return "🟠 WCCI > 100 = Surachat, attention aux CALL"
    if wcci_val < -200: return "🟢 WCCI < -200 = SURVENTE EXTRÊME, retournement haussier probable"
    if wcci_val < -100: return "🟡 WCCI < -100 = Survente, attention aux PUT"
    if wcci_val > 0: return "WCCI > 0 = Momentum haussier"
    return "WCCI < 0 = Momentum baissier"

def calcul_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return float(macd.iloc[-1]), float(signal.iloc[-1]), float(hist.iloc[-1])

def calcul_adx(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return float(adx.iloc[-1]), float(plus_di.iloc[-1]), float(minus_di.iloc[-1])

# ================= 2. CHANDELIERS CORRIGÉS =================
def analyse_chandelier_corrige(o, h, l, c, o_prev, h_prev, l_prev, c_prev, o_prev2=None, c_prev2=None):
    """
    Détection corrigée avec ratios réels.
    corps = |C-O|, range = H-L, meche_haut, meche_bas
    """
    patterns = []
    score_hausse = 0
    score_baisse = 0
    corps = abs(c - o)
    rng = h - l if h != l else 0.00001
    meche_haut = h - max(o, c)
    meche_bas = min(o, c) - l
    corps_prev = abs(c_prev - o_prev)
    rng_prev = h_prev - l_prev if h_prev != l_prev else 0.00001
    est_verte = c > o
    est_rouge = c < o
    est_verte_prev = c_prev > o_prev
    est_rouge_prev = c_prev < o_prev

    # --- DOJI : corps < 10% du range ---
    if corps < rng * 0.10:
        if meche_haut > rng*0.4 and meche_bas > rng*0.4:
            patterns.append("➖ Doji Longue Jambe (grosse indécision)")
        else:
            patterns.append("➖ Doji (indécision - ATTENDRE)")
        # Doji = neutre, pas de score

    # --- MARTEAU : meche_bas > 2x corps, meche_haut < 0.3x corps, corps dans tiers haut ---
    if meche_bas > corps * 2 and meche_haut < corps * 0.5 and min(o,c) > l + rng*0.6:
        if est_rouge_prev or c_prev < o_prev:
            patterns.append("🔨 Marteau Haussier (rejet bas après baisse - CALL à étudier)")
            score_hausse += 2
        else:
            patterns.append("🔨 Marteau (rejet bas)")

    # --- ÉTOILE FILANTE / MARTEAU INVERSÉ ---
    if meche_haut > corps * 2 and meche_bas < corps * 0.5 and max(o,c) < h - rng*0.6:
        if est_verte_prev:
            patterns.append("⭐ Étoile Filante (rejet haut après hausse - PUT à étudier)")
            score_baisse += 2
        else:
            patterns.append("⭐ Marteau Inversé (rejet haut)")

    # --- ENGLOBANTE : corps actuel englobe totalement corps précédent + sens opposé ---
    if est_rouge_prev and est_verte and o < c_prev and c > o_prev and corps > corps_prev * 1.1:
        patterns.append("🟢 Englobante Haussière FORTE (retournement haussier)")
        score_hausse += 2
    if est_verte_prev and est_rouge and o > c_prev and c < o_prev and corps > corps_prev * 1.1:
        patterns.append("🔴 Englobante Baissière FORTE (retournement baissier)")
        score_baisse += 2

    # --- HARAMI : corps actuel dans corps précédent ---
    if est_rouge_prev and est_verte and o > c_prev and c < o_prev:
        patterns.append("🟡 Harami Haussier (affaiblissement baisse)")
        score_hausse += 1
    if est_verte_prev and est_rouge and o < c_prev and c > o_prev:
        patterns.append("🟡 Harami Baissier (affaiblissement hausse)")
        score_baisse += 1

    # --- PÉNÉTRANTE / COUVERTURE NUAGE NOIR ---
    if est_rouge_prev and est_verte and c > (o_prev + c_prev)/2 and c < o_prev:
        patterns.append("🟢 Pénétrante Haussière")
        score_hausse += 1
    if est_verte_prev and est_rouge and c < (o_prev + c_prev)/2 and c > o_prev:
        patterns.append("🔴 Couverture en Nuage Noir (baissier)")
        score_baisse += 1

    # --- 3 SOLDATS / 3 CORBEAUX (si 3 bougies données) ---
    if o_prev2 is not None and c_prev2 is not None:
        if c_prev2 > o_prev2 and c_prev > o_prev and est_verte:
            patterns.append("🟢 3 Soldats Blancs (tendance haussière forte)")
            score_hausse += 2
        if c_prev2 < o_prev2 and c_prev < o_prev and est_rouge:
            patterns.append("🔴 3 Corbeaux Noirs (tendance baissière forte)")
            score_baisse += 2

    # --- CLÔTURE PROCHE EXTREMES ---
    if c > h - rng*0.10 and est_verte:
        patterns.append("⬆️ Clôture proche du haut (acheteurs forts)")
        score_hausse += 1
    if c < l + rng*0.10 and est_rouge:
        patterns.append("⬇️ Clôture proche du bas (vendeurs forts)")
        score_baisse += 1

    if not patterns:
        patterns.append("Bougie normale - aucune figure spéciale")

    return patterns, score_hausse, score_baisse

# ================= 5. DÉCISION ATTENDRE SI CONTRADICTION =================
def decision_pro(bull, bear, macd_hist, adx, plus_di, minus_di, rsi, wcci, prix, bb_up, bb_low, dxy_alerte):
    """
    Règle ATTENDRE forcée si contradiction :
    - RSI haussier mais MACD baissier = contradiction
    - ADX < 20 = pas de tendance = ATTENDRE
    - Prix entre Bollinger mais WCCI extrême opposé = contradiction
    - DXY contredit le signal = ATTENDRE ou signal faible
    """
    contradictions = []
    # 1. RSI vs MACD
    if rsi > 55 and macd_hist < 0:
        contradictions.append("RSI haussier (>55) mais MACD baissier = contradiction")
    if rsi < 45 and macd_hist > 0:
        contradictions.append("RSI baissier (<45) mais MACD haussier = contradiction")
    # 2. ADX faible
    if adx < 20:
        contradictions.append(f"ADX {adx:.1f} < 20 = pas de tendance, range")
    # 3. DI croisés faibles
    if abs(plus_di - minus_di) < 3:
        contradictions.append("+DI et -DI trop proches = indécision")
    # 4. WCCI extrême contre tendance
    if bull >= 6 and wcci < -100:
        contradictions.append("Signal haussier mais WCCI < -100 survente = contradiction")
    if bear >= 6 and wcci > 100:
        contradictions.append("Signal baissier mais WCCI > 100 surachat = contradiction")
    # 5. Bull et Bear proches
    if abs(bull - bear) <= 1:
        contradictions.append(f"Score trop serré : Hausse {bull} vs Baisse {bear}")

    return contradictions

def donner_position_v62(bull, bear, prix, support, resistance, bb_up, bb_low, bb_mid, bougie, macd_hist, adx, plus_di, minus_di, patterns, rsi, wcci, ch_hausse, ch_baisse):
    contradictions = decision_pro(bull, bear, macd_hist, adx, plus_di, minus_di, rsi, wcci, prix, bb_up, bb_low, alerte_dxy)
    # Ajoute score chandeliers
    bull_total = bull + ch_hausse
    bear_total = bear + ch_baisse

    # FORCÉ ATTENDRE si contradiction majeure ou ADX faible
    if len(contradictions) >= 2 or adx < 18:
        return {
            "signal": f"🟡 ATTENDRE FORCÉ sur {actif} - {len(contradictions)} contradiction(s)", "type": "warning",
            "entree": "NE PAS ENTRER",
            "condition": f"Attendre que ADX > 20 et que les indicateurs s'alignent. Support {support:.5f} / Résistance {resistance:.5f}",
            "objectif": "Pas d'objectif",
            "invalidation": "Pas de signal valide",
            "conseil": f"Contradictions : {'; '.join(contradictions)}",
            "contradictions": contradictions, "bull": bull_total, "bear": bear_total
        }
    if bull_total >= 7 and bougie == "Verte" and not contradictions:
        return {"signal": f"🟢 CALL FORT sur {actif} ({bull_total}/12)", "type": "success",
                "entree": f"Autour de {prix:.5f}", "condition": f"Entrée après rejet sur {bb_low:.5f} ou Support {support:.5f}",
                "objectif": f"{resistance:.5f} / Bollinger Haute {bb_up:.5f}", "invalidation": f"Casse Support {support:.5f}",
                "conseil": f"Expiration {expiration} min. Mise conseillée ${mise_conseillee:.2f}", "contradictions": [], "bull": bull_total, "bear": bear_total}
    if bear_total >= 7 and bougie == "Rouge" and not contradictions:
        return {"signal": f"🔴 PUT FORT sur {actif} ({bear_total}/12)", "type": "error",
                "entree": f"Autour de {prix:.5f}", "condition": f"Entrée après rejet sur {bb_up:.5f} ou Résistance {resistance:.5f}",
                "objectif": f"{support:.5f} / Bollinger Basse {bb_low:.5f}", "invalidation": f"Casse Résistance {resistance:.5f}",
                "conseil": f"Expiration {expiration} min. Mise conseillée ${mise_conseillee:.2f}", "contradictions": [], "bull": bull_total, "bear": bear_total}
    return {"signal": f"🟡 ATTENDRE sur {actif} - Hausse {bull_total}/12 | Baisse {bear_total}/12", "type": "warning",
            "entree": "NE PAS ENTRER", "condition": f"Attendre Support {support:.5f} OU Résistance {resistance:.5f} + confirmation",
            "objectif": "Pas d'objectif", "invalidation": "Pas de signal",
            "conseil": f"Contradictions : {'; '.join(contradictions) if contradictions else 'Score insuffisant'}", "contradictions": contradictions, "bull": bull_total, "bear": bear_total}

def afficher_position(pos, actif_nom):
    if pos["type"] == "success": st.success(pos["signal"])
    elif pos["type"] == "error": st.error(pos["signal"])
    else: st.warning(pos["signal"])
    st.write(f"**📍 ENTRÉE :** {pos['entree']}")
    st.write(f"**🎯 CONDITION :** {pos['condition']}")
    st.write(f"**🏁 OBJECTIF :** {pos['objectif']}")
    st.write(f"**❌ INVALIDATION :** {pos['invalidation']}")
    st.write(f"**💡 CONSEIL :** {pos['conseil']}")
    if pos.get("contradictions"):
        st.error(f"⚠️ CONTRADICTIONS DÉTECTÉES : {'; '.join(pos['contradictions'])}")
    if alerte_dxy: st.write(f"**💵 DXY :** {alerte_dxy}")
    # Boutons journal
    c1, c2, c3 = st.columns(3)
    if c1.button("✅ J'ai GAGNÉ ce trade", key=f"win_{actif_nom}_{datetime.now().timestamp()}"):
        st.session_state.risk_journal.append({"date": today, "heure": datetime.now().strftime("%H:%M"), "actif": actif_nom, "signal": pos["signal"], "resultat": "GAIN"})
        st.rerun()
    if c2.button("❌ J'ai PERDU ce trade", key=f"lose_{actif_nom}_{datetime.now().timestamp()}"):
        st.session_state.risk_journal.append({"date": today, "heure": datetime.now().strftime("%H:%M"), "actif": actif_nom, "signal": pos["signal"], "resultat": "PERTE"})
        st.rerun()
    if c3.button("⏭️ Je n'ai PAS pris ce trade"):
        st.info("Bien joué, ne pas trader c'est aussi trader.")

# ================= MODE 1 : SANS CAPTURE =================
if mode.startswith("SANS"):
    if blocage_raison:
        st.stop()
    st.header(f"1. SANS capture - {actif} - {expiration} min - V6.2 PRO+")
    st.write("Graphique IQ Option 2 min : RSI 14, WCCI Woodie 14, CFO 14, Bollinger 20,2, EMA 9/21, MACD 12,26,9, ADX 14")
    st.info(f"💰 Mise conseillée : ${mise_conseillee:.2f} | Capital ${capital:.0f} | Risque {risque_pct}% | Série pertes : {pertes_consecutives}/3")
    c1, c2, c3, c4 = st.columns(4)
    rsi = c1.number_input("RSI 14", value=50.0, min_value=0.0, max_value=100.0)
    cfo_val = c2.number_input("CFO 14", value=0.0, format="%.3f")
    wcci_val = c3.number_input("WCCI Woodie 14 (IQ Option)", value=0.0, format="%.1f")
    adx_val = c4.number_input("ADX 14", value=20.0, min_value=0.0, max_value=100.0)
    c5, c6, c7, c8 = st.columns(4)
    macd_val = c5.number_input("MACD Hist", value=0.0, format="%.5f")
    di_plus = c6.number_input("+DI", value=20.0)
    di_minus = c7.number_input("-DI", value=20.0)
    prix = c8.number_input("Prix actuel", value=1.10950, format="%.5f")
    c9, c10, c11 = st.columns(3)
    ema9 = c9.number_input("EMA 9", value=1.10950, format="%.5f")
    ema21 = c10.number_input("EMA 21", value=1.10940, format="%.5f")
    bougie = c11.selectbox("Dernière bougie 2 min", ["Verte", "Rouge"])
    b1, b2, b3, b4, b5 = st.columns(5)
    bb_up = b1.number_input("Bollinger Haute", value=1.11000, format="%.5f")
    bb_mid = b2.number_input("Bollinger Moyenne", value=1.10950, format="%.5f")
    bb_low = b3.number_input("Bollinger Basse", value=1.10900, format="%.5f")
    support = b4.number_input("Support", value=1.10880, format="%.5f")
    resistance = b5.number_input("Résistance", value=1.11020, format="%.5f")
    st.subheader("🕯️ Chandeliers - 3 dernières bougies (corrigé)")
    st.caption("Pour détecter Englobante, Harami, 3 Soldats, etc. il faut 2-3 bougies.")
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
        st.write(f"**🕯️ Chandeliers détectés :** {', '.join(patterns)} | Score chandelier Hausse +{ch_h} / Baisse +{ch_b}")
        st.write(f"**WCCI Woodie :** {interprete_wcci(wcci_val)}")
        bullish = {"EMA 9 > EMA 21": ema9 > ema21, "RSI > 50": rsi > 50, "CFO > 0": cfo_val > 0, "WCCI > 0": wcci_val > 0, "Prix > BB Moyenne": prix > bb_mid, "Bougie Verte": bougie=="Verte", "MACD Hist > 0": macd_val > 0, "ADX > 20 + +DI > -DI": adx_val > 20 and di_plus > di_minus, "Prix > BB Basse": prix > bb_low, "WCCI pas surachat extrême": wcci_val < 200}
        bearish = {"EMA 9 < EMA 21": ema9 < ema21, "RSI < 50": rsi < 50, "CFO < 0": cfo_val < 0, "WCCI < 0": wcci_val < 0, "Prix < BB Moyenne": prix < bb_mid, "Bougie Rouge": bougie=="Rouge", "MACD Hist < 0": macd_val < 0, "ADX > 20 + -DI > +DI": adx_val > 20 and di_minus > di_plus, "Prix < BB Haute": prix < bb_up, "WCCI pas survente extrême": wcci_val > -200}
        pos = donner_position_v62(sum(bullish.values()), sum(bearish.values()), prix, support, resistance, bb_up, bb_low, bb_mid, bougie, macd_val, adx_val, di_plus, di_minus, patterns, rsi, wcci_val, ch_h, ch_b)
        afficher_position(pos, actif)
        col1, col2 = st.columns(2)
        with col1: st.write("**✅ Haussiers :**", bullish)
        with col2: st.write("**🔴 Baissiers :**", bearish)

# ================= MODE 2 : AVEC CAPTURE AMÉLIORÉE =================
elif mode.startswith("AVEC"):
    if blocage_raison:
        st.stop()
    st.header(f"2. AVEC capture - {actif} - {expiration} min - Lecture PRO")
    st.warning("📸 POUR UNE BONNE LECTURE : 1. Mets IQ Option en plein écran 2. Zoom pour voir RSI + WCCI + MACD + ADX 3. Pas de doigt sur l'écran 4. Lumière normale, pas de reflet")
    uploaded = st.file_uploader("Ta capture IQ Option", type=["png","jpg","jpeg","webp"])
    if uploaded:
        st.image(uploaded, caption="Ta capture", use_container_width=True)
        # Checklist lecture
        st.subheader("✅ Coche ce que tu vois VRAIMENT sur ta capture")
        colA, colB, colC = st.columns(3)
        voir_rsi = colA.checkbox("Je vois RSI", value=True)
        voir_wcci = colA.checkbox("Je vois WCCI", value=True)
        voir_macd = colB.checkbox("Je vois MACD", value=False)
        voir_adx = colB.checkbox("Je vois ADX", value=False)
        voir_boll = colC.checkbox("Je vois Bollinger", value=True)
        voir_ema = colC.checkbox("Je vois EMA 9/21", value=True)
        colD, colE = st.columns(2)
        support2 = colD.number_input("Support visible", value=1.10880, format="%.5f", key="s2")
        resistance2 = colE.number_input("Résistance visible", value=1.11020, format="%.5f", key="r2")
        qualite = st.selectbox("Qualité de ta capture", ["Bonne - tout est lisible", "Moyenne - un peu flou", "Mauvaise - flou / petit"])
        if st.button("🧠 ANALYSER LA CAPTURE - LECTURE PRO", type="primary", use_container_width=True):
            api_key = None
            try: api_key = st.secrets.get("OPENAI_API_KEY", None)
            except Exception: pass
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key or OpenAI is None:
                st.warning("Pas de clé OpenAI. Utilise le Mode SANS capture, c'est plus fiable.")
            else:
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"
                    client = OpenAI(api_key=api_key)
                    prompt = f"""
Tu es un analyste technique PRO qui lit des captures IQ Option. Tu DOIS être honnête sur ce que tu vois.
Actif : {actif}. Bougies 2 min. Expiration : {expiration} min. Support utilisateur : {support2}. Résistance : {resistance2}.
Qualité déclarée : {qualite}.
L'utilisateur dit voir : RSI={voir_rsi}, WCCI={voir_wcci}, MACD={voir_macd}, ADX={voir_adx}, Bollinger={voir_boll}, EMA={voir_ema}.
Filtre DXY : {dxy_tendance}. Alerte : {alerte_dxy if alerte_dxy else 'Aucune'}.

MÉTHODE DE LECTURE OBLIGATOIRE - Lis zone par zone :
ZONE 1 - PRIX : Quel est le prix actuel EXACT si lisible ? Sinon dis ILLISIBLE.
ZONE 2 - BOUGIES : 3 dernières bougies : vertes ou rouges ? Figures : marteau, doji, englobante, harami, étoile filante ? Si tu n'es pas sûr, dis INCERTAIN.
ZONE 3 - BOLLINGER : Prix touche bande haute / basse / milieu ? Squeeze ou élargissement ?
ZONE 4 - RSI : Valeur exacte si lisible, sinon ILLISIBLE. Surachat >70 ? Survente <30 ?
ZONE 5 - WCCI WOODIE : Valeur exacte si lisible. >100 surachat ? <-100 survente ? >200 extrême ? N'invente JAMAIS une valeur WCCI.
ZONE 6 - MACD : Si visible, au-dessus ou sous signal ? Histogramme grandit ou rétrécit ? Si pas visible, dis NON VISIBLE.
ZONE 7 - ADX : Si visible, valeur ? >25 forte tendance ? <20 range ? Si pas visible, dis NON VISIBLE.
ZONE 8 - EMA 9/21 : Laquelle est au-dessus ?

DÉCISION :
- Si 2 contradictions ou plus (ex RSI haussier mais MACD baissier, ou ADX <20) → CONCLUSION OBLIGATOIRE : ATTENDRE
- Si WCCI >200 ou <-200 + prix sur Bollinger extrême → Attention retournement
- Si une zone est ILLISIBLE, dis-le et baisse ta confiance.

Réponds en français avec :
1. Tableau de lecture zone par zone avec Confiance : HAUTE / MOYENNE / ILLISIBLE
2. Contradictions détectées (liste)
3. OÙ PRENDRE POSITION : prix ou NE PAS ENTRER
4. CONDITION, OBJECTIF, INVALIDATION
5. GESTION RISQUE : Mise conseillée, ne pas trader si 3 pertes d'affilée
6. CONCLUSION : CALL FORT / PUT FORT / ATTENDRE FORCÉ + score /12
7. Qualité de lecture : /10 et ce qu'il faut améliorer sur la prochaine capture.

RÈGLE D'OR : Mieux vaut dire ILLISIBLE que d'inventer un chiffre. Ne garantis jamais un gain.
"""
                    resp = client.responses.create(model=os.getenv("OPENAI_VISION_MODEL","gpt-5.5"), input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":data_url,"detail":"high"}]}])
                    st.markdown(resp.output_text)
                except Exception as e:
                    st.error(f"Erreur IA : {e}")

# ================= MODE 3 : ENTRAÎNEMENT =================
else:
    st.header(f"3. ENTRAÎNEMENT - {actif} - Yahoo Finance - V6.2 PRO+")
    if actif in TICKER_YAHOO:
        if st.button("Analyser - Tous indicateurs corrigés"):
            data = yf.download(TICKER_YAHOO[actif], period="5d", interval="2m", progress=False, auto_adjust=False)
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            close = data["Close"]
            prix_v = float(close.iloc[-1])
            ema9_v = float(close.ewm(span=9).mean().iloc[-1])
            ema21_v = float(close.ewm(span=21).mean().iloc[-1])
            delta = close.diff()
            gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
            loss = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
            rsi_v = float((100 - (100/(1+gain/loss.replace(0,np.nan)))).iloc[-1])
            # WCCI Woodie corrigé
            wcci_series = calcul_wcci_woodie(data)
            wcci_v = float(wcci_series.iloc[-1])
            bb_mid_v = float(close.rolling(20).mean().iloc[-1])
            bb_std = float(close.rolling(20).std(ddof=0).iloc[-1])
            bb_up_v = bb_mid_v + 2*bb_std
            bb_low_v = bb_mid_v - 2*bb_std
            macd_v, sig_v, hist_v = calcul_macd(close)
            adx_v, pdi_v, mdi_v = calcul_adx(data)
            o_v = float(data["Open"].iloc[-1]); h_v = float(data["High"].iloc[-1]); l_v = float(data["Low"].iloc[-1]); c_v = prix_v
            o_p = float(data["Open"].iloc[-2]); h_p = float(data["High"].iloc[-2]); l_p = float(data["Low"].iloc[-2]); c_p = float(data["Close"].iloc[-2])
            o_p2 = float(data["Open"].iloc[-3]); c_p2 = float(data["Close"].iloc[-3])
            patterns, ch_h, ch_b = analyse_chandelier_corrige(o_v, h_v, l_v, c_v, o_p, h_p, l_p, c_p, o_p2, c_p2)
            support_v = float(data["Low"].tail(30).min()); resistance_v = float(data["High"].tail(30).max())
            st.success(f"Prix : {prix_v:.5f} | RSI : {rsi_v:.1f} | WCCI Woodie : {wcci_v:.1f} | EMA9 : {ema9_v:.5f} | EMA21 : {ema21_v:.5f}")
            st.write(f"**Bollinger :** Haute {bb_up_v:.5f} / Moy {bb_mid_v:.5f} / Basse {bb_low_v:.5f}")
            st.write(f"**MACD :** {macd_v:.5f} | Signal {sig_v:.5f} | Hist {hist_v:.5f}")
            st.write(f"**ADX :** {adx_v:.1f} | +DI {pdi_v:.1f} | -DI {mdi_v:.1f} → {'FORTE' if adx_v>25 else 'FAIBLE / Range' if adx_v<20 else 'Modérée'}")
            st.write(f"**WCCI :** {interprete_wcci(wcci_v)}")
            st.write(f"**🕯️ Chandeliers :** {', '.join(patterns)}")
            st.write(f"Support : {support_v:.5f} | Résistance : {resistance_v:.5f}")
            st.info("Recopie ces chiffres dans le Mode SANS capture + ajoute CFO pour avoir ta position PRO+.")
    else:
        st.warning("Cette paire n'existe pas sur Yahoo Finance. Utilise le Mode SANS capture.")

st.divider()
st.warning("⚠️ Outil d'analyse seulement. Même avec 12/12, tu peux perdre. Règle : 2% max par trade, STOP après 3 pertes, JAMAIS de Martingale. Teste TOUJOURS en DÉMO.")
