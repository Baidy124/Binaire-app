import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

# --- SEUL AJOUT 1 : FLUX IQ ---
try:
    from iqoptionapi.stable_api import IQ_Option
    IQ_LIB = True
except ImportError:
    IQ_Option = None
    IQ_LIB = False

APP_TITLE = "IQ OPTION AI TRADER — MULTI AGENTS V1.0"
DB_PATH = Path("trading_journal.db")

st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")

# -----------------------------
# DATA + INDICATORS - JE NE TOUCHE RIEN
# -----------------------------
def normalize_ohlcv(df):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    aliases = {"datetime": "date", "timestamp": "date", "time": "date", "vol": "volume"}
    df = df.rename(columns=aliases)
    required = ["date", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Colonnes manquantes : " + ", ".join(missing))
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"])
    df = df.sort_values("date").drop_duplicates("date").set_index("date")
    return df[["open", "high", "low", "close", "volume"]]

def resample_ohlcv(df, rule):
    return df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna(subset=["open", "high", "low", "close"])

def add_indicators(df):
    x = df.copy()
    close, high, low = x["close"], x["high"], x["low"]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi"] = 100 - (100 / (1 + rs))
    typical = (high + low + close) / 3
    sma_tp = typical.rolling(14).mean()
    mean_dev = typical.rolling(14).apply(lambda a: np.mean(np.abs(a - np.mean(a))), raw=True)
    x["wcci"] = (typical - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))
    def _cfo_window(values):
        values = np.asarray(values, dtype=float)
        if len(values) < 2 or not np.isfinite(values).all():
            return np.nan
        xx = np.arange(len(values), dtype=float)
        slope, intercept = np.polyfit(xx, values, 1)
        fitted_last = intercept + slope * xx[-1]
        return 100 * (values[-1] - fitted_last) / values[-1] if values[-1] else np.nan
    x["cfo"] = close.rolling(14).apply(_cfo_window, raw=True)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    x["macd"] = ema12 - ema26
    x["macd_signal"] = x["macd"].ewm(span=9, adjust=False).mean()
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    x["bb_mid"] = mid
    x["bb_upper"] = mid + 2 * std
    x["bb_lower"] = mid - 2 * std
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    x["atr"] = tr.rolling(14).mean()
    x["atr_pct"] = 100 * x["atr"] / close
    x["ema20"] = close.ewm(span=20, adjust=False).mean()
    x["ema50"] = close.ewm(span=50, adjust=False).mean()
    return x

def candle_analysis(df):
    if len(df) < 3:
        return "Historique insuffisant", 0
    c = df.iloc[-1]
    body = abs(c.close - c.open)
    span = max(c.high - c.low, 1e-12)
    upper = c.high - max(c.open, c.close)
    lower = min(c.open, c.close) - c.low
    if body / span < 0.12:
        return "Doji / indécision", 0
    if lower > body * 2 and upper < body:
        return "Rejet haussier (mèche basse)", 1
    if upper > body * 2 and lower < body:
        return "Rejet baissier (mèche haute)", -1
    if c.close > c.open:
        return "Bougie haussière", 1
    return "Bougie baissière", -1

def support_resistance(df, lookback=60):
    sample = df.tail(lookback)
    if sample.empty:
        return np.nan, np.nan
    return float(sample["low"].min()), float(sample["high"].max())

def detect_false_breakout(df, level_window=20):
    if len(df) < level_window + 2:
        return "Données insuffisantes", 0
    prior = df.iloc[-level_window-1:-1]
    last = df.iloc[-1]
    resistance = prior["high"].max()
    support = prior["low"].min()
    if last["high"] > resistance and last["close"] < resistance:
        return "Possible fausse cassure haussière", -1
    if last["low"] < support and last["close"] > support:
        return "Possible fausse cassure baissière", 1
    return "Aucune fausse cassure détectée", 0

