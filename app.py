import os
import base64
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

st.set_page_config(page_title="IQ OPTION AI TRADER V8.1 - BINAIRE + CFD", page_icon="📈", layout="wide")
st.title("📈 IQ OPTION AI TRADER V8.1 - BINAIRE + CFD")
st.caption("Binaire 1-19 min + CFD | DXY Auto | Capture | Paper Trading avec P/L | Pas d'exécution réelle")

# ================= 1. LISTES =================
PAIRES = [
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
TICKER = {
    "Dollar Index (DXY)": "DX-Y.NYB",
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "USD/CHF": "USDCHF=X", "AUD/USD": "AUDUSD=X", "NZD/USD": "NZDUSD=X",
    "USD/CAD": "USDCAD=X", "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X", "AUD/JPY": "AUDJPY=X", "USD/BRL": "USDBRL=X",
    "USD/MXN": "USDMXN=X", "USD/ZAR": "USDZAR=X",
}

def decimals_for(a):
    if a == "Dollar Index (DXY)": return 2
    if "JPY" in a: return 3
    if a in ["USD/MXN","USD/BRL","USD/ZAR","USD/TRY","USD/THB","USD/NOK","USD/SEK"]: return 4
    return 5
def fmt(p, a): return f"{p:.{decimals_for(a)}f}"
def prix_defaut(a):
    if a == "Dollar Index (DXY)": return 104.50
    if a == "USD/JPY": return 150.250
    if a in ["EUR/JPY","GBP/JPY"]: return 162.500
    if a == "USD/MXN": return 17.2500
    if a == "USD/BRL": return 5.0500
    if a == "USD/ZAR": return 18.5000
    if "JPY" in a: return 150.000
    return 1.10950

# ================= 2. DXY AUTO =================
@st.cache_data(ttl=60, show_spinner=False)
def get_dxy_auto():
    try:
        d = yf.download("DX-Y.NYB", period="1d", interval="5m", progress=False, auto_adjust=False)
        if d is None or d.empty: return None, "Je ne sais pas"
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        close = pd.to_numeric(d["Close"], errors="coerce").dropna()
        if len(close) < 22: return None, "Je ne sais pas"
        prix = float(close.iloc[-1]); e9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1]); e21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        if prix > e9 > e21: t = "DXY monte - Dollar FORT"
        elif prix < e9 < e21: t = "DXY descend - Dollar FAIBLE"
        else: t = "DXY neutre / range"
        return prix, t
    except Exception: return None, "Je ne sais pas"

# ================= 3. PAPER BROKER AVEC P/L - CORRIGÉ =================
class PaperBroker:
    def __init__(self):
        if "balance" not in st.session_state: st.session_state.balance = 1000.0
        if "positions" not in st.session_state: st.session_state.positions = []
        if "history" not in st.session_state: st.session_state.history = []
    def open_trade(self, actif, type_trade, mode_trade, entree, mise, expiration, stop=None, target=None):
        # Binaire : on ne sait le résultat qu'à l'expiration, on le met en attente
        # CFD : on suit le prix, on peut fermer manuellement
        pos = {"id": len(st.session_state.positions)+len(st.session_state.history)+1, "heure": datetime.now().strftime("%H:%M"), "actif": actif, "type": type_trade, "mode": mode_trade, "entree": entree, "mise": mise, "expiration": expiration, "stop": stop, "target": target, "statut": "OUVERTE"}
        st.session_state.positions.append(pos)
        return pos
    def close_trade(self, pos_id, prix_sortie, resultat_manuel=None):
        for i, p in enumerate(st.session_state.positions):
            if p["id"] == pos_id:
                # Calcul P/L
                if p["mode"] == "BINAIRE":
                    # Binaire : si tu gagnes, tu gagnes ~80% de ta mise. Si tu perds, tu perds ta mise.
                    # Tu dois dire si c'est gagné ou perdu, car on n'a pas le prix live IQ Option
                    if resultat_manuel == "GAGNÉ":
                        pl = p["mise"] * 0.80
                    elif resultat_manuel == "PERDU":
                        pl = -p["mise"]
                    else:
                        pl = 0
                else:
                    # CFD simplifié : 1 point = 1$ pour 0.01 lot - pour t'entraîner seulement
                    # BUY : (sortie - entrée) * 10000 * mise/100
                    # SELL : inverse
                    diff = (prix_sortie - p["entree"]) if p["type"] == "BUY" else (p["entree"] - prix_sortie)
                    pl = diff * 10000 * (p["mise"]/100)
                st.session_state.balance += pl
                p["sortie"] = prix_sortie; p["pl"] = round(pl, 2); p["statut"] = "FERMÉE"
                st.session_state.history.append(p)
                del st.session_state.positions[i]
                return pl
        return 0

