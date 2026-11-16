# Code.py - V8.7 - UN SEUL FICHIER - V8.6 + V8.5 - COURT POUR COPIER
import os, base64, uuid
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go, yfinance as yf
try:
 from openai import OpenAI
except: OpenAI=None
st.set_page_config(page_title="IQ OPTION V8.7", page_icon="📈", layout="wide")
st.title("📈 IQ OPTION AI TRADER V8.7")
st.caption("Analyse lecture seule - aucun ordre")
SEUIL_V2PRO=5; SEUIL_SCALPING=4; PAYOUT=0.85; MAX_JOUR=6
def get_secret(n,d=None):
 try:
  v=st.secrets.get(n,d)
  if v: return v
 except: pass
 return os.getenv(n,d)
@st.cache_resource
def get_ai():
 c=get_secret("OPENAI_API_KEY")
 if not c or not str(c).startswith("sk-"): return None
 try: return OpenAI(api_key=str(c).strip())
 except: return None
client=get_ai(); CLE=client is not None
if "hist" not in st.session_state: st.session_state.hist=[]
PAIRES={"Dollar Index (DXY)":"^DXY","EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X","USD/CHF":"USDCHF=X","AUD/USD":"AUDUSD=X","NZD/USD":"NZDUSD=X","USD/CAD":"USDCAD=X","EUR/GBP":"EURGBP=X","EUR/JPY":"EURJPY=X","EUR/CHF":"EURCHF=X","EUR/AUD":"EURAUD=X","EUR/CAD":"EURCAD=X","EUR/NZD":"EURNZD=X","GBP/JPY":"GBPJPY=X","GBP/CHF":"GBPCHF=X","GBP/AUD":"GBPAUD=X","GBP/CAD":"GBPCAD=X","AUD/JPY":"AUDJPY=X","AUD/CAD":"AUDCAD=X","AUD/CHF":"AUDCHF=X","CAD/JPY":"CADJPY=X","CHF/JPY":"CHFJPY=X","NZD/JPY":"NZDJPY=X","NZD/CAD":"NZDCAD=X","USD/BRL":"USDBRL=X","EUR/BRL":"EURBRL=X","USD/MXN":"USDMXN=X","USD/ZAR":"USDZAR=X","USD/TRY":"USDTRY=X","USD/INR":"USDINR=X","BTC/USD":"BTC-USD","ETH/USD":"ETH-USD","LTC/USD":"LTC-USD","XRP/USD":"XRP-USD"}
def is_dxy(n): return "DXY" in n or "Dollar" in n
with st.sidebar:
 st.header("⚙️ V8.7")
 src=st.radio("Source",["Yahoo Finance","OTCharts (IQ Option)"],index=0)
 mode=st.radio("Mode",[f"📊 V2 PRO - {SEUIL_V2PRO}/6",f"⚡ SCALPING - {SEUIL_SCALPING}/6"],index=0)
 scalp=mode.startswith("⚡")
 exp=st.slider("Expiration SCALPING",1,5,2) if scalp else st.slider("Expiration V2 PRO",1,19,5)
 use_mtf=st.checkbox("✅ MTF 3/3",value=True); use_ichi=st.checkbox("✅ Ichimoku",value=True); use_v8=st.checkbox("✅ V8 Pullback",value=True); use_faux=st.checkbox("✅ Faux Cassure",value=True); use_vol=st.checkbox("✅ Volume",value=True)
 refresh=st.button("🔄 Actualiser")
col1,col2=st.columns(2)
with col1: paire=st.selectbox("Choisir un actif",list(PAIRES.keys()))
with col2: st.metric("Expiration",f"{exp} min"); st.metric("Mode","SCALPING" if scalp else "V2 PRO")
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
  if ts.notna().sum()==0: ts=pd.to_datetime(raw["time"],utc=True,errors="coerce")
  df.index=ts
 elif not isinstance(df.index,pd.DatetimeIndex): df.index=pd.to_datetime(df.index,utc=True,errors="coerce")
 elif df.index.tz is None: df.index=df.index.tz_localize("UTC")
 else: df.index=df.index.tz_convert("UTC")
 for c in ["open","high","low","close","volume"]:
  if c not in df.columns: df[c]=np.nan
  df[c]=pd.to_numeric(df[c],errors="coerce")
 df=df[~df.index.isna()].sort_index(); df=df[~df.index.duplicated(keep="last")]; df=df.dropna(subset=["open","high","low","close"])
 df=df.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"})
 return df[["Open","High","Low","Close","Volume"]].tail(500)
@st.cache_data(ttl=25,show_spinner=False)
def load_yahoo(sym,per="5d",inter="2m"):
 d=yf.Ticker(sym).history(period=per,interval=inter,auto_adjust=False)
 if d.empty: raise ValueError("Yahoo vide")
 d=d.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
 if d.index.tz is None: d.index=d.index.tz_localize("UTC")
 else: d.index=d.index.tz_convert("UTC")
 return norm(d)
def get_yahoo(sym,inter="2m",per="5d"):
 try: return load_yahoo(sym,per,inter)
 except: return pd.DataFrame()