# -----------------------------
# AGENTS - JE NE TOUCHE RIEN
# -----------------------------
def agent_scanner(df):
    if len(df) < 60:
        return {"name": "SCANNER", "status": "WAIT", "detail": "60 bougies minimum recommandées"}
    last = df.iloc[-1]
    trend = "haussière" if last.ema20 > last.ema50 else "baissière"
    return {"name": "SCANNER", "status": "SCAN", "detail": f"Tendance courte : {trend}"}

def agent_technical(df):
    last = df.iloc[-1]
    score = 0
    notes = []
    if pd.notna(last.rsi):
        if last.rsi > 52: score += 1
        elif last.rsi < 48: score -= 1
        notes.append(f"RSI {last.rsi:.1f}")
    if pd.notna(last.wcci):
        if last.wcci > 25: score += 1
        elif last.wcci < -25: score -= 1
        notes.append(f"WCCI {last.wcci:.1f}")
    if pd.notna(last.cfo):
        if last.cfo > 0: score += 1
        elif last.cfo < 0: score -= 1
        notes.append(f"CFO {last.cfo:.3f}")
    if pd.notna(last.macd) and pd.notna(last.macd_signal):
        if last.macd > last.macd_signal: score += 1
        elif last.macd < last.macd_signal: score -= 1
        notes.append("MACD haussier" if last.macd > last.macd_signal else "MACD baissier")
    if last.close > last.bb_mid: score += 1
    elif last.close < last.bb_mid: score -= 1
    notes.append("Bollinger au-dessus de la médiane" if last.close > last.bb_mid else "Bollinger sous la médiane")
    return {"name": "TECHNICAL", "score": score, "detail": " • ".join(notes)}

def agent_patterns(df):
    pattern, score = candle_analysis(df)
    fake, fake_score = detect_false_breakout(df)
    return {"name": "PATTERN", "score": score + fake_score, "detail": f"{pattern} ; {fake}"}

def agent_mtf(raw):
    scores = []
    descriptions = []
    for label, rule in [("5 min", "5min"), ("15 min", "15min")]:
        tf = resample_ohlcv(raw, rule)
        if len(tf) < 25:
            descriptions.append(f"{label}: historique insuffisant")
            continue
        t = add_indicators(tf).iloc[-1]
        direction = 1 if t.ema20 > t.ema50 else -1
        scores.append(direction)
        descriptions.append(f"{label}: {'haussière' if direction > 0 else 'baissière'}")
    return {"name": "MULTI-TIMEFRAME", "score": int(np.sign(sum(scores))) if scores else 0, "detail": " ; ".join(descriptions)}

def agent_risk(df, max_atr_pct, max_spread_pct=0.0):
    last = df.iloc[-1]
    atr_pct = float(last.atr_pct) if pd.notna(last.atr_pct) else np.nan
    if not np.isfinite(atr_pct):
        return {"name": "RISK MANAGER", "pass": False, "detail": "ATR indisponible"}
    ok = atr_pct <= max_atr_pct
    detail = f"ATR {atr_pct:.3f}% — seuil {max_atr_pct:.3f}%"
    if not ok:
        detail += " — volatilité trop élevée"
    return {"name": "RISK MANAGER", "pass": ok, "detail": detail}

def make_decision(df, raw, max_atr_pct, min_score):
    scanner = agent_scanner(df)
    technical = agent_technical(df)
    patterns = agent_patterns(df)
    mtf = agent_mtf(raw)
    risk = agent_risk(df, max_atr_pct)
    components = [technical["score"], patterns["score"], mtf["score"]]
    total = int(sum(components))
    if not risk["pass"] or scanner["status"] == "WAIT":
        signal = "ATTENDRE"
    elif total >= min_score:
        signal = "HAUT"
    elif total <= -min_score:
        signal = "BAS"
    else:
        signal = "ATTENDRE"
    agents = [scanner, technical, patterns, mtf, risk]
    return signal, total, agents