broker = PaperBroker()

# ================= 4. SIDEBAR =================
st.sidebar.header("⚙️ Paramètres")
# NOUVEAU : Choix Binaire ou CFD en premier
type_trading = st.sidebar.radio("Type de trading :", ["🔵 BINAIRE (1-19 min)", "🟠 CFD (BUY / SELL)"])
actif = st.sidebar.selectbox("Paire", PAIRES, index=1)
if type_trading.startswith("🔵"):
    expiration = st.sidebar.slider("Expiration Binaire (minutes)", 1, 19, 5)
    mise = st.sidebar.number_input("Mise binaire ($)", value=10.0, min_value=1.0, step=1.0)
else:
    expiration = None
    mise = st.sidebar.number_input("Mise CFD ($ - pour calcul P/L démo)", value=100.0, min_value=10.0, step=10.0)

mode_saisie = st.sidebar.radio("Saisie :", ["SANS capture - Je tape", "AVEC capture - Photo", "ENTRAÎNEMENT - Yahoo"])

st.sidebar.divider()
st.sidebar.subheader("💵 Filtre DXY")
dxy_auto = st.sidebar.checkbox("DXY automatique", value=True)
if dxy_auto:
    dxy_prix, dxy_tendance = get_dxy_auto()
    if dxy_prix is not None: st.sidebar.success(f"DXY : {dxy_prix:.2f} - {dxy_tendance}")
    else:
        st.sidebar.warning("DXY auto indisponible")
        dxy_tendance = st.sidebar.selectbox("DXY manuel :", ["Je ne sais pas","DXY monte - Dollar FORT","DXY descend - Dollar FAIBLE","DXY neutre / range"])
else:
    dxy_tendance = st.sidebar.selectbox("DXY manuel :", ["Je ne sais pas","DXY monte - Dollar FORT","DXY descend - Dollar FAIBLE","DXY neutre / range"])

def filtre_dxy(a, dxy):
    usd_second = ["EUR/USD","GBP/USD","AUD/USD","NZD/USD","PEN/USD"]
    usd_first = ["USD/JPY","USD/CHF","USD/CAD","USD/MXN","USD/BRL","USD/ZAR","USD/TRY","USD/THB","USD/NOK","USD/SEK","USD/SGD","USD/HKD","USD/COP"]
    if a == "Dollar Index (DXY)": return None, 0
    if dxy in ["Je ne sais pas","DXY neutre / range"]: return None, 0
    if dxy == "DXY monte - Dollar FORT":
        if a in usd_second: return "⚠️ DXY FORT → Paire risque de BAISSER. Privilégie PUT / SELL.", -1
        if a in usd_first: return "✅ DXY FORT → Paire risque de MONTER. Privilégie CALL / BUY.", +1
        return "ℹ️ Paire sans USD direct. DXY a moins d'impact.", 0
    if dxy == "DXY descend - Dollar FAIBLE":
        if a in usd_second: return "✅ DXY FAIBLE → Paire risque de MONTER. Privilégie CALL / BUY.", +1
        if a in usd_first: return "⚠️ DXY FAIBLE → Paire risque de BAISSER. Privilégie PUT / SELL.", -1
        return "ℹ️ Paire sans USD direct. DXY a moins d'impact.", 0
    return None, 0

