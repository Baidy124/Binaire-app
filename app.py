# Code.py - V10.1 SIMPLE - Bouton ANALYSER remis - SANS AUTO - LIVE OTCharts
import os
from datetime import datetime
import numpy as np, pandas as pd, streamlit as st
st.set_page_config(page_title="IQ OPTION SIMPLE", page_icon="📈", layout="centered")
st.markdown("""<style>.big{font-size:55px;font-weight:bold;line-height:1}.mid{font-size:38px;font-weight:bold}.lab{color:#AAAAAA;font-size:15px}.call{background:#1E4D2B;color:white;padding:15px;border-radius:10px;font-size:18px}.put{background:#5A1F1F;color:white;padding:15px;border-radius:10px;font-size:18px}.wait{background:#3A3A1F;color:white;padding:15px;border-radius:10px;font-size:18px}</style>""", unsafe_allow_html=True)
def get_secret(n):
 try:
  v=st.secrets.get(n)
  if v: return v
 except: pass
 return os.getenv(n)
def ot_client():
 from otcharts import Client as C
 k=get_secret("OTCHARTS_API_KEY")
 if not k:
  try: k=st.secrets.get("otcharts",{}).get("api_key")
  except: k=None
 if not k: st.error("❌ Mets OTCHARTS_API_KEY dans Secrets"); st.stop()
 try: return C(api_key=k)
 except TypeError: return C()
def norm(raw):
 if isinstance(raw,pd.DataFrame): df=raw.copy()
 elif isinstance(raw,list): df=pd.DataFrame(raw)
 elif isinstance(raw,dict): df=pd.DataFrame(raw.get("candles",raw.get("data",raw)))
 else: raise ValueError("Format")
 if isinstance(df.columns,pd.MultiIndex): df.columns=[str(c[0]) for c in df.columns]
 df.columns=[str(c).strip().lower() for c in df.columns]
 mp={"open":["open","o"],"high":["high","h","max"],"low":["low","l","min"],"close":["close","c","price"],"volume":["volume","vol","v"],"time":["time","timestamp","date","datetime"]}
 rn={}
 for s,chs in mp.items():
  for c in chs:
   if c in df.columns: rn[c]=s; break
 df=df.rename(columns=rn)
 if "time" in df.columns:
  ts=pd.to_datetime(df.pop("time"),unit="s",utc=True,errors="coerce")
  df.index=ts
 else: df.index=pd.to_datetime(df.index,utc=True,errors="coerce")
 for c in ["open","high","low","close","volume"]:
  if c not in df.columns: df[c]=np.nan
  df[c]=pd.to_numeric(df[c],errors="coerce")
 df=df[~df.index.isna()].sort_index(); df=df[~df.index.duplicated(keep="last")]; df=df.dropna(subset=["open","high","low","close"])
 return df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"})[["Open","High","Low","Close","Volume"]].tail(500)
def ot_candles(sym,tf=120):
 cl=ot_client(); return norm(cl.candles("iq",sym,tf=tf,limit=500))
def ot_symbols(cl):
 s=cl.symbols("iq")
 if isinstance(s,pd.DataFrame): return s.to_dict("records")
 if isinstance(s,dict): return s.get("symbols",s.get("data",list(s.values())))
 return list(s)
# --- COMME TA PHOTO ---
st.markdown('<div class="lab">Temps (expiration)</div>', unsafe_allow_html=True)
exp=st.slider("",1,19,16)
paire=st.selectbox("Choisir", ["Dollar Index (DXY)","EUR/USD","GBP/USD","USD/JPY","BTC/USD","ETH/USD"])
st.markdown(f"Tu as choisi : **{paire} - {exp} mn**")
try:
 cl=ot_client(); items=ot_symbols(cl); opts=[]
 for it in items:
  s=it.get("symbol") if isinstance(it,dict) else str(it)
  if s and s not in opts: opts.append(str(s))
 cand=[s for s in opts if "DXY" in s.upper() or "DOLLAR" in s.upper()] if paire=="Dollar Index (DXY)" else [s for s in opts if paire.split("/")[0] in s.upper()]
 idx=opts.index(cand[0]) if cand else 0
 ot_sym=st.selectbox("Symbole IQ Option LIVE", opts, index=idx)