def get_dxy(inter="2m",per="5d"):
 try:
  ticks={"EURUSD":"EURUSD=X","USDJPY":"USDJPY=X","GBPUSD":"GBPUSD=X","USDCAD":"USDCAD=X","USDSEK":"USDSEK=X","USDCHF":"USDCHF=X"}; dfs={}
  for n,t in ticks.items():
   d=get_yahoo(t,inter,per)
   if d.empty or len(d)<50: return pd.DataFrame()
   dfs[n]=d["Close"]
  a=pd.concat(dfs,axis=1,join="inner"); a.columns=list(dfs.keys()); a=a.dropna()
  if len(a)<80: return pd.DataFrame()
  cl=50.14348112*(a["EURUSD"]**(-0.576))*(a["USDJPY"]**0.136)*(a["GBPUSD"]**(-0.119))*(a["USDCAD"]**0.091)*(a["USDSEK"]**0.042)*(a["USDCHF"]**0.036)
  df=pd.DataFrame(index=a.index); df["Close"]=cl; df["Open"]=cl.shift(1); df["High"]=pd.concat([df["Open"],df["Close"]],axis=1).max(axis=1); df["Low"]=pd.concat([df["Open"],df["Close"]],axis=1).min(axis=1); df["Volume"]=1000; return df.dropna()
 except: return pd.DataFrame()
def get_data(sym,inter="2m",per="5d",paire=""):
 if is_dxy(paire):
  d=get_dxy(inter,per)
  if not d.empty: return d
  return get_yahoo("^DXY",inter,per)
 return get_yahoo(sym,inter,per)
def ot_client():
 from otcharts import Client as C
 k=get_secret("OTCHARTS_API_KEY")
 if not k:
  try: k=st.secrets.get("otcharts",{}).get("api_key")
  except: k=None
 try:
  return C(api_key=k) if k else C()
 except TypeError: return C()
def ot_symbols(cl):
 s=cl.symbols("iq")
 if isinstance(s,pd.DataFrame): return s.to_dict("records")
 if isinstance(s,dict): return s.get("symbols",s.get("data",list(s.values())))
 return list(s)
def ot_candles(sym):
 cl=ot_client(); raw=cl.candles("iq",sym,tf=120,limit=500); return norm(raw)