alerte_dxy, biais_dxy = filtre_dxy(actif, dxy_tendance)
if alerte_dxy: st.info(f"💵 {alerte_dxy}")

# ================= 5. FONCTION ANALYSE COMMUNE =================
def analyser(bull, bear, prix, support, resistance, bb_up, bb_low, bougie, biais, type_trading):
    # Signal de base
    signal = None
    if bull >= 5 and bougie == "Verte": signal = "HAUSSE"
    elif bear >= 5 and bougie == "Rouge": signal = "BAISSE"
    # Conflit DXY
    conflit = False
    if signal == "HAUSSE" and biais == -1: conflit = True
    if signal == "BAISSE" and biais == +1: conflit = True
    if conflit:
        return {"titre": f"🚫 CONFLIT DXY sur {actif} - NE PAS ENTRER", "type": "conflit", "signal": None,
                "entree": prix, "stop": support if signal=="HAUSSE" else resistance, "target": resistance if signal=="HAUSSE" else support,
                "detail": f"Ton signal dit {signal} mais DXY dit le contraire. Tu trades contre le Dollar."}
    if signal == "HAUSSE":
        qual = "⭐⭐⭐ Fort (6/6)" if bull==6 else "⭐⭐ Moyen (5/6)"
        if type_trading.startswith("🔵"):
            return {"titre": f"🟢 CALL - HAUSSE sur {actif} - {qual}", "type": "CALL", "signal": "CALL",
                    "entree": prix, "stop": support, "target": resistance,
                    "detail": f"Entrée autour de {fmt(prix, actif)} | Idéal : attendre retour vers {fmt(bb_low, actif)} ou support {fmt(support, actif)} puis bougie verte | Objectif {fmt(resistance, actif)} | Annulé si casse {fmt(support, actif)} | Expiration {expiration} min | Mise {mise}$"}
        else:
            return {"titre": f"🟢 BUY - HAUSSE sur {actif} - {qual}", "type": "BUY", "signal": "BUY",
                    "entree": prix, "stop": support, "target": resistance,
                    "detail": f"Entrée BUY autour de {fmt(prix, actif)} | Stop illustratif : {fmt(support, actif)} | Target : {fmt(resistance, actif)} / Bollinger Haute {fmt(bb_up, actif)} | Annulé si casse support"}
    if signal == "BAISSE":
        qual = "⭐⭐⭐ Fort (6/6)" if bear==6 else "⭐⭐ Moyen (5/6)"
        if type_trading.startswith("🔵"):
            return {"titre": f"🔴 PUT - BAISSE sur {actif} - {qual}", "type": "PUT", "signal": "PUT",
                    "entree": prix, "stop": resistance, "target": support,
                    "detail": f"Entrée autour de {fmt(prix, actif)} | Idéal : attendre remontée vers {fmt(bb_up, actif)} ou résistance {fmt(resistance, actif)} puis bougie rouge | Objectif {fmt(support, actif)} | Annulé si casse {fmt(resistance, actif)} | Expiration {expiration} min | Mise {mise}$"}
        else:
            return {"titre": f"🔴 SELL - BAISSE sur {actif} - {qual}", "type": "SELL", "signal": "SELL",
                    "entree": prix, "stop": resistance, "target": support,
                    "detail": f"Entrée SELL autour de {fmt(prix, actif)} | Stop illustratif : {fmt(resistance, actif)} | Target : {fmt(support, actif)} / Bollinger Basse {fmt(bb_low, actif)} | Annulé si casse résistance"}
    return {"titre": f"🟡 ATTENDRE sur {actif} - Hausse {bull}/6 | Baisse {bear}/6", "type": "WAIT", "signal": None,
            "entree": prix, "stop": support, "target": resistance,
            "detail": f"Attendre prix touche Support {fmt(support, actif)} OU Résistance {fmt(resistance, actif)} avec confirmation. Ne force pas."}