# -----------------------------
# JOURNAL - JE NE TOUCHE RIEN
# -----------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, instrument TEXT, signal TEXT, score INTEGER, close REAL, decision TEXT, notes TEXT)""")

def save_signal(instrument, signal, score, close, decision, notes):
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("INSERT INTO signals(created_at,instrument,signal,score,close,decision,notes) VALUES(?,?,?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(), instrument, signal, int(score), float(close), decision, notes))

def read_journal():
    init_db()
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql_query("SELECT * FROM signals ORDER BY id DESC LIMIT 300", con)

# -----------------------------
# INTERFACE
# -----------------------------
st.title("📈 " + APP_TITLE)
st.caption("DXY • Multi-agents • Analyse assistée • Validation humaine obligatoire")

with st.sidebar:
    st.header("⚙️ Configuration")
    instrument = st.selectbox("Instrument", ["DXY / Dollar Index", "EUR/USD OTC", "GBP/USD OTC", "EUR/JPY OTC"])
    candle_rule = st.selectbox("Unité principale", ["2min", "1min", "5min"], index=0)
    max_atr_pct = st.slider("ATR maximum (%) — filtre volatilité", 0.01, 1.50, 0.35, 0.01)
    min_score = st.slider("Score minimum de décision", 2, 8, 4)
    # --- SEUL AJOUT 2 : EXPIRATION 1 A 19 ---
    expiration = st.slider("Expiration (mn)", 1, 19, 2)
    st.divider()
    # --- SEUL AJOUT 1 : CHOIX FLUX ---
    st.header("📡 FLUX")
    source_flux = st.radio("Choisir le flux :", ["🟡 Yahoo Finance", "🔴 Flux IQ Option", "📁 CSV"], index=0)
    iq_api = None
    iq_connecte = False
    if source_flux.startswith("🔴"):
        st.subheader("🔴 Connexion IQ DEMO")
        if not IQ_LIB:
            st.error("Mets dans requirements.txt : iqoptionapi")
        else:
            iq_email = st.text_input("Email IQ DEMO")
            iq_mdp = st.text_input("Mot de passe DEMO", type="password")
            if st.button("🔌 Connecter au flux IQ"):
                try:
                    iq_api = IQ_Option(iq_email, iq_mdp)
                    check, reason = iq_api.connect()
                    if check:
                        iq_api.change_balance("PRACTICE")
                        st.session_state["iq_api"] = iq_api
                        st.success("✅ Connecte - Flux IQ")
                    else:
                        st.error(f"Echec : {reason}")
                except Exception as e:
                    st.error(f"Erreur : {e}")
            if "iq_api" in st.session_state and st.session_state["iq_api"] is not None:
                iq_api = st.session_state["iq_api"]
                try:
                    if iq_api.check_connect():
                        iq_connecte = True
                        st.success("✅ Flux IQ deja connecte")
                except Exception:
                    pass
    st.divider()
    st.warning("Mode semi-automatique : aucune connexion ni exécution d'ordre IQ Option dans cette version.")

tab1, tab2, tab3 = st.tabs(["🏠 Terminal", "📚 Journal", "ℹ️ Guide"])

with tab1:
    st.subheader("1. Source des cotations")
    st.caption(f"Expiration choisie : **{expiration} mn** | Flux : **{source_flux}**")
    source_col1, source_col2 = st.columns([1, 1])
    with source_col1:
        uploaded = st.file_uploader("Importer un CSV de bougies", type=["csv"])
        st.caption("Colonnes attendues : Date, Open, High, Low, Close, Volume (Volume facultatif).")
    with source_col2:
        st.markdown("**Source expérimentale Yahoo Finance / Flux IQ**")
        st.caption("Vérifie toujours sur le graphique du broker.")
        fetch = st.button("Récupérer les données", use_container_width=True)

    raw = None
    source_name = "Aucune source chargée"
    if uploaded is not None:
        try:
            raw = normalize_ohlcv(pd.read_csv(uploaded))
            source_name = "CSV importé"
        except Exception as e:
            st.error(f"CSV invalide : {e}")

    if fetch:
        # --- FLUX IQ ---
        if source_flux.startswith("🔴"):
            if iq_connecte and iq_api is not None:
                try:
                    code_iq = "EURUSD-OTC" if "OTC" in instrument else "EURUSD"
                    if "GBP" in instrument: code_iq = "GBPUSD-OTC" if "OTC" in instrument else "GBPUSD"
                    if "EUR/JPY" in instrument: code_iq = "EURJPY-OTC" if "OTC" in instrument else "EURJPY"
                    iq_api.start_candles_stream(code_iq, 60, 200)
                    time.sleep(1)
                    candles = iq_api.get_realtime_candles(code_iq, 60)
                    iq_api.stop_candles_stream(code_iq, 60)
                    rows = []
                    for ts in sorted(candles.keys()):
                        c = candles[ts]
                        rows.append({"Date": pd.to_datetime(ts, unit="s", utc=True), "Open": c["open"], "High": c["max"], "Low": c["min"], "Close": c["close"], "Volume": 0})
                    raw = normalize_ohlcv(pd.DataFrame(rows))
                    source_name = "IQ OPTION - VRAI PRIX"
                    st.session_state["fetched_raw"] = raw
                    st.session_state["fetched_source"] = source_name
                except Exception as e:
                    st.error(f"Erreur flux IQ : {e}")
            else:
                st.warning("Pas connecte au flux IQ. Connecte-toi a gauche ou choisis Yahoo.")
        else:
            try:
                import yfinance as yf
                with st.spinner("Récupération expérimentale des données..."):
                    y = yf.download("DX-Y.NYB", period="5d", interval="1m", auto_adjust=False, progress=False)
                    if y is None or y.empty:
                        raise ValueError("Yahoo Finance n'a retourné aucune donnée.")
                    if isinstance(y.columns, pd.MultiIndex):
                        y.columns = y.columns.get_level_values(0)
                    y = y.reset_index()
                    raw = normalize_ohlcv(y)
                    source_name = "Yahoo Finance — non garanti temps réel"
                    st.session_state["fetched_raw"] = raw
                    st.session_state["fetched_source"] = source_name
            except Exception as e:
                st.error(f"Récupération impossible : {e}")

    if raw is None and "fetched_raw" in st.session_state and uploaded is None:
        raw = st.session_state["fetched_raw"]
        source_name = st.session_state.get("fetched_source", "Source externe")

    if raw is None or len(raw) < 30:
        st.info("Charge un CSV contenant au moins 30 bougies, ou essaie la récupération expérimentale.")
        st.stop()

    candles = resample_ohlcv(raw, candle_rule)
    if len(candles) < 30:
        st.warning("Pas assez de bougies après conversion. Importe davantage d'historique.")
        st.stop()
    data = add_indicators(candles)
    latest = data.iloc[-1]
    signal, score, agents = make_decision(data, raw, max_atr_pct, min_score)

    st.caption(f"Source : {source_name} | Dernière bougie : {data.index[-1].strftime('%Y-%m-%d %H:%M:%S UTC')} | {len(data)} bougies | Expiration : {expiration} mn")
    if len(data) >= 2:
        age_min = (datetime.now(timezone.utc) - data.index[-1].to_pydatetime()).total_seconds() / 60
        if age_min > 5:
            st.warning(f"Données anciennes : dernière bougie datant d'environ {age_min:.0f} minutes. Ne pas utiliser comme signal en direct.")
        else:
            st.success("Horodatage récent selon la source importée — cela ne garantit pas une cotation IQ Option identique.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Dernier cours", f"{latest.close:.4f}")
    m2.metric("RSI (14)", f"{latest.rsi:.1f}" if pd.notna(latest.rsi) else "N/D")
    m3.metric("ATR (%)", f"{latest.atr_pct:.3f}%" if pd.notna(latest.atr_pct) else "N/D")
    m4.metric("Score agents", f"{score:+d}")

    st.divider()
    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("2. Décision collective")
        if signal == "HAUT":
            st.success(f"PROPOSITION : HAUT - {expiration} mn")
        elif signal == "BAS":
            st.error(f"PROPOSITION : BAS - {expiration} mn")
        else:
            st.warning("PROPOSITION : ATTENDRE")
        st.write(f"Score agrégé : **{score:+d}** | Seuil : **±{min_score}**")
        st.caption("Ce score est une règle technique expérimentale, pas une probabilité de gain.")
        st.subheader("3. Agents")
        for a in agents:
            if a["name"] == "RISK MANAGER":
                status = "PASS" if a["pass"] else "BLOCK"
                st.write(f"**{a['name']} — {status}**")
            elif a["name"] == "SCANNER":
                st.write(f"**{a['name']} — {a['status']}**")
            else:
                st.write(f"**{a['name']} — score {a.get('score', 0):+d}**")
            st.caption(a["detail"])
    with right:
        st.subheader("4. Validation humaine")
        st.write("Le robot propose une direction. Tu décides si tu souhaites retenir le signal.")
        st.metric("Cours observé", f"{latest.close:.4f}")
        st.metric("Dernière clôture", data.index[-1].strftime("%H:%M:%S UTC"))
        note = st.text_input("Note facultative", placeholder="Ex. confirmation observée sur IQ Option")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Accepter / enregistrer", use_container_width=True, disabled=(signal == "ATTENDRE")):
                save_signal(instrument, signal, score, latest.close, "ACCEPTE_PAR_UTILISATEUR", " | ".join(a["detail"] for a in agents) + " | " + note + f" | Expiration {expiration}mn")
                st.success("Signal enregistré comme accepté. Aucun ordre n'a été envoyé.")
        with c2:
            if st.button("⛔ Refuser / enregistrer", use_container_width=True):
                save_signal(instrument, signal, score, latest.close, "REFUSE_PAR_UTILISATEUR", " | ".join(a["detail"] for a in agents) + " | " + note + f" | Expiration {expiration}mn")
                st.info("Signal refusé et enregistré.")
    st.divider()
    st.subheader("5. Graphique et indicateurs")
    chart = data[["close", "bb_upper", "bb_mid", "bb_lower", "ema20", "ema50"]].tail(150)
    st.line_chart(chart)
    st.dataframe(data.tail(12).reset_index(), use_container_width=True)

with tab2:
    st.subheader("Historique des décisions")
    journal = read_journal()
    if journal.empty:
        st.info("Aucune décision enregistrée pour le moment.")
    else:
        st.dataframe(journal, use_container_width=True, hide_index=True)
        accepted = int((journal["decision"] == "ACCEPTE_PAR_UTILISATEUR").sum())
        refused = int((journal["decision"] == "REFUSE_PAR_UTILISATEUR").sum())
        a, b, c = st.columns(3)
        a.metric("Décisions enregistrées", len(journal))
        b.metric("Acceptées", accepted)
        c.metric("Refusées", refused)
        st.caption("Le journal enregistre les décisions, pas les résultats gagnants/perdants. Il faudra renseigner les résultats après expiration pour calculer un taux de réussite réel.")

with tab3:
    st.subheader("Guide de démarrage")
    st.markdown("""
1. Exporte ou prépare un fichier CSV de bougies avec les colonnes `Date, Open, High, Low, Close` et éventuellement `Volume`.
2. Importe le CSV dans l'onglet Terminal.
3. Vérifie la source, l'heure de la dernière bougie et la cohérence avec ton graphique IQ Option.
4. Lis les avis des agents et la proposition HAUT / BAS / ATTENDRE.
5. Compare toujours le signal avec le graphique réel avant de l'accepter.
6. Enregistre ta décision. Après expiration, ajoute le résultat dans une future version du journal.
""")

st.caption("V1.0 — Prototype d'analyse et de validation humaine. Tester d'abord en compte démo.")