def ind(df):
 d=df.copy(); c,h,l=d["Close"],d["High"],d["Low"]
 d["EMA5"]=c.ewm(span=5,adjust=False).mean(); d["EMA9"]=c.ewm(span=9,adjust=False).mean(); d["EMA21"]=c.ewm(span=21,adjust=False).mean(); d["EMA50"]=c.ewm(span=50,adjust=False).mean(); d["EMA20"]=c.ewm(span=20,adjust=False).mean()
 dl=c.diff(); g=dl.clip(lower=0); lo=-dl.clip(upper=0); ag=g.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); al=lo.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); rs=ag/al.replace(0,np.nan); d["RSI"]=100-(100/(1+rs)); d["RSI"]=d["RSI"].fillna(50)
 ag7=g.ewm(alpha=1/7,adjust=False,min_periods=7).mean(); al7=lo.ewm(alpha=1/7,adjust=False,min_periods=7).mean(); rs7=ag7/al7.replace(0,np.nan); d["RSI7"]=100-(100/(1+rs7)); d["RSI7"]=d["RSI7"].fillna(50)
 d["BB_MID"]=c.rolling(20).mean(); sd=c.rolling(20).std(); d["BB_UPPER"]=d["BB_MID"]+2*sd; d["BB_LOWER"]=d["BB_MID"]-2*sd; d["BB_WIDTH"]=(d["BB_UPPER"]-d["BB_LOWER"])/d["BB_MID"].replace(0,np.nan)
 typ=(h+l+c)/3; mn=typ.rolling(20).mean(); mad=typ.rolling(20).apply(lambda x: np.mean(np.abs(x-np.mean(x))),raw=True); d["WCCI"]=(typ-mn)/(0.015*mad.replace(0,np.nan)); d["WCCI"]=d["WCCI"].fillna(0)
 x=np.arange(14,dtype=float)
 def cfo_w(v):
  if len(v)<14 or np.isnan(v).any(): return np.nan
  sl,ic=np.polyfit(x,v,1); f=ic+sl*14; return ((v[-1]-f)/v[-1])*100 if v[-1] else np.nan
 d["CFO"]=c.rolling(14).apply(cfo_w,raw=True); d["CFO"]=d["CFO"].fillna(0)
 d["MACD"]=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean(); d["MACD_SIGNAL"]=d["MACD"].ewm(span=9,adjust=False).mean(); d["MACD_HIST"]=d["MACD"]-d["MACD_SIGNAL"]
 pc=c.shift(1); tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1); d["ATR"]=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); d["ATR_MOYEN"]=d["ATR"].rolling(50).mean(); d["SUPPORT"]=l.rolling(30).min().shift(1); d["RESISTANCE"]=h.rolling(30).max().shift(1)
 if "Volume" in d.columns: d["VOL_MOYEN"]=d["Volume"].rolling(20).mean()
 e9,e21,e50,rsi,wcci,cfo,mh,bm,cv=d["EMA9"].values,d["EMA21"].values,d["EMA50"].values,d["RSI"].values,d["WCCI"].values,d["CFO"].values,d["MACD_HIST"].values,d["BB_MID"].values,c.values
 th=(e9>e21)&(e21>e50); tb=(e9<e21)&(e21<e50)
 d["SCORE_H"]=(th.astype(int)+((rsi>50)&(rsi<70)).astype(int)+(wcci>0).astype(int)+(cfo>0).astype(int)+(mh>0).astype(int)+(cv>bm).astype(int))
 d["SCORE_B"]=(tb.astype(int)+((rsi>30)&(rsi<50)).astype(int)+(wcci<0).astype(int)+(cfo<0).astype(int)+(mh<0).astype(int)+(cv<bm).astype(int))
 o=d["Open"].values; cc=d["Close"].values; hh=d["High"].values; ll=d["Low"].values; corps=np.abs(cc-o); amp=hh-ll; ratio=np.divide(corps,amp,out=np.zeros_like(corps,dtype=float),where=amp!=0); d["DIR"]=np.where(ratio<0.10,0,np.where(cc>o,1,-1)); d["RATIO"]=ratio
 d["DIST_ATR"]=(d["Close"]-d["EMA9"]).abs()/d["ATR"].replace(0,np.nan); d["ECART_9_21"]=(d["EMA9"]-d["EMA21"]).abs()/d["ATR"].replace(0,np.nan); d["ECART_21_50"]=(d["EMA21"]-d["EMA50"]).abs()/d["ATR"].replace(0,np.nan); d["FORCE_OK"]=(d["ECART_9_21"]>=0.25)&(d["ECART_21_50"]>=0.25); d["DIST_OK"]=d["DIST_ATR"]<=1.2; d["PULL_H"]=(d["DIST_ATR"]<=1.0)&(d["Close"]>=d["EMA9"]); d["PULL_B"]=(d["DIST_ATR"]<=1.0)&(d["Close"]<=d["EMA9"]); d["MOM_H"]=(d["MACD_HIST"]>d["MACD_HIST"].shift(1))&(d["MACD_HIST"]>0); d["MOM_B"]=(d["MACD_HIST"]<d["MACD_HIST"].shift(1))&(d["MACD_HIST"]<0)
 tk=(h.rolling(9).max()+l.rolling(9).min())/2; kj=(h.rolling(26).max()+l.rolling(26).min())/2; d["tenkan"]=tk; d["kijun"]=kj; d["senkou_a"]=((tk+kj)/2).shift(26); d["senkou_b"]=((h.rolling(52).max()+l.rolling(52).min())/2).shift(26)
 nh=d[["senkou_a","senkou_b"]].max(axis=1); nb=d[["senkou_a","senkou_b"]].min(axis=1); d["ichi_pos"]=np.where(d["senkou_a"].isna()|d["senkou_b"].isna(),np.nan,np.where(d["Close"]>nh,1,np.where(d["Close"]<nb,-1,0))); d["ichi_signal"]="ATTENDRE"; d.loc[(d["ichi_pos"]==1),"ichi_signal"]="CALL"; d.loc[(d["ichi_pos"]==-1),"ichi_signal"]="PUT"; d.loc[d["ichi_pos"]==0,"ichi_signal"]="ATTENDRE"
 return d
def trois(df):
 if len(df)<3: return {"liste":[],"fig":"Pas assez","nb_h":0,"nb_b":0,"nb_d":0,"dir":"NEUTRE","doji":True}
 def desc(r):
  o,c,h,l=float(r["Open"]),float(r["Close"]),float(r["High"]),float(r["Low"]); co=abs(c-o); am=h-l
  if am==0: return "Doji","NEUTRE",0
  ra=co/am
  if ra<0.10: return "Doji","NEUTRE",ra
  return ("Verte" if c>o else "Rouge"),("HAUSSE" if c>o else "BAISSE"),ra
 b3,b2,b1=df.iloc[-3],df.iloc[-2],df.iloc[-1]; d3,dir3,r3=desc(b3); d2,dir2,r2=desc(b2); d1,dir1,r1=desc(b1)
 lst=[{"Bougie":"-3","Type":d3,"Dir":dir3},{"Bougie":"-2","Type":d2,"Dir":dir2},{"Bougie":"-1","Type":d1,"Dir":dir1}]
 nh=sum([1 for x in [dir3,dir2,dir1] if x=="HAUSSE"]); nb=sum([1 for x in [dir3,dir2,dir1] if x=="BAISSE"]); nd=sum([1 for x in [dir3,dir2,dir1] if x=="NEUTRE"])
 fig="Aucune"
 if nh==3: fig="🟢 3 Vertes"
 elif nb==3: fig="🔴 3 Rouges"
 elif nh==2 and dir1=="HAUSSE": fig="🟢 2 Vertes / 1 Rouge"
 elif nb==2 and dir1=="BAISSE": fig="🔴 2 Rouges / 1 Verte"
 elif nd>=2: fig="🟡 Beaucoup Doji"
 return {"liste":lst,"fig":fig,"nb_h":nh,"nb_b":nb,"nb_d":nd,"dir":dir1,"doji":dir1=="NEUTRE"}