def afficher_resultat(res):
    if res["type"] in ["CALL","BUY"]: st.success(res["titre"])
    elif res["type"] in ["PUT","SELL"]: st.error(res["titre"])
    elif res["type"] == "conflit": st.error(res["titre"])
    else: st.warning(res["titre"])
    st.write(res["detail"])
    if alerte_dxy: st.write(f"**💵 DXY :** {alerte_dxy}")
    st.write(f"**📍 Entrée :** {fmt(res['entree'], actif)} | **🛑 Stop :** {fmt(res['stop'], actif)} | **🎯 Target :** {fmt(res['target'], actif)}")
    return res

# ================= 6. MODES DE SAISIE =================
resultat = None
if mode_saisie.startswith("SANS"):
    st.header(f"SANS capture - {actif} - {type_trading}")
    st.write("Graphique IQ Option en 2 min : RSI 14, CFO 14, WCCI/CCI 14, Bollinger 20,2, EMA 9/21")
    dec = decimals_for(actif); fmt_str = f"%.{dec}f"; p_def = prix_defaut(actif)
    c1,c2,c3 = st.columns(3)
    rsi = c1.number_input("RSI 14", value=50.0, min_value=0.0, max_value=100.0, key=f"rsi_{actif}")
    cfo_val = c2.number_input("CFO 14", value=0.0, format="%.3f", key=f"cfo_{actif}")
    wcci_val = c3.number_input("WCCI / CCI 14", value=0.0, format="%.1f", key=f"wcci_{actif}")
    c4,c5,c6 = st.columns(3)
    prix = c4.number_input("Prix actuel", value=p_def, format=fmt_str, key=f"prix_{actif}")
    ema9 = c5.number_input("EMA 9", value=p_def, format=fmt_str, key=f"ema9_{actif}")
    ema21 = c6.number_input("EMA 21", value=p_def, format=fmt_str, key=f"ema21_{actif}")
    b1,b2,b3,b4,b5 = st.columns(5)
    bb_up = b1.number_input("Bollinger Haute", value=p_def, format=fmt_str, key=f"bbu_{actif}")
    bb_mid = b2.number_input("Bollinger Moyenne", value=p_def, format=fmt_str, key=f"bbm_{actif}")
    bb_low = b3.number_input("Bollinger Basse", value=p_def, format=fmt_str, key=f"bbl_{actif}")
    support = b4.number_input("Support", value=p_def, format=fmt_str, key=f"sup_{actif}")
    resistance = b5.number_input("Résistance", value=p_def, format=fmt_str, key=f"res_{actif}")
    bougie = st.selectbox("Dernière bougie 2 min", ["Verte","Rouge"], key=f"bougie_{actif}")
    if st.button("🔎 ANALYSER - OÙ JE PRENDS POSITION ?", type="primary", use_container_width=True):
        bullish = {"EMA 9 > EMA 21": ema9>ema21, "RSI > 50": rsi>50, "CFO > 0": cfo_val>0, "WCCI > 0": wcci_val>0, "Prix > BB Moy": prix>bb_mid, "Bougie Verte": bougie=="Verte"}
        bearish = {"EMA 9 < EMA 21": ema9<ema21, "RSI < 50": rsi<50, "CFO < 0": cfo_val<0, "WCCI < 0": wcci_val<0, "Prix < BB Moy": prix<bb_mid, "Bougie Rouge": bougie=="Rouge"}
        res = analyser(sum(bullish.values()), sum(bearish.values()), prix, support, resistance, bb_up, bb_low, bougie, biais_dxy, type_trading)
        resultat = afficher_resultat(res)
        st.session_state.last_res = res
        st.write("Hausse", bullish); st.write("Baisse", bearish)
        st.progress(max(sum(bullish.values()), sum(bearish.values()))/6)

