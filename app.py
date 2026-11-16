# -*- coding: utf-8 -*-
"""
IQ OPTION AI TRADER V8.6 PRO — analyse uniquement

Installation:
    pip install streamlit yfinance pandas numpy plotly

Option OTCharts (facultatif):
    pip install otcharts
    Définir OTCHARTS_API_KEY dans l'environnement ou dans .streamlit/secrets.toml
    [otcharts]
    api_key = "VOTRE_CLE"

Lancer:
    streamlit run iq_option_ai_trader_v86.py

IMPORTANT:
- Le programme n'envoie aucun ordre et ne se connecte pas pour trader.
- OTCharts est un fournisseur tiers indépendant, pas une API officielle IQ Option.
- Le DXY n'est pas nécessairement disponible dans le catalogue IQ Option d'OTCharts.
- Yahoo Finance est une source externe : ses prix peuvent différer du graphique IQ Option.
- Les signaux sont des règles indicatives, pas des garanties ni des conseils financiers.
"""

import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import yfinance as yf

# --------------------------- CONFIGURATION ---------------------------

st.set_page_config(
    page_title="IQ OPTION AI TRADER V8.6 PRO",
    page_icon="📈",
    layout="wide"
)

st.title("📈 IQ OPTION AI TRADER V8.6 PRO")
st.caption("Analyse technique en lecture seule — aucun ordre n'est exécuté.")

DEFAULT_SYMBOL = "^DXY"
TIMEFRAME_MINUTES = 2
MAX_CANDLES = 500

# --------------------------- OUTILS GÉNÉRAUX ---------------------------

def get_secret(name, default=None):
    """Lit une valeur depuis Streamlit secrets ou les variables d'environnement."""
    try:
        value = st.secrets.get(name, default)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, default)

def normalize_ohlcv(raw):
    """Convertit les réponses OTCharts/Yahoo en DataFrame OHLCV standard."""
    if raw is None:
        raise ValueError("Aucune donnée reçue.")

    if isinstance(raw, pd.DataFrame):
        df = raw.copy()
    elif isinstance(raw, list):
        df = pd.DataFrame(raw)
    elif isinstance(raw, dict):
        if "candles" in raw:
            df = pd.DataFrame(raw["candles"])
        elif "data" in raw:
            df = pd.DataFrame(raw["data"])
        else:
            df = pd.DataFrame(raw)
    else:
        raise TypeError(f"Format de données non reconnu : {type(raw).__name__}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(c[0]) for c in df.columns]
    df.columns = [str(c).strip().lower() for c in df.columns]

    aliases = {
        "open": ["open", "o", "opening_price"],
        "high": ["high", "h", "max"],
        "low": ["low", "l", "min"],
        "close": ["close", "c", "price", "closing_price"],
        "volume": ["volume", "vol", "v"],
        "time": ["time", "timestamp", "date", "datetime", "from"],
    }

    rename = {}
    for standard, choices in aliases.items():
        for col in choices:
            if col in df.columns:
                rename[col] = standard
                break
    df = df.rename(columns=rename)

    if "time" in df.columns:
        ts = pd.to_datetime(df.pop("time"), unit="s", utc=True, errors="coerce")
        if ts.notna().sum() == 0:
            ts = pd.to_datetime(raw["time"], utc=True, errors="coerce")
        df.index = ts
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
    elif df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Colonnes OHLC manquantes : " + ", ".join(missing))

    if "volume" not in df.columns:
        df["volume"] = np.nan

    for col in required + ["volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[~df.index.isna()].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df.dropna(subset=required)
    return df[["open", "high", "low", "close", "volume"]].tail(MAX_CANDLES)

# --------------------------- DONNÉES YAHOO ---------------------------

@st.cache_data(ttl=25, show_spinner=False)
def load_yahoo(symbol, period="5d", interval="2m"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=False)
    if df.empty:
        raise ValueError("Yahoo Finance n'a renvoyé aucune bougie.")
    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume"
    })
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return normalize_ohlcv(df)