def mtf_calc(df,df5,df15):
 def direction(d):
  try: return np.where((d["EMA9"].values>d["EMA21"].values)&(d["RSI"].values>50),"HAUSSE",np.where((d["EMA9"].values<d["EMA21"].values)&(d["RSI"].values<50),"BAISSE","NEUTRE"))
  except: return np.array(["NEUTRE"]*len(d))
 d2=direction(df)
 def mp(small):
  if small is None or small.empty or len(small)<20: return np.array(["NEUTRE"]*len(df))
  ds=direction(small); i2=pd.DatetimeIndex([x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC") for x in df.index]); ismall=pd.DatetimeIndex([x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC") for x in small.index]); p=ismall.searchsorted(i2,side="right")-1; m=p>=0; pc=np.clip(p,0,len(ds)-1); out=np.array(["NEUTRE"]*len(df),dtype=object); out[m]=ds[pc[m]]; return out
 d5=mp(df5); d15=mp(df15); fin=np.array(["NEUTRE"]*len(df),dtype=object)
 for i in range(len(df)):
  if d2[i]=="HAUSSE" and d5[i]=="HAUSSE" and d15[i]=="HAUSSE": fin[i]="HAUSSE"
  elif d2[i]=="BAISSE" and d5[i]=="BAISSE" and d15[i]=="BAISSE": fin[i]="BAISSE"
  elif d2[i] in ["HAUSSE","BAISSE"] and d5[i] in ["HAUSSE","BAISSE"] and d2[i]!=d5[i]: fin[i]="CONFLIT"
 return fin[-1],{"2m":d2[-1],"5m":d5[-1],"15m":d15[-1]}
def v8_check(df):
 c=df.iloc[-1]; prix=float(c["Close"]); atr=float(c["ATR"]) if pd.notna(c["ATR"]) else 0
 if atr<=0: return False,False,["ATR invalide"],0
 dist=abs(prix-float(c["EMA9"]))/atr; ok_dist=dist<=1.2; e1=abs(float(c["EMA9"])-float(c["EMA21"]))/atr; e2=abs(float(c["EMA21"])-float(c["EMA50"]))/atr; force=(e1>=0.25) and (e2>=0.25); pull_h=dist<=1.0 and prix>=float(c["EMA9"]); pull_b=dist<=1.0 and prix<=float(c["EMA9"]); arr=df["DIR"].values; ep_h=len(arr)>=3 and arr[-1]==1 and arr[-2]==1 and arr[-3]==1; ep_b=len(arr)>=3 and arr[-1]==-1 and arr[-2]==-1 and arr[-3]==-1; mh=df["MACD_HIST"].values; mom_h=len(mh)>=2 and mh[-1]>mh[-2] and mh[-1]>0; mom_b=len(mh)>=2 and mh[-1]<mh[-2] and mh[-1]<0; rsi=float(c["RSI"]); okc=ok_dist and force and pull_h and (not ep_h) and rsi<=68 and mom_h; okp=ok_dist and force and pull_b and (not ep_b) and rsi>=32 and mom_b; rs=[]
 if not ok_dist: rs.append(f"Trop loin EMA9 {dist:.2f} ATR")
 if not force: rs.append("RANGE EMA collées")
 if ep_h or ep_b: rs.append("Épuisement 3 bougies")
 return okc,okp,rs,dist