elif mode_saisie.startswith("AVEC"):
    st.header(f"AVEC capture - {actif} - {type_trading}")
    uploaded = st.file_uploader("Ta capture IQ Option", type=["png","jpg","jpeg","webp"])
    if uploaded:
        st.image(uploaded, caption="Ta capture", use_container_width=True)
        dec = decimals_for(actif); fmt_str = f"%.{dec}f"; p_def = prix_defaut(actif)
        colA,colB = st.columns(2)
        support2 = colA.number_input("Support visible", value=p_def, format=fmt_str, key="s2")
        resistance2 = colB.number_input("Résistance visible", value=p_def, format=fmt_str, key="r2")
        if st.button("🧠 ANALYSER LA CAPTURE", type="primary", use_container_width=True):
            api_key = None
            try: api_key = st.secrets.get("OPENAI_API_KEY", None)
            except Exception: pass
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key or OpenAI is None:
                st.warning("Pas de clé OpenAI. Utilise le Mode SANS capture.")
            else:
                try:
                    mime = uploaded.type or "image/png"
                    encoded = base64.b64encode(uploaded.getvalue()).decode("utf-8")
                    data_url = f"data:{mime};base64,{encoded}"
                    client = OpenAI(api_key=api_key)
                    prompt = f"""Tu es un analyste prudent. Analyse UNIQUEMENT ce qui est visible sur cette capture IQ Option.
Actif : {actif}. Type : {type_trading}. Bougies 2 min. Expiration Binaire : {expiration} min. Support : {support2}. Résistance : {resistance2}.
Filtre DXY : {dxy_tendance}. Alerte : {alerte_dxy if alerte_dxy else 'Aucune'}. Biais DXY : {biais_dxy}.
Si le signal va CONTRE le biais DXY, dis CONFLIT DXY - NE PAS ENTRER.
Réponds en français : 1. Ce que tu vois vraiment 2. Tendance 3. OÙ PRENDRE POSITION : {'CALL / PUT' if 'BINAIRE' in type_trading else 'BUY / SELL'} 4. CONDITION 5. OBJECTIF 6. STOP / INVALIDATION 7. Prise en compte DXY 8. CONCLUSION 9. Si illisible, dis-le, n'invente rien. Ne garantis jamais un gain."""
                    resp = client.responses.create(model=os.getenv("OPENAI_VISION_MODEL","gpt-5.5"), input=[{"role":"user","content":[{"type":"input_text","text":prompt},{"type":"input_image","image_url":data_url,"detail":"high"}]}])
                    st.markdown(resp.output_text)
                except Exception as e: st.error(f"Erreur IA : {e}")

else:
    st.header(f"ENTRAÎNEMENT - {actif} - Yahoo (pas IQ Option OTC)")
    if actif in TICKER:
        if st.button("Analyser pour t'entraîner"):
            try:
                data = yf.download(TICKER[actif], period="5d", interval="2m", progress=False, auto_adjust=False)
                if data is None or data.empty: st.error("Yahoo n'a pas renvoyé de données.")
                else:
                    if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
                    close = pd.to_numeric(data["Close"], errors="coerce").dropna()
                    prix_v = float(close.iloc[-1]); ema9_v = float(close.ewm(span=9, adjust=False).mean().iloc[-1]); ema21_v = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
                    delta = close.diff(); gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss = -delta.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
                    rsi_v = float((100 - (100/(1+gain/loss.replace(0,np.nan)))).iloc[-1])
                    bb_mid_v = float(close.rolling(20).mean().iloc[-1]); bb_up_v = bb_mid_v + 2*float(close.rolling(20).std(ddof=0).iloc[-1]); bb_low_v = bb_mid_v - 2*float(close.rolling(20).std(ddof=0).iloc[-1])
                    support_v = float(data["Low"].tail(30).min()); resistance_v = float(data["High"].tail(30).max())
                    bougie_v = "Verte" if float(close.iloc[-1]) > float(close.iloc[-2]) else "Rouge"
                    # Pour entraînement, on met CFO/WCCI à 0 et on laisse l'utilisateur les compléter, mais on montre le calcul de base
                    st.success(f"Prix : {fmt(prix_v, actif)} | RSI : {rsi_v:.1f} | EMA9 : {fmt(ema9_v, actif)} | EMA21 : {fmt(ema21_v, actif)} | Bougie : {bougie_v}")
                    st.write(f"Bollinger : {fmt(bb_up_v, actif)} / {fmt(bb_mid_v, actif)} / {fmt(bb_low_v, actif)}")
                    st.write(f"Support récent : {fmt(support_v, actif)} | Résistance récente : {fmt(resistance_v, actif)}")
                    st.info("Recopie ces chiffres dans Mode SANS capture + CFO et WCCI pour avoir ta position complète.")
            except Exception as e: st.error(f"Erreur Yahoo : {e}")
    else:
        st.warning("Paire pas sur Yahoo. Utilise Mode SANS capture avec vrais chiffres IQ Option.")