# --------------------------- DONNÉES OTCHARTS ---------------------------

def create_otcharts_client():
    """
    Connexion facultative. La signature du constructeur peut varier selon
    la version du paquet OTCharts installée : en cas d'échec, le message
    d'erreur est affiché et Yahoo reste une source distincte.
    """
    try:
        from otcharts import Client as OTChartsClient
    except ImportError as exc:
        raise RuntimeError(
            "Le paquet 'otcharts' n'est pas installé. "
            "Installe-le avec : pip install otcharts"
        ) from exc

    api_key = get_secret("OTCHARTS_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("otcharts", {}).get("api_key")
        except Exception:
            api_key = None

    try:
        if api_key:
            return OTChartsClient(api_key=api_key)
        return OTChartsClient()
    except TypeError:
        return OTChartsClient()

def get_otcharts_symbols(client):
    symbols = client.symbols("iq")
    if isinstance(symbols, pd.DataFrame):
        return symbols.to_dict("records")
    if isinstance(symbols, dict):
        return symbols.get("symbols", symbols.get("data", list(symbols.values())))
    return list(symbols)

def symbol_label(item):
    if isinstance(item, dict):
        sym = item.get("symbol") or item.get("id") or item.get("name")
        name = item.get("name") or item.get("description") or sym
        return str(sym), str(name)
    return str(item), str(item)

def fetch_otcharts_candles(symbol):
    client = create_otcharts_client()
    raw = client.candles("iq", symbol, tf=120, limit=MAX_CANDLES)
    df = normalize_ohlcv(raw)
    return df, "OTCharts / IQ Option", symbol

# --------------------------- INDICATEURS ---------------------------

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_indicators(df):
    d = df.copy()
    c, h, l = d["close"], d["high"], d["low"]
    d["rsi"] = calculate_rsi(c, 14)
    typical = (h + l + c) / 3
    mean = typical.rolling(20).mean()
    mad = typical.rolling(20).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    d["wcci"] = (typical - mean) / (0.015 * mad.replace(0, np.nan))
    x = np.arange(14, dtype=float)
    def cfo_window(values):
        if len(values) < 14 or np.isnan(values).any():
            return np.nan
        slope, intercept = np.polyfit(x, values, 1)
        forecast = intercept + slope * 14
        return ((values[-1] - forecast) / values[-1]) * 100 if values[-1] else np.nan
    d["cfo"] = c.rolling(14).apply(cfo_window, raw=True)
    d["macd"] = ema(c, 12) - ema(c, 26)
    d["macd_signal"] = ema(d["macd"], 9)
    d["macd_hist"] = d["macd"] - d["macd_signal"]
    d["bb_mid"] = c.rolling(20).mean()
    std = c.rolling(20).std()
    d["bb_upper"] = d["bb_mid"] + 2 * std
    d["bb_lower"] = d["bb_mid"] - 2 * std
    d["bb_width"] = (d["bb_upper"] - d["bb_lower"]) / d["bb_mid"] * 100
    tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
    span_a = (tenkan + kijun) / 2
    span_b = (h.rolling(52).max() + l.rolling(52).min()) / 2
    d["tenkan"] = tenkan
    d["kijun"] = kijun
    d["senkou_a"] = span_a
    d["senkou_b"] = span_b
    prev = c.shift(1)
    tr = pd.concat([(h-l), (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
    d["atr"] = tr.rolling(14).mean()
    d["ema20"] = ema(c, 20)
    d["ema50"] = ema(c, 50)
    d["volume_mean"] = d["volume"].rolling(20).mean()
    d["volume_ratio"] = d["volume"] / d["volume_mean"].replace(0, np.nan)
    return d

# --------------------------- STRUCTURE ET CHANDELIERS ---------------------------

def candle_pattern(row, previous=None):
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    body = abs(c - o)
    rng = max(h - l, 1e-12)
    upper = h - max(o, c)
    lower = min(o, c) - l
    if body / rng < 0.10:
        return "Doji", 0
    if lower > body * 2 and upper < body * 0.8:
        return "Marteau / rejet bas", 1
    if upper > body * 2 and lower < body * 0.8:
        return "Étoile / rejet haut", -1
    if previous is not None:
        po, pc = previous["open"], previous["close"]
        if c > o and pc < po and c >= po and o <= pc:
            return "Englobante haussière", 1
        if c < o and pc > po and c <= po and o >= pc:
            return "Englobante baissière", -1
    return "Aucun motif majeur", 0

def support_resistance(df, window=60):
    recent = df.tail(window)
    return float(recent["low"].min()), float(recent["high"].max())

def detect_false_breakout(df, support, resistance):
    if len(df) < 3:
        return "Données insuffisantes"
    last = df.iloc[-1]
    prev = df.iloc[-2]
    if prev["high"] > resistance and last["close"] < resistance:
        return "Possible fausse cassure haussière (réintégration)"
    if prev["low"] < support and last["close"] > support:
        return "Possible fausse cassure baissière (réintégration)"
    return "Aucune fausse cassure évidente"

def resample_timeframe(df, minutes):
    rule = f"{minutes}min"
    return df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna(subset=["open", "high", "low", "close"])

# --------------------------- MOTEUR DE SIGNAL ---------------------------

def safe_num(value):
    return float(value) if pd.notna(value) else np.nan

def analyze_market(df):
    if len(df) < 60:
        raise ValueError(
            f"Il faut au moins 60 bougies pour l'analyse. "
            f"Données reçues : {len(df)}."
        )
    d = add_indicators(df)
    last = d.iloc[-1]
    prev = d.iloc[-2]
    score = 0
    reasons = []
    def add(condition, points, reason):
        nonlocal score
        if condition:
            score += points
            reasons.append(("+" if points > 0 else "") + f"{points}: {reason}")
    add(last["rsi"] > 52 and last["rsi"] > prev["rsi"], 1, "RSI haussier")
    add(last["rsi"] < 48 and last["rsi"] < prev["rsi"], -1, "RSI baissier")
    add(last["wcci"] > 50, 1, "WCCI positif")
    add(last["wcci"] < -50, -1, "WCCI négatif")
    add(last["cfo"] > 0, 1, "CFO positif")
    add(last["cfo"] < 0, -1, "CFO négatif")
    add(last["macd"] > last["macd_signal"], 1, "MACD au-dessus du signal")
    add(last["macd"] < last["macd_signal"], -1, "MACD sous le signal")
    add(last["close"] > last["ema20"] > last["ema50"], 1, "Prix au-dessus EMA20/EMA50")
    add(last["close"] < last["ema20"] < last["ema50"], -1, "Prix sous EMA20/EMA50")
    cloud_top = np.nanmax([last["senkou_a"], last["senkou_b"]])
    cloud_bottom = np.nanmin([last["senkou_a"], last["senkou_b"]])
    add(last["close"] > cloud_top, 1, "Prix au-dessus du nuage Ichimoku")
    add(last["close"] < cloud_bottom, -1, "Prix sous le nuage Ichimoku")
    pattern, pattern_score = candle_pattern(last, prev)
    add(pattern_score != 0, pattern_score, f"Chandelier : {pattern}")
    higher = add_indicators(resample_timeframe(df, 5))
    mtf = "Neutre"
    if len(higher) >= 30:
        hlast = higher.iloc[-1]
        if pd.notna(hlast["ema20"]) and pd.notna(hlast["ema50"]):
            if hlast["close"] > hlast["ema20"] > hlast["ema50"]:
                mtf = "Haussier"
                add(True, 1, "Confirmation tendance 5 min")
            elif hlast["close"] < hlast["ema20"] < hlast["ema50"]:
                mtf = "Baissier"
                add(True, -1, "Confirmation tendance 5 min")
    support, resistance = support_resistance(df)
    false_breakout = detect_false_breakout(df, support, resistance)
    atr_pct = (last["atr"] / last["close"] * 100) if last["close"] else np.nan
    volatility = "Normale"
    if pd.notna(atr_pct):
        if atr_pct < 0.015:
            volatility = "Faible — marché possiblement endormi"
        elif atr_pct > 0.50:
            volatility = "Très forte — prudence"
    volume_status = "Indisponible"
    if pd.notna(last["volume_ratio"]):
        volume_status = "Au-dessus de la moyenne" if last["volume_ratio"] > 1.2 else "Normal/faible"
    now_dakar = datetime.now(timezone.utc)
    hour = now_dakar.hour
    session_ok = 7 <= hour <= 20
    if not session_ok:
        reasons.append("Filtre horaire : hors plage indicative 07h–20h UTC")
    caution = []
    if "Possible fausse cassure" in false_breakout:
        caution.append(false_breakout)
    if "Faible" in volatility or "Très forte" in volatility:
        caution.append(volatility)
    if pattern == "Doji":
        caution.append("Doji : hésitation")
    if not session_ok:
        caution.append("Hors plage horaire")
    if score >= 6:
        raw_signal = "CALL"
    elif score <= -6:
        raw_signal = "PUT"
    else:
        raw_signal = "ATTENDRE"
    if caution and raw_signal != "ATTENDRE":
        signal = "ATTENDRE"
    else:
        signal = raw_signal
    confidence = min(95, int(abs(score) / 11 * 100))
    if signal == "ATTENDRE":
        confidence = min(confidence, 49)
    return {
        "data": d,
        "signal": signal,
        "raw_signal": raw_signal,
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
        "cautions": caution,
        "pattern": pattern,
        "mtf": mtf,
        "support": support,
        "resistance": resistance,
        "false_breakout": false_breakout,
        "volatility": volatility,
        "volume_status": volume_status,
        "atr_pct": atr_pct,
    }

# --------------------------- INTERFACE ---------------------------

with st.sidebar:
    st.header("⚙️ Configuration")
    source_choice = st.radio(
        "Source des données",
        ["Yahoo Finance (externe)", "OTCharts (IQ Option si symbole disponible)"],
        index=0
    )
    yahoo_symbol = st.text_input("Symbole Yahoo", value=DEFAULT_SYMBOL)
    st.caption("Pour le Dollar Index Yahoo : ^DXY")
    st.caption("Bougies : 2 minutes")
    st.divider()
    st.subheader("Règles")
    min_score = st.number_input(
        "Seuil de score CALL/PUT (règle indicative)",
        min_value=3, max_value=10, value=6
    )
    st.caption("Le moteur reste prudent : en cas de filtre défavorable, il affiche ATTENDRE.")
    refresh = st.button("🔄 Actualiser l'analyse", use_container_width=True)

if "signal_history" not in st.session_state:
    st.session_state.signal_history = []

if source_choice.startswith("OTCharts"):
    st.subheader("Connexion OTCharts")
    try:
        client = create_otcharts_client()
        symbol_items = get_otcharts_symbols(client)
        options = []
        for item in symbol_items:
            sym, label = symbol_label(item)
            if sym and sym not in options:
                options.append(sym)
        if not options:
            st.error("Le catalogue OTCharts n'a renvoyé aucun symbole IQ Option.")
            st.stop()
        dxy_candidates = [
            s for s in options
            if "DXY" in s.upper() or "DOLLAR" in s.upper() or "USDINDEX" in s.upper()
        ]
        default_index = options.index(dxy_candidates[0]) if dxy_candidates else 0
        chosen_symbol = st.selectbox(
            "Symbole réellement présent dans le catalogue IQ Option",
            options,
            index=default_index
        )
        if not dxy_candidates:
            st.warning(
                "Aucun symbole DXY évident n'a été trouvé dans le catalogue. "
                "Ne sélectionne pas un autre actif en pensant qu'il s'agit du DXY."
            )
        if st.button("📥 Charger les bougies OTCharts"):
            with st.spinner("Récupération des bougies..."):
                try:
                    market_df, source_name, used_symbol = fetch_otcharts_candles(chosen_symbol)
                    st.session_state.market_df = market_df
                    st.session_state.source_name = source_name
                    st.session_state.used_symbol = used_symbol
                    st.session_state.loaded_at = datetime.now(timezone.utc)
                except Exception as exc:
                    st.error(f"Échec OTCharts : {exc}")
                    st.info("Aucun basculement silencieux vers Yahoo n'est effectué.")
    except Exception as exc:
        st.error(f"Connexion OTCharts impossible : {exc}")
        st.info(
            "Vérifie l'installation du paquet, ta clé API et la disponibilité du service. "
            "Tu peux sélectionner Yahoo Finance dans la barre latérale."
        )
else:
    if refresh or "market_df" not in st.session_state or st.session_state.get("source_name") != "Yahoo Finance":
        with st.spinner("Téléchargement des bougies Yahoo Finance..."):
            try:
                market_df = load_yahoo(yahoo_symbol, period="5d", interval="2m")
                st.session_state.market_df = market_df
                st.session_state.source_name = "Yahoo Finance"
                st.session_state.used_symbol = yahoo_symbol
                st.session_state.loaded_at = datetime.now(timezone.utc)
            except Exception as exc:
                st.error(f"Erreur Yahoo Finance : {exc}")

if "market_df" not in st.session_state:
    st.info("Choisis une source et charge les données pour commencer.")
    st.stop()

market_df = st.session_state.market_df.copy()
source_name = st.session_state.get("source_name", "Source inconnue")
used_symbol = st.session_state.get("used_symbol", "Symbole inconnu")
loaded_at = st.session_state.get("loaded_at", datetime.now(timezone.utc))
age = (datetime.now(timezone.utc) - loaded_at).total_seconds()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Source", source_name)
c2.metric("Symbole", used_symbol)
c3.metric("Bougies", len(market_df))
c4.metric("Dernière réception", f"{int(age)} s")

last_timestamp = market_df.index[-1]
last_age = (datetime.now(timezone.utc) - last_timestamp.to_pydatetime()).total_seconds()
st.caption(
    f"Dernière bougie horodatée UTC : {last_timestamp} | "
    f"Âge de cette bougie : {int(last_age)} secondes. "
    "L'heure de téléchargement ne prouve pas que la cotation est en direct."
)

if last_age > 600:
    st.error("Données anciennes (plus de 10 minutes). N'utilise pas le signal pour une décision en direct.")
elif last_age > 180:
    st.warning("Les données semblent retardées ou le marché peut être peu actif. Vérifie le graphique source.")

try:
    result = analyze_market(market_df)
except Exception as exc:
    st.error(f"Analyse impossible : {exc}")
    st.stop()

if result["score"] >= min_score:
    adjusted_raw = "CALL"
elif result["score"] <= -min_score:
    adjusted_raw = "PUT"
else:
    adjusted_raw = "ATTENDRE"

if adjusted_raw != "ATTENDRE" and result["cautions"]:
    adjusted_signal = "ATTENDRE"
else:
    adjusted_signal = adjusted_raw

st.divider()
st.subheader("🎯 Résultat de l'analyse")
col1, col2, col3 = st.columns(3)
col1.metric("Signal", adjusted_signal)
col2.metric("Score technique", f'{result["score"]:+d}')
col3.metric("Indice de concordance", f'{result["confidence"]}%')
st.caption(
    "L'indice de concordance est un score interne basé sur les règles ci-dessus, "
    "pas une probabilité de réussite."
)

if adjusted_signal == "CALL":
    st.success("Biais haussier détecté — attendre une confirmation sur le graphique avant toute décision.")
elif adjusted_signal == "PUT":
    st.error("Biais baissier détecté — attendre une confirmation sur le graphique avant toute décision.")
else:
    st.warning("Pas assez de confirmations ou filtre défavorable : ATTENDRE.")

left, right = st.columns(2)
with left:
    st.markdown("**Indicateurs**")
    st.write(f'RSI : {result["data"]["rsi"].iloc[-1]:.2f}')
    st.write(f'WCCI : {result["data"]["wcci"].iloc[-1]:.2f}')
    st.write(f'CFO : {result["data"]["cfo"].iloc[-1]:.4f}')
    st.write(f'MACD : {result["data"]["macd"].iloc[-1]:.6f}')
    st.write(f'ATR % : {result["atr_pct"]:.4f}' if pd.notna(result["atr_pct"]) else "ATR % : indisponible")
with right:
    st.markdown("**Contexte de marché**")
    st.write(f'Tendance 5 min : {result["mtf"]}')
    st.write(f'Chandelier : {result["pattern"]}')
    st.write(f'Volatilité : {result["volatility"]}')
    st.write(f'Volume : {result["volume_status"]}')
    st.write(f'Fausse cassure : {result["false_breakout"]}')

st.markdown("**Supports et résistances détectés (fenêtre récente)**")
sr1, sr2 = st.columns(2)
sr1.metric("Support indicatif", f'{result["support"]:.5f}')
sr2.metric("Résistance indicative", f'{result["resistance"]:.5f}')

with st.expander("Voir les raisons du score"):
    if result["reasons"]:
        for reason in result["reasons"]:
            st.write("• " + reason)
    else:
        st.write("Aucune condition directionnelle suffisamment claire.")
    if result["cautions"]:
        st.markdown("**Filtres de prudence :**")
        for caution in result["cautions"]:
            st.write("⚠️ " + caution)

chart_df = result["data"].tail(180)
fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=chart_df.index, open=chart_df["open"], high=chart_df["high"],
    low=chart_df["low"], close=chart_df["close"], name="Prix"
))
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["bb_upper"], name="BB supérieure",
                         line=dict(width=1, dash="dot")))
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["bb_mid"], name="BB moyenne",
                         line=dict(width=1)))
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["bb_lower"], name="BB inférieure",
                         line=dict(width=1, dash="dot")))
fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["ema20"], name="EMA 20",
                         line=dict(width=1)))
fig.update_layout(
    height=620, xaxis_rangeslider_visible=False,
    title=f"{used_symbol} — bougies 2 minutes — {source_name}",
    legend_orientation="h"
)
st.plotly_chart(fig, use_container_width=True)

if not st.session_state.signal_history or st.session_state.signal_history[-1]["time"] != str(last_timestamp):
    st.session_state.signal_history.append({
        "time": str(last_timestamp),
        "source": source_name,
        "symbol": used_symbol,
        "signal": adjusted_signal,
        "score": result["score"],
        "close": float(market_df["close"].iloc[-1])
    })
    st.session_state.signal_history = st.session_state.signal_history[-200:]

st.subheader("📊 Historique des signaux de cette session")
history = pd.DataFrame(st.session_state.signal_history)
if not history.empty:
    st.dataframe(history.iloc[::-1], use_container_width=True, hide_index=True)
    csv = history.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Télécharger l'historique CSV", csv, "historique_signaux_v86.csv", "text/csv")
else:
    st.info("Aucun signal enregistré.")

st.divider()
st.warning(
    "Sécurité : ce robot est un outil d'analyse uniquement. Il ne passe aucun ordre. "
    "Vérifie toujours le symbole, la source, l'heure et les bougies directement sur IQ Option. "
    "Ne considère jamais un signal comme certain."
)
# FIN DU FICHIER - V8.6 PRO - UN SEUL FICHIER