def analyse_live(df,ticker,paire):
 c=df.iloc[-1]; prix=float(c["Close"]); atr=float(c["ATR"]) if pd.notna(c["ATR"]) else 0; sup=float(c["SUPPORT"]) if pd.notna(c["SUPPORT"]) else np.nan; res=float(c["RESISTANCE"]) if pd.notna(c["RESISTANCE"]) else np.nan; proche_sup=pd.notna(sup) and atr>0 and abs(prix-sup)<=atr*0.20; proche_res=pd.notna(res) and atr>0 and abs(res-prix)<=atr*0.20; info=trois(df); sh=int(c["SCORE_H"]); sb=int(c["SCORE_B"])
 try:
  if is_dxy(paire): df5=get_dxy("5m","5d"); df15=get_dxy("15m","5d")
  else: df5=get_data(ticker,"5m","5d",paire); df15=get_data(ticker,"15m","5d",paire)
  df5=ind(df5) if not df5.empty else df5; df15=ind(df15) if not df15.empty else df15; mtf_dir,mtf_det=mtf_calc(df,df5,df15)
 except: mtf_dir="NEUTRE"; mtf_det={"2m":"NEUTRE","5m":"NEUTRE","15m":"NEUTRE"}
 ichi_pos=c["ichi_pos"]; ichi_sig=c["ichi_signal"]
 if pd.isna(ichi_pos): ichi_txt="Ichimoku : Pas assez"
 elif ichi_pos==0: ichi_txt="Ichimoku : DANS nuage - ATTENDRE"
 elif ichi_sig=="CALL": ichi_txt="Ichimoku CALL - DESSUS nuage"
 elif ichi_sig=="PUT": ichi_txt="Ichimoku PUT - DESSOUS nuage"
 else: ichi_txt="Ichimoku ATTENDRE"
 okc,okp,raisons,dist=v8_check(df)
 vol_txt="Volume indisponible"; vol_faible=False
 try:
  vol=float(c["Volume"]); vm=float(c["VOL_MOYEN"])
  if np.isfinite(vol) and np.isfinite(vm) and vm>0:
   ra=vol/vm; vol_txt=f"Volume {ra:.2f}x"; vol_faible=ra<0.7
 except: pass
 faux=False; faux_txt="✅ Pas de faux breakout"
 try:
  for j in range(-6,-1):
   r=df.iloc[j]; rj=float(r["RESISTANCE"]) if pd.notna(r["RESISTANCE"]) else np.nan; sj=float(r["SUPPORT"]) if pd.notna(r["SUPPORT"]) else np.nan; cj=float(r["Close"]); cn=float(df.iloc[j+1]["Close"])
   if pd.notna(rj) and cj>rj and cn<rj: faux=True; faux_txt="⚠️ FAUX BREAKOUT HAUSSIER"; break
   if pd.notna(sj) and cj<sj and cn>sj: faux=True; faux_txt="⚠️ FAUX BREAKOUT BAISSIER"; break
 except: pass
 base={"sh":sh,"sb":sb,"info":info,"sup":sup,"res":res,"mtf":mtf_dir,"mtf_det":mtf_det,"ichi_txt":ichi_txt,"ichi_sig":ichi_sig,"ichi_pos":ichi_pos,"okc":okc,"okp":okp,"raisons":raisons,"dist":dist,"vol_txt":vol_txt,"faux":faux,"faux_txt":faux_txt,"dir":info["dir"],"doji":info["doji"]}
 seuil=SEUIL_SCALPING if scalp else SEUIL_V2PRO
 if use_mtf:
  if sh>=seuil and mtf_dir!="HAUSSE": return {"signal":"ATTENDRE","raison":f"MTF non haussier : {mtf_dir}",**base}
  if sb>=seuil and mtf_dir!="BAISSE": return {"signal":"ATTENDRE","raison":f"MTF non baissier : {mtf_dir}",**base}
 if use_ichi:
  if not pd.isna(ichi_pos) and ichi_pos==0: return {"signal":"ATTENDRE","raison":f"ICHIMOKU : {ichi_txt}",**base}
  if sh>=seuil and ichi_sig=="PUT": return {"signal":"ATTENDRE","raison":"ICHIMOKU contraire CALL vs PUT",**base}
  if sb>=seuil and ichi_sig=="CALL": return {"signal":"ATTENDRE","raison":"ICHIMOKU contraire PUT vs CALL",**base}
 if use_v8:
  if sh>=seuil and not okc: return {"signal":"ATTENDRE","raison":f"V8 bloque CALL : {' | '.join(raisons) if raisons else 'Pullback non validé'}",**base}
  if sb>=seuil and not okp: return {"signal":"ATTENDRE","raison":f"V8 bloque PUT : {' | '.join(raisons) if raisons else 'Pullback non validé'}",**base}
 if faux and use_faux: return {"signal":"ATTENDRE","raison":faux_txt,**base}
 if use_vol and vol_faible: return {"signal":"ATTENDRE","raison":f"VOLUME : {vol_txt}",**base}
 if info["nb_d"]>=2: return {"signal":"ATTENDRE","raison":f"Filtre : {info['nb_d']} Doji",**base}
 if scalp:
  sh_ok=float(c["EMA5"])>float(c["EMA9"]) and float(c["RSI7"])>50; sb_ok=float(c["EMA5"])<float(c["EMA9"]) and float(c["RSI7"])<50
  if sh>=seuil and sh_ok and not proche_res and info["dir"]=="HAUSSE" and not info["doji"]: return {"signal":"CALL / HAUSSE","raison":f"V8.7 SCALPING {sh}/6 + MTF {mtf_dir}",**base}
  if sb>=seuil and sb_ok and not proche_sup and info["dir"]=="BAISSE" and not info["doji"]: return {"signal":"PUT / BAISSE","raison":f"V8.7 SCALPING {sb}/6 + MTF {mtf_dir}",**base}
  return {"signal":"ATTENDRE","raison":f"SCALPING : Pas {seuil}/6",**base}
 if sh>=seuil and not proche_res and info["dir"]=="HAUSSE" and not info["doji"]: return {"signal":"CALL / HAUSSE","raison":f"V8.7 V2 PRO {sh}/6 + MTF {mtf_dir}",**base}
 if sb>=seuil and not proche_sup and info["dir"]=="BAISSE" and not info["doji"]: return {"signal":"PUT / BAISSE","raison":f"V8.7 V2 PRO {sb}/6 + MTF {mtf_dir}",**base}
 return {"signal":"ATTENDRE","raison":f"Pas {seuil}/6 - H {sh}, B {sb}",**base}
# --- OTCharts catalogue ---
ot_sym=None
if src.startswith("OTCharts"):
 st.subheader("OTCharts - Catalogue réel IQ Option")
 try:
  cl=ot_client(); items=ot_symbols(cl); opts=[]
  for it in items:
   s=it.get("symbol") if isinstance(it,dict) else str(it)
   if s and s not in opts: opts.append(str(s))
  if not opts: st.error("Catalogue vide"); st.stop()
  cand=[s for s in opts if "DXY" in s.upper() or "DOLLAR" in s.upper()]
  idx=opts.index(cand[0]) if cand else 0; ot_sym=st.selectbox("Symbole dans catalogue IQ Option",opts,index=idx)
  if not cand: st.warning("Pas de DXY dans catalogue. Ne choisis pas un autre actif en croyant que c'est DXY.")
 except Exception as e: st.error(f"OTCharts impossible : {e}")