# ================= 7. PAPER TRADING =================
st.divider()
st.subheader("📓 Paper Trading - Faux argent seulement - Pas d'exécution réelle")
st.write(f"💰 Balance démo : **{st.session_state.balance:.2f} $** | Positions ouvertes : {len(st.session_state.positions)} | Historique : {len(st.session_state.history)}")
if "last_res" in st.session_state and st.session_state.last_res is not None:
    lr = st.session_state.last_res
    if lr["signal"] is not None:
        if st.button(f"📝 Ouvrir un trade démo : {lr['type']} {actif} à {fmt(lr['entree'], actif)}", type="primary"):
            broker.open_trade(actif, lr["type"], "BINAIRE" if "BINAIRE" in type_trading else "CFD", lr["entree"], mise, expiration, stop=lr["stop"], target=lr["target"])
            st.success("Trade démo ouvert ! Va en bas pour le fermer.")
            st.rerun()

if st.session_state.positions:
    st.write("**Positions ouvertes :**")
    for p in st.session_state.positions:
        c1,c2,c3,c4 = st.columns([3,2,2,2])
        c1.write(f"#{p['id']} {p['actif']} {p['type']} {p['mode']} - Entrée {fmt(p['entree'], p['actif'])} - Mise {p['mise']}$")
        if p["mode"] == "BINAIRE":
            res = c2.selectbox(f"Résultat #{p['id']}", ["GAGNÉ","PERDU"], key=f"res_{p['id']}")
            if c3.button(f"Fermer #{p['id']}", key=f"close_{p['id']}"):
                pl = broker.close_trade(p["id"], p["entree"], resultat_manuel=res)
                st.success(f"Fermé : P/L {pl:.2f} $")
                st.rerun()
        else:
            prix_sortie = c2.number_input(f"Prix sortie #{p['id']}", value=p["entree"], format=f"%.{decimals_for(p['actif'])}f", key=f"sortie_{p['id']}")
            if c3.button(f"Fermer #{p['id']}", key=f"close_{p['id']}"):
                pl = broker.close_trade(p["id"], prix_sortie)
                st.success(f"Fermé : P/L {pl:.2f} $")
                st.rerun()
        c4.write(f"Stop {fmt(p['stop'], p['actif'])} | Target {fmt(p['target'], p['actif'])}")

if st.session_state.history:
    st.write("**Historique :**")
    df = pd.DataFrame(st.session_state.history)
    # Calcul total
    total_pl = df["pl"].sum() if "pl" in df.columns else 0
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.write(f"**P/L total démo : {total_pl:.2f} $**")
    if st.button("Réinitialiser balance démo à 1000$"):
        st.session_state.balance = 1000.0; st.session_state.positions = []; st.session_state.history = []
        st.rerun()

st.divider()
st.warning("⚠️ Outil d'analyse + démo seulement. Yahoo ≠ IQ Option OTC. Aucune exécution réelle. Même avec DXY + 6/6, tu peux perdre. Teste TOUJOURS en DÉMO. Risque max 2% par trade. Ce n'est pas un conseil d'investissement.")