except Exception as e: st.error(f"OTCharts : {e}"); st.stop()
# --- BOUTONS REMIS - SANS AUTO ---
col1, col2 = st.columns(2)
with col1: btn_verif = st.button("Vérifier MAINTENANT", use_container_width=True)
with col2: btn_analyse = st.button("🔍 ANALYSER", type="primary", use_container_width=True)
# Si tu cliques sur un des 2, ça analyse. C'est toi qui décides.
if btn_verif or btn_analyse:
 with st.spinner("Analyse LIVE..."):
  try: df=ot_candles(ot_sym,120)
  except Exception as e: st.error(f"Échec OTCharts : {e}"); st.stop()
  if len(df)<60: st.error("Pas assez de bougies"); st.stop()
  c=df["Close"]; ema9=c.ewm(span=9,adjust=False).mean(); ema21=c.ewm(span=21,adjust=False).mean()
  dl=c.diff(); g=dl.clip(lower=0); lo=-dl.clip(upper=0); ag=g.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); al=lo.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); rs=ag/al.replace(0,np.nan); rsi=100-(100/(1+rs)); rsi=rsi.fillna(50)
  prix=float(c.iloc[-1]); r=float(rsi.iloc[-1]); e9=float(ema9.iloc[-1]); e21=float(ema21.iloc[-1])
  o=df["Open"].values; cc=df["Close"].values; trois="OK"
  if cc[-1]>o[-1] and cc[-2]>o[-2] and cc[-3]>o[-3]: trois="ÉPUISEMENT"
  if cc[-1]<o[-1] and cc[-2]<o[-2] and cc[-3]<o[-3]: trois="ÉPUISEMENT"
  h=df["High"]; l=df["Low"]; tk=(h.rolling(9).max()+l.rolling(9).min())/2; kj=(h.rolling(26).max()+l.rolling(26).min())/2; sa=((tk+kj)/2).shift(26); sb=((h.rolling(52).max()+l.rolling(52).min())/2).shift(26); nh=max(sa.iloc[-1],sb.iloc[-1]) if pd.notna(sa.iloc[-1]) else np.nan; nb=min(sa.iloc[-1],sb.iloc[-1]) if pd.notna(sa.iloc[-1]) else np.nan; dans_nuage=pd.notna(nh) and nb<=prix<=nh
  if dans_nuage or trois=="ÉPUISEMENT": sig="ATTENDRE"; raison="Dans nuage ou 3 bougies d'affilée - Attends"
  elif e9>e21 and 50<r<68 and cc[-1]>o[-1]: sig="CALL"; raison=""
  elif e9<e21 and 32<r<50 and cc[-1]<o[-1]: sig="PUT"; raison=""
  else: sig="ATTENDRE"; raison="Pas de confirmation - Attends"
  st.markdown('<div class="lab">Prix actuel</div>', unsafe_allow_html=True); st.markdown(f'<div class="big">{prix:.3f}</div>', unsafe_allow_html=True); st.caption(f"LIVE OTCharts - {ot_sym} - 0 retard - {datetime.now().strftime('%H:%M:%S')}")
  st.markdown('<div class="lab">RSI (14)</div>', unsafe_allow_html=True); st.markdown(f'<div class="mid">{r:.1f}</div>', unsafe_allow_html=True)
  st.markdown('<div class="lab">EMA 9 / 21</div>', unsafe_allow_html=True); st.markdown(f'<div class="mid">{e9:.5f} / {e21:.5f}</div>', unsafe_allow_html=True)
  if sig=="CALL": st.markdown(f'<div class="call">🟢 TENDANCE : CALL pour {exp} mn sur {paire}</div>', unsafe_allow_html=True); st.success(f"Sur IQ Option, clique Haut, {exp} min")
  elif sig=="PUT": st.markdown(f'<div class="put">🔴 TENDANCE : PUT pour {exp} mn sur {paire}</div>', unsafe_allow_html=True); st.error(f"Sur IQ Option, clique Bas, {exp} min")
  else: st.markdown(f'<div class="wait">⏳ TENDANCE : ATTENDRE pour {exp} mn sur {paire}<br>{raison}</div>', unsafe_allow_html=True); st.warning("Ne clique rien sur IQ Option")
  st.line_chart(c.tail(80))
st.caption("V10.1 SIMPLE - Bouton ANALYSER remis - SANS AUTO - Prix LIVE IQ Option - Analyse uniquement, aucun ordre. Lundi = DÉMO.")
# FIN V10.1