# --- BACKTEST ---
st.divider(); st.header("🧪 BACKTEST V8.7 - Yahoo")
mode_bt=st.radio("Mode backtest",["✅ Mode 1 PRÉCIS 1m","⚠️ Mode 2 APPROX 2m"],index=0)
exp_bt=st.selectbox("Expiration backtest",[1,3,5],index=1) if mode_bt.startswith("✅") else st.selectbox("Expiration backtest approx",[2,4,6],index=1)
if st.button("🧪 LANCER BACKTEST",type="secondary"):
 with st.spinner("Backtest..."):
  tick=PAIRES[paire]; df2=get_data(tick,"2m","5d",paire); df1=get_data(tick,"1m","5d",paire) if mode_bt.startswith("✅") else df2
  if df2.empty or len(df2)<200: st.error("Pas assez données")
  else:
   df2=ind(df2); df2=df2.iloc[100:].copy().dropna(subset=["RSI","WCCI","CFO","MACD_HIST","ATR","BB_MID","EMA50"])
   ng=np_=na=0; dets=[]; profit=0; last_h=None; trades_jour={}; seuil=SEUIL_SCALPING if scalp else SEUIL_V2PRO
   for i in range(60,len(df2)-2):
    idx=df2.index[i]; utc=idx.tz_localize("UTC") if idx.tzinfo is None else idx.tz_convert("UTC"); h=utc.hour; js=utc.weekday()
    if js==6 or (js==5 and h>=20) or h<7 or h>=17 or (12<=h<14): na+=1; continue
    js_str=utc.strftime("%Y-%m-%d"); hs=utc.strftime("%Y-%m-%d %H")
    if last_h==hs: continue
    if trades_jour.get(js_str,0)>=MAX_JOUR: continue
    r=df2.iloc[i]; sh=int(r["SCORE_H"]); sb=int(r["SCORE_B"]); sig="ATTENDRE"
    if scalp:
     if sh>=seuil and float(r["EMA5"])>float(r["EMA9"]) and float(r["RSI7"])>50 and int(r["DIR"])==1: sig="CALL / HAUSSE"
     elif sb>=seuil and float(r["EMA5"])<float(r["EMA9"]) and float(r["RSI7"])<50 and int(r["DIR"])==-1: sig="PUT / BAISSE"
     else: na+=1; continue
    else:
     if sh>=seuil and int(r["DIR"])==1: sig="CALL / HAUSSE"
     elif sb>=seuil and int(r["DIR"])==-1: sig="PUT / BAISSE"
     else: na+=1; continue
    if mode_bt.startswith("✅"):
     if df1.empty or len(df1)<100: continue
     idx1=pd.DatetimeIndex([x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC") for x in df1.index]); pe=idx1.searchsorted(utc+timedelta(minutes=2),side="right")
     if pe>=len(df1): continue
     ps=pe+exp_bt
     if ps>=len(df1): continue
     pe_p=float(df1["Close"].values[pe]); ps_p=float(df1["Close"].values[ps])
    else:
     pas=max(1,int(round(exp_bt/2)))
     if i+pas>=len(df2): break
     pe_p=float(df2["Close"].values[i]); ps_p=float(df2["Close"].values[i+pas])
    g=(ps_p>pe_p) if sig=="CALL / HAUSSE" else (ps_p<pe_p)
    if g: ng+=1; profit+=PAYOUT
    else: np_+=1; profit-=1
    last_h=hs; trades_jour[js_str]=trades_jour.get(js_str,0)+1
    if len(dets)<30: dets.append({"Heure":utc.strftime("%d/%m %H:%M"),"Signal":sig,"Entrée":round(pe_p,5),"Sortie":round(ps_p,5),"Résultat":"GAGNÉ" if g else "PERDU"})
   tot=ng+np_; taux=(ng/tot*100) if tot>0 else 0; st.metric("Trades",tot); st.metric("✅ GAGNÉ",ng); st.metric("❌ PERDU",np_); st.metric("🏆 Taux",f"{taux:.1f}%"); st.metric("💰 Profit 1$ / trade",f"{profit:.2f}$"); st.write(f"ATTENDRE : {na}")
   if taux>=60: st.success(f"✅ Excellent {taux:.1f}% - Démo")
   elif taux>=55: st.warning(f"🟡 Juste {taux:.1f}% - Démo d'abord")
   else: st.error(f"🔴 Non rentable {taux:.1f}% - Ne passe pas en réel")
   if dets: st.dataframe(pd.DataFrame(dets),use_container_width=True,hide_index=True)
# --- ANALYSER ---
if st.button("🔍 ANALYSER MAINTENANT - V8.7",type="primary"):
 with st.spinner("Analyse..."):
  tick=PAIRES[paire]; df=pd.DataFrame(); src_txt=""
  if src.startswith("OTCharts"):
   if not ot_sym: st.error("Choisis symbole OTCharts")
   else:
    try: df=ot_candles(ot_sym); src_txt=f"OTCharts - {ot_sym} - Prix IQ Option LIVE"; st.success(f"✅ LIVE OTCharts : {len(df)} bougies")
    except Exception as e: st.error(f"Échec OTCharts : {e} - Aucune bascule silencieuse vers Yahoo"); df=pd.DataFrame()
  else: df=get_data(tick,"2m","5d",paire); src_txt="Yahoo / DXY Synthétique - RETARD 2-5 min"; st.warning(src_txt)
  if df.empty: st.error("Données insuffisantes. Si DXY fermé dimanche, normal.")
  elif len(df)<80: st.error(f"Seulement {len(df)} bougies")
  else:
   try:
    lt=df.index[-1]; age=(datetime.now(timezone.utc)-pd.to_datetime(lt,utc=True).to_pydatetime()).total_seconds(); st.caption(f"Dernière bougie : {lt} | Âge {int(age)} s")
    if age>600: st.error("Données >10 min - Ne trade pas en direct")
    elif age>180: st.warning("Données retardées - Vérifie graphique")
   except: pass
   df=ind(df); df=df.dropna(subset=["RSI","WCCI","CFO","MACD_HIST","ATR","BB_MID","EMA50"])
   if len(df)<4: st.error("Pas assez données")
   else:
    a=analyse_live(df,tick,paire); c=df.iloc[-1]; nid=str(uuid.uuid4())[:8]; st.session_state.hist.append({"ID":nid,"Heure":datetime.now().strftime("%H:%M:%S"),"Paire":paire,"Mode":"SCALPING" if scalp else "V2 PRO","Signal":a["signal"],"Prix":round(float(c["Close"]),5),"Score H":a["sh"],"Score B":a["sb"],"MTF":a["mtf"],"Résultat":"En attente"})
    st.divider(); st.subheader(f"🎯 SIGNAL V8.7 - {paire} - {exp} min - {src_txt}")
    if is_dxy(paire):
     if a["signal"]=="CALL / HAUSSE": st.info("DXY CALL = Dollar FORT - Sur IQ Option clique DXY CALL - EUR/USD PUT")
     elif a["signal"]=="PUT / BAISSE": st.info("DXY PUT = Dollar FAIBLE - Sur IQ Option clique DXY PUT - EUR/USD CALL")
     else: st.info("DXY ATTENDRE - Ne trade pas")
    st.metric("Prix",f"{float(c['Close']):.5f}"); st.metric("RSI 14 / RSI 7",f"{float(c['RSI']):.1f} / {float(c['RSI7']):.1f}"); st.metric("EMA 5 / 9 / 21",f"{float(c['EMA5']):.5f} / {float(c['EMA9']):.5f} / {float(c['EMA21']):.5f}"); st.metric("WCCI / CFO",f"{float(c['WCCI']):.1f} / {float(c['CFO']):.4f}")
    if a["signal"]=="CALL / HAUSSE": st.success(f"🟢 CALL - {exp} mn - VALIDÉ")
    elif a["signal"]=="PUT / BAISSE": st.error(f"🔴 PUT - {exp} mn - VALIDÉ")
    else: st.warning("⏳ ATTENDRE")
    st.write("Motif :",a["raison"]); st.metric("Score HAUSSE",f"{a['sh']}/6"); st.metric("Score BAISSE",f"{a['sb']}/6"); st.subheader("🚀 V8 Pullback"); st.info(f"Distance {a['dist']:.2f} ATR | OK CALL {a['okc']} / OK PUT {a['okp']} | {a['raisons']}"); st.subheader("☁️ Ichimoku"); st.info(a["ichi_txt"]); st.subheader("MTF 3/3"); st.info(f"MTF {a['mtf']}"); st.dataframe(pd.DataFrame([a["mtf_det"]]),use_container_width=True); st.subheader("Faux Cassure"); st.write(a["faux_txt"]); st.subheader("Volume"); st.write(a["vol_txt"]); st.subheader("🕯️ 3 Bougies"); st.info(f"Figure {a['info']['fig']} | Vertes {a['info']['nb_h']} | Rouges {a['info']['nb_b']} | Doji {a['info']['nb_d']}"); st.dataframe(pd.DataFrame(a["info"]["liste"]),use_container_width=True,hide_index=True); st.subheader("Support / Résistance"); st.metric("Support",f"{float(a['sup']):.5f}" if pd.notna(a["sup"]) else "-"); st.metric("Résistance",f"{float(a['res']):.5f}" if pd.notna(a["res"]) else "-")
    fig=go.Figure(); fig.add_trace(go.Candlestick(x=df.index.tail(100),open=df["Open"].tail(100),high=df["High"].tail(100),low=df["Low"].tail(100),close=df["Close"].tail(100),name="Prix")); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["BB_UPPER"].tail(100),name="BB sup",line=dict(width=1,dash="dot"))); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["BB_MID"].tail(100),name="BB mid",line=dict(width=1))); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["BB_LOWER"].tail(100),name="BB inf",line=dict(width=1,dash="dot"))); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["EMA9"].tail(100),name="EMA9",line=dict(width=1))); fig.update_layout(height=600,xaxis_rangeslider_visible=False,title=f"{paire} - 2m - {src_txt}"); st.plotly_chart(fig,use_container_width=True)
# --- HISTORIQUE ---
st.divider(); st.header("📊 Historique")
if not st.session_state.hist: st.info("Aucun signal")
else:
 dfh=pd.DataFrame(st.session_state.hist); f=dfh[dfh["Signal"].isin(["CALL / HAUSSE","PUT / BAISSE"])]; fin=f[f["Résultat"].isin(["GAGNÉ","PERDU"])]; ng=len(fin[fin["Résultat"]=="GAGNÉ"]); np_=len(fin[fin["Résultat"]=="PERDU"]); taux=(ng/(ng+np_)*100) if (ng+np_)>0 else 0; st.metric("🏆 Taux",f"{taux:.1f}%"); st.metric("GAGNÉ",ng); st.metric("PERDU",np_)
 for _,row in dfh.iterrows():
  st.write(f"{row['Heure']} - {row['Paire']} - {row['Signal']} - Prix {row['Prix']} - {row['Résultat']}")
  if row["Signal"] in ["CALL / HAUSSE","PUT / BAISSE"] and row["Résultat"]=="En attente":
   if st.button("✅ GAGNÉ",key=f"g{row['ID']}"):
    for j in range(len(st.session_state.hist)):
     if st.session_state.hist[j]["ID"]==row["ID"]: st.session_state.hist[j]["Résultat"]="GAGNÉ"
    st.rerun()
   if st.button("❌ PERDU",key=f"p{row['ID']}"):
    for j in range(len(st.session_state.hist)):
     if st.session_state.hist[j]["ID"]==row["ID"]: st.session_state.hist[j]["Résultat"]="PERDU"
    st.rerun()
 if st.button("🗑️ Effacer historique"): st.session_state.hist=[]; st.rerun()
# --- CAPTURE ---
st.divider(); st.header(f"📸 Capture V8.7 - {paire} - {exp} mn")
mode_cap=st.radio("Mode capture",["🤖 AUTO IA","✍️ MANUEL"],index=0 if CLE else 1,horizontal=True)
up=st.file_uploader("Envoie ta capture",type=["png","jpg","jpeg","webp"],key="cap87")
if up:
 st.image(up,use_container_width=True)
 if mode_cap.startswith("🤖"):
  if not CLE: st.error("Mets clé OpenAI ou utilise MANUEL")
  elif st.button("🧠 ANALYSER CAPTURE",type="primary"):
   try:
    enc=base64.b64encode(up.getvalue()).decode("utf-8"); url=f"data:{up.type or 'image/png'};base64,{enc}"; pr=f"Analyste PRO V8.7 IQ Option {paire} Expiration {exp} min Graphique 2m. Règles : MTF 3/3 sinon ATTENDRE, Ichimoku DANS nuage = ATTENDRE, V8 Pullback, Épuisement 3 bougies = ATTENDRE, Distance EMA9 <1.2 ATR, RSI CALL<=68 PUT>=32, Minimum 5/6. Donne tableau 3 bougies, MTF, Ichimoku, V8, Score /6, CONCLUSION CALL/PUT/ATTENDRE. Ne garantis jamais un gain."
    with st.spinner("IA analyse..."): r=client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"user","content":[{"type":"text","text":pr},{"type":"image_url","image_url":{"url":url,"detail":"high"}}]}],max_tokens=1200); st.markdown(r.choices[0].message.content)
   except Exception as e: st.error(f"Erreur IA : {e}")
 else:
  b3=st.selectbox("Bougie -3",["Verte","Rouge","Doji"],key="b3"); b2=st.selectbox("Bougie -2",["Verte","Rouge","Doji"],key="b2"); b1=st.selectbox("Bougie -1",["Verte","Rouge","Doji"],key="b1"); mt=st.selectbox("5m et 15m ?",["HAUSSE comme 2m","BAISSE comme 2m","Contraire (CONFLIT)","Je ne sais pas"]); ic=st.selectbox("Nuage ?",["DESSUS","DESSOUS","DANS le nuage","Je ne sais pas"])
  if st.button("🔎 ANALYSER SANS CLÉ",type="primary"):
   if mt.startswith("Contraire"): st.warning("⏳ ATTENDRE - MTF CONFLIT")
   elif ic.startswith("DANS"): st.warning("⏳ ATTENDRE - DANS nuage")
   elif b1=="Doji": st.warning("⏳ ATTENDRE - Doji")
   elif b3=="Verte" and b2=="Verte" and b1=="Verte": st.warning("⏳ ATTENDRE - Épuisement 3 vertes")
   elif b3=="Rouge" and b2=="Rouge" and b1=="Rouge": st.warning("⏳ ATTENDRE - Épuisement 3 rouges")
   elif [b3,b2,b1].count("Verte")==2 and b1=="Verte" and ic=="DESSUS": st.success(f"🟢 CALL {paire}")
   elif [b3,b2,b1].count("Rouge")==2 and b1=="Rouge" and ic=="DESSOUS": st.error(f"🔴 PUT {paire}")
   else: st.warning(f"🟡 ATTENDRE {paire}")
st.caption("V8.7 - Analyse uniquement, aucun ordre. Lundi = DÉMO.")
# FIN - Code.py V8.7 UN SEUL FICHIER
