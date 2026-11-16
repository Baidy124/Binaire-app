# Code.py - V8.9 - OTCharts SEULEMENT - 0 RETARD - PAS DE YAHOO
import os, base64, uuid, time
from datetime import datetime, timezone, timedelta
import numpy as np, pandas as pd, streamlit as st, plotly.graph_objects as go
try:
 from openai import OpenAI
except: OpenAI=None
st.set_page_config(page_title="IQ OPTION V8.9 LIVE", page_icon="📈", layout="wide")
st.title("📈 IQ OPTION V8.9 - LIVE OTCharts - 0 RETARD")
st.caption("Prix direct IQ Option - Aucun Yahoo - Aucun retard")
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
def is_dxy(n): return "DXY" in n or "Dollar" in n
with st.sidebar:
 st.header("⚙️ V8.9 LIVE")
 mode=st.radio("Mode",[f"📊 V2 PRO - {SEUIL_V2PRO}/6",f"⚡ SCALPING - {SEUIL_SCALPING}/6"],index=0)
 scalp=mode.startswith("⚡")
 exp=st.slider("Expiration SCALPING",1,5,2) if scalp else st.slider("Expiration V2 PRO",1,19,5)
 use_mtf=st.checkbox("✅ MTF 3/3",value=True); use_ichi=st.checkbox("✅ Ichimoku",value=True); use_v8=st.checkbox("✅ V8 Pullback",value=True); use_faux=st.checkbox("✅ Faux Cassure",value=True); use_vol=st.checkbox("✅ Volume",value=True)
 st.divider(); st.subheader("🔄 AUTO-REFRESH")
 auto=st.checkbox("✅ Auto-refresh",value=True)
 interval=st.selectbox("Toutes les :",[30,60,120],index=0,format_func=lambda x: f"{x} secondes")
paire=st.selectbox("Choisir un actif", ["Dollar Index (DXY)","EUR/USD","GBP/USD","USD/JPY","BTC/USD","ETH/USD"])
st.metric("Expiration",f"{exp} min"); st.metric("Mode","SCALPING" if scalp else "V2 PRO")
if auto: st.info(f"🔄 AUTO ACTIF : {interval}s - 0 retard - Prix IQ Option direct")
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
def ot_client():
 from otcharts import Client as C
 k=get_secret("OTCHARTS_API_KEY")
 if not k:
  try: k=st.secrets.get("otcharts",{}).get("api_key")
  except: k=None
 if not k: st.error("❌ Pas de clé OTCHARTS_API_KEY dans Secrets. Mets ta clé, sinon 0 retard impossible."); st.stop()
 try: return C(api_key=k)
 except TypeError: return C()
def ot_symbols(cl):
 s=cl.symbols("iq")
 if isinstance(s,pd.DataFrame): return s.to_dict("records")
 if isinstance(s,dict): return s.get("symbols",s.get("data",list(s.values())))
 return list(s)
def ot_candles(sym, tf=120):
 cl=ot_client(); raw=cl.candles("iq",sym,tf=tf,limit=500); return norm(raw)
def ot_prix_live(sym):
 try:
  cl=ot_client()
  for tick in cl.stream("iq",[sym]):
   p=getattr(tick,"price",getattr(tick,"close",None))
   if p is not None: return float(p),None
   break
  return None,"Pas de tick"
 except Exception as e: return None,f"{e}"
def ind(df):
 d=df.copy(); c,h,l=d["Close"],d["High"],d["Low"]
 d["EMA5"]=c.ewm(span=5,adjust=False).mean(); d["EMA9"]=c.ewm(span=9,adjust=False).mean(); d["EMA21"]=c.ewm(span=21,adjust=False).mean(); d["EMA50"]=c.ewm(span=50,adjust=False).mean()
 dl=c.diff(); g=dl.clip(lower=0); lo=-dl.clip(upper=0); ag=g.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); al=lo.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); rs=ag/al.replace(0,np.nan); d["RSI"]=100-(100/(1+rs)); d["RSI"]=d["RSI"].fillna(50)
 ag7=g.ewm(alpha=1/7,adjust=False,min_periods=7).mean(); al7=lo.ewm(alpha=1/7,adjust=False,min_periods=7).mean(); rs7=ag7/al7.replace(0,np.nan); d["RSI7"]=100-(100/(1+rs7)); d["RSI7"]=d["RSI7"].fillna(50)
 d["BB_MID"]=c.rolling(20).mean(); sd=c.rolling(20).std(); d["BB_UPPER"]=d["BB_MID"]+2*sd; d["BB_LOWER"]=d["BB_MID"]-2*sd
 typ=(h+l+c)/3; mn=typ.rolling(20).mean(); mad=typ.rolling(20).apply(lambda x: np.mean(np.abs(x-np.mean(x))),raw=True); d["WCCI"]=(typ-mn)/(0.015*mad.replace(0,np.nan)); d["WCCI"]=d["WCCI"].fillna(0)
 x=np.arange(14,dtype=float)
 def cfo_w(v):
  if len(v)<14 or np.isnan(v).any(): return np.nan
  sl,ic=np.polyfit(x,v,1); f=ic+sl*14; return ((v[-1]-f)/v[-1])*100 if v[-1] else np.nan
 d["CFO"]=c.rolling(14).apply(cfo_w,raw=True); d["CFO"]=d["CFO"].fillna(0)
 d["MACD"]=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean(); d["MACD_SIGNAL"]=d["MACD"].ewm(span=9,adjust=False).mean(); d["MACD_HIST"]=d["MACD"]-d["MACD_SIGNAL"]
 pc=c.shift(1); tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1); d["ATR"]=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean(); d["SUPPORT"]=l.rolling(30).min().shift(1); d["RESISTANCE"]=h.rolling(30).max().shift(1)
 if "Volume" in d.columns: d["VOL_MOYEN"]=d["Volume"].rolling(20).mean()
 e9,e21,e50,rsi,wcci,cfo,mh,bm,cv=d["EMA9"].values,d["EMA21"].values,d["EMA50"].values,d["RSI"].values,d["WCCI"].values,d["CFO"].values,d["MACD_HIST"].values,d["BB_MID"].values,c.values
 th=(e9>e21)&(e21>e50); tb=(e9<e21)&(e21<e50)
 d["SCORE_H"]=(th.astype(int)+((rsi>50)&(rsi<70)).astype(int)+(wcci>0).astype(int)+(cfo>0).astype(int)+(mh>0).astype(int)+(cv>bm).astype(int))
 d["SCORE_B"]=(tb.astype(int)+((rsi>30)&(rsi<50)).astype(int)+(wcci<0).astype(int)+(cfo<0).astype(int)+(mh<0).astype(int)+(cv<bm).astype(int))
 o=d["Open"].values; cc=d["Close"].values; hh=d["High"].values; ll=d["Low"].values; corps=np.abs(cc-o); amp=hh-ll; ratio=np.divide(corps,amp,out=np.zeros_like(corps,dtype=float),where=amp!=0); d["DIR"]=np.where(ratio<0.10,0,np.where(cc>o,1,-1))
 d["DIST_ATR"]=(d["Close"]-d["EMA9"]).abs()/d["ATR"].replace(0,np.nan); d["ECART_9_21"]=(d["EMA9"]-d["EMA21"]).abs()/d["ATR"].replace(0,np.nan); d["ECART_21_50"]=(d["EMA21"]-d["EMA50"]).abs()/d["ATR"].replace(0,np.nan)
 tk=(h.rolling(9).max()+l.rolling(9).min())/2; kj=(h.rolling(26).max()+l.rolling(26).min())/2; d["tenkan"]=tk; d["kijun"]=kj; d["senkou_a"]=((tk+kj)/2).shift(26); d["senkou_b"]=((h.rolling(52).max()+l.rolling(52).min())/2).shift(26)
 nh=d[["senkou_a","senkou_b"]].max(axis=1); nb=d[["senkou_a","senkou_b"]].min(axis=1); d["ichi_pos"]=np.where(d["senkou_a"].isna()|d["senkou_b"].isna(),np.nan,np.where(d["Close"]>nh,1,np.where(d["Close"]<nb,-1,0))); d["ichi_signal"]="ATTENDRE"; d.loc[(d["ichi_pos"]==1),"ichi_signal"]="CALL"; d.loc[(d["ichi_pos"]==-1),"ichi_signal"]="PUT"; d.loc[d["ichi_pos"]==0,"ichi_signal"]="ATTENDRE"
 return d
def trois(df):
 def desc(r):
  o,c,h,l=float(r["Open"]),float(r["Close"]),float(r["High"]),float(r["Low"]); co=abs(c-o); am=h-l
  if am==0: return "Doji","NEUTRE"
  ra=co/am
  if ra<0.10: return "Doji","NEUTRE"
  return ("Verte" if c>o else "Rouge"),("HAUSSE" if c>o else "BAISSE")
 b3,b2,b1=df.iloc[-3],df.iloc[-2],df.iloc[-1]; d3,dir3=desc(b3); d2,dir2=desc(b2); d1,dir1=desc(b1)
 lst=[{"Bougie":"-3","Type":d3,"Dir":dir3},{"Bougie":"-2","Type":d2,"Dir":dir2},{"Bougie":"-1","Type":d1,"Dir":dir1}]
 nh=sum([1 for x in [dir3,dir2,dir1] if x=="HAUSSE"]); nb=sum([1 for x in [dir3,dir2,dir1] if x=="BAISSE"]); nd=sum([1 for x in [dir3,dir2,dir1] if x=="NEUTRE"])
 fig="🟢 3 Vertes" if nh==3 else "🔴 3 Rouges" if nb==3 else "🟡 Doji" if nd>=2 else "Aucune"
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
def analyse_live(df,paire,ot_sym):
 c=df.iloc[-1]; prix=float(c["Close"]); atr=float(c["ATR"]) if pd.notna(c["ATR"]) else 0; sup=float(c["SUPPORT"]) if pd.notna(c["SUPPORT"]) else np.nan; res=float(c["RESISTANCE"]) if pd.notna(c["RESISTANCE"]) else np.nan; proche_sup=pd.notna(sup) and atr>0 and abs(prix-sup)<=atr*0.20; proche_res=pd.notna(res) and atr>0 and abs(res-prix)<=atr*0.20; info=trois(df); sh=int(c["SCORE_H"]); sb=int(c["SCORE_B"])
 try:
  df5=ind(ot_candles(ot_sym,300)); df15=ind(ot_candles(ot_sym,900)); mtf_dir,mtf_det=mtf_calc(df,df5,df15)
 except: mtf_dir="NEUTRE"; mtf_det={"2m":"NEUTRE","5m":"NEUTRE","15m":"NEUTRE"}
 ichi_pos=c["ichi_pos"]; ichi_sig=c["ichi_signal"]; ichi_txt="Ichimoku : Pas assez" if pd.isna(ichi_pos) else "Ichimoku : DANS nuage - ATTENDRE" if ichi_pos==0 else "Ichimoku CALL - DESSUS" if ichi_sig=="CALL" else "Ichimoku PUT - DESSOUS" if ichi_sig=="PUT" else "ATTENDRE"
 dist=abs(prix-float(c["EMA9"]))/atr if atr>0 else 99; e1=abs(float(c["EMA9"])-float(c["EMA21"]))/atr if atr>0 else 0; e2=abs(float(c["EMA21"])-float(c["EMA50"]))/atr if atr>0 else 0; force=(e1>=0.25) and (e2>=0.25); arr=df["DIR"].values; ep_h=len(arr)>=3 and arr[-1]==1 and arr[-2]==1 and arr[-3]==1; ep_b=len(arr)>=3 and arr[-1]==-1 and arr[-2]==-1 and arr[-3]==-1; mh=df["MACD_HIST"].values; mom_h=len(mh)>=2 and mh[-1]>mh[-2] and mh[-1]>0; mom_b=len(mh)>=2 and mh[-1]<mh[-2] and mh[-1]<0; rsi=float(c["RSI"]); okc=(dist<=1.2) and force and (dist<=1.0 and prix>=float(c["EMA9"])) and (not ep_h) and rsi<=68 and mom_h; okp=(dist<=1.2) and force and (dist<=1.0 and prix<=float(c["EMA9"])) and (not ep_b) and rsi>=32 and mom_b; raisons=[]
 if dist>1.2: raisons.append(f"Trop loin EMA9 {dist:.2f}")
 if not force: raisons.append("RANGE")
 if ep_h or ep_b: raisons.append("Épuisement 3 bougies")
 vol_txt="Volume indisponible"; vol_faible=False
 try:
  vol=float(c["Volume"]); vm=float(c["VOL_MOYEN"])
  if np.isfinite(vol) and np.isfinite(vm) and vm>0: ra=vol/vm; vol_txt=f"Volume {ra:.2f}x"; vol_faible=ra<0.7
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
  if sh>=seuil and ichi_sig=="PUT": return {"signal":"ATTENDRE","raison":"ICHIMOKU contraire",**base}
  if sb>=seuil and ichi_sig=="CALL": return {"signal":"ATTENDRE","raison":"ICHIMOKU contraire",**base}
 if use_v8:
  if sh>=seuil and not okc: return {"signal":"ATTENDRE","raison":f"V8 bloque CALL : {' | '.join(raisons) if raisons else 'Pullback'}",**base}
  if sb>=seuil and not okp: return {"signal":"ATTENDRE","raison":f"V8 bloque PUT : {' | '.join(raisons) if raisons else 'Pullback'}",**base}
 if faux and use_faux: return {"signal":"ATTENDRE","raison":faux_txt,**base}
 if use_vol and vol_faible: return {"signal":"ATTENDRE","raison":f"VOLUME : {vol_txt}",**base}
 if info["nb_d"]>=2: return {"signal":"ATTENDRE","raison":f"Filtre : {info['nb_d']} Doji",**base}
 if scalp:
  sh_ok=float(c["EMA5"])>float(c["EMA9"]) and float(c["RSI7"])>50; sb_ok=float(c["EMA5"])<float(c["EMA9"]) and float(c["RSI7"])<50
  if sh>=seuil and sh_ok and not proche_res and info["dir"]=="HAUSSE" and not info["doji"]: return {"signal":"CALL / HAUSSE","raison":f"V8.9 SCALPING {sh}/6 + MTF {mtf_dir}",**base}
  if sb>=seuil and sb_ok and not proche_sup and info["dir"]=="BAISSE" and not info["doji"]: return {"signal":"PUT / BAISSE","raison":f"V8.9 SCALPING {sb}/6 + MTF {mtf_dir}",**base}
  return {"signal":"ATTENDRE","raison":f"SCALPING : Pas {seuil}/6",**base}
 if sh>=seuil and not proche_res and info["dir"]=="HAUSSE" and not info["doji"]: return {"signal":"CALL / HAUSSE","raison":f"V8.9 V2 PRO {sh}/6 + MTF {mtf_dir}",**base}
 if sb>=seuil and not proche_sup and info["dir"]=="BAISSE" and not info["doji"]: return {"signal":"PUT / BAISSE","raison":f"V8.9 V2 PRO {sb}/6 + MTF {mtf_dir}",**base}
 return {"signal":"ATTENDRE","raison":f"Pas {seuil}/6 - H {sh}, B {sb}",**base}
# --- OTCharts catalogue ---
st.subheader("OTCharts - Catalogue réel IQ Option - LIVE")
try:
 cl=ot_client(); items=ot_symbols(cl); opts=[]
 for it in items:
  s=it.get("symbol") if isinstance(it,dict) else str(it)
  if s and s not in opts: opts.append(str(s))
 if not opts: st.error("Catalogue vide - Vérifie ta clé"); st.stop()
 cand=[s for s in opts if "DXY" in s.upper() or "DOLLAR" in s.upper()]
 idx=opts.index(cand[0]) if cand else 0; ot_sym=st.selectbox("Symbole IQ Option - Choisis ici",opts,index=idx)
 if not cand: st.warning("Pas de DXY dans catalogue. Ne choisis pas un autre actif en croyant que c'est DXY.")
 pl,err=ot_prix_live(ot_sym)
 if pl is not None: st.success(f"💰 PRIX LIVE IQ Option : {pl:.5f} pour {ot_sym} - Compare avec ton IQ Option, doit être pareil")
 else: st.warning(f"Prix LIVE indisponible : {err}")
except Exception as e: st.error(f"OTCharts impossible : {e} - Mets la clé dans Secrets"); st.stop()
# --- SIGNAL LIVE AUTO ---
st.divider(); st.header("🎯 SIGNAL LIVE V8.9 - 0 RETARD")
if auto or st.button("🔍 ANALYSER MAINTENANT - V8.9",type="primary"):
 with st.spinner("Analyse LIVE..."):
  try: df=ot_candles(ot_sym,120); st.success(f"✅ LIVE OTCharts : {len(df)} bougies - 0 retard")
  except Exception as e: st.error(f"Échec OTCharts : {e} - Pas de Yahoo, pas de faux prix"); df=pd.DataFrame()
  if df.empty: st.error("Données insuffisantes.")
  elif len(df)<80: st.error(f"Seulement {len(df)} bougies")
  else:
   try:
    lt=df.index[-1]; age=(datetime.now(timezone.utc)-pd.to_datetime(lt,utc=True).to_pydatetime()).total_seconds(); st.caption(f"Dernière bougie : {lt} | Âge {int(age)} s | Mise à jour : {datetime.now().strftime('%H:%M:%S')}")
    if age>600: st.error("Données >10 min - Ne trade pas")
    elif age>180: st.warning("Données un peu vieilles - Attends prochaine bougie")
   except: pass
   df=ind(df); df=df.dropna(subset=["RSI","WCCI","CFO","MACD_HIST","ATR","BB_MID","EMA50"])
   if len(df)<4: st.error("Pas assez données")
   else:
    a=analyse_live(df,paire,ot_sym); c=df.iloc[-1]; nid=str(uuid.uuid4())[:8]
    if not st.session_state.hist or st.session_state.hist[-1]["Signal"]!=a["signal"] or st.session_state.hist[-1]["Paire"]!=paire: st.session_state.hist.append({"ID":nid,"Heure":datetime.now().strftime("%H:%M:%S"),"Paire":paire,"Mode":"SCALPING" if scalp else "V2 PRO","Signal":a["signal"],"Prix":round(float(c["Close"]),5),"Score H":a["sh"],"Score B":a["sb"],"MTF":a["mtf"],"Résultat":"En attente"})
    st.subheader(f"🎯 SIGNAL V8.9 - {paire} - {ot_sym} - {exp} min - LIVE 0 retard")
    if is_dxy(paire):
     if a["signal"]=="CALL / HAUSSE": st.info("DXY CALL = Dollar FORT - Sur IQ Option clique DXY CALL - EUR/USD PUT")
     elif a["signal"]=="PUT / BAISSE": st.info("DXY PUT = Dollar FAIBLE - Sur IQ Option clique DXY PUT - EUR/USD CALL")
     else: st.info("DXY ATTENDRE - Ne trade pas")
    st.metric("Prix LIVE",f"{float(c['Close']):.5f}"); st.metric("RSI 14 / RSI 7",f"{float(c['RSI']):.1f} / {float(c['RSI7']):.1f}"); st.metric("EMA 5 / 9 / 21",f"{float(c['EMA5']):.5f} / {float(c['EMA9']):.5f} / {float(c['EMA21']):.5f}")
    if a["signal"]=="CALL / HAUSSE": st.success(f"🟢 CALL - {exp} mn - VALIDÉ")
    elif a["signal"]=="PUT / BAISSE": st.error(f"🔴 PUT - {exp} mn - VALIDÉ")
    else: st.warning("⏳ ATTENDRE - Ne clique rien")
    st.write("Motif :",a["raison"]); st.metric("Score HAUSSE",f"{a['sh']}/6"); st.metric("Score BAISSE",f"{a['sb']}/6"); st.subheader("🚀 V8 Pullback"); st.info(f"Distance {a['dist']:.2f} ATR | OK CALL {a['okc']} / OK PUT {a['okp']}"); st.subheader("☁️ Ichimoku"); st.info(a["ichi_txt"]); st.subheader("MTF 3/3"); st.info(f"MTF {a['mtf']}"); st.dataframe(pd.DataFrame([a["mtf_det"]]),use_container_width=True); st.subheader("Faux Cassure"); st.write(a["faux_txt"]); st.subheader("Volume"); st.write(a["vol_txt"]); st.subheader("🕯️ 3 Bougies"); st.info(f"Figure {a['info']['fig']} | Vertes {a['info']['nb_h']} | Rouges {a['info']['nb_b']} | Doji {a['info']['nb_d']}"); st.dataframe(pd.DataFrame(a["info"]["liste"]),use_container_width=True,hide_index=True); st.subheader("Support / Résistance"); st.metric("Support",f"{float(a['sup']):.5f}" if pd.notna(a["sup"]) else "-"); st.metric("Résistance",f"{float(a['res']):.5f}" if pd.notna(a["res"]) else "-")
    fig=go.Figure(); fig.add_trace(go.Candlestick(x=df.index.tail(100),open=df["Open"].tail(100),high=df["High"].tail(100),low=df["Low"].tail(100),close=df["Close"].tail(100),name="Prix")); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["BB_UPPER"].tail(100),name="BB sup",line=dict(width=1,dash="dot"))); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["BB_MID"].tail(100),name="BB mid",line=dict(width=1))); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["BB_LOWER"].tail(100),name="BB inf",line=dict(width=1,dash="dot"))); fig.add_trace(go.Scatter(x=df.index.tail(100),y=df["EMA9"].tail(100),name="EMA9",line=dict(width=1))); fig.update_layout(height=600,xaxis_rangeslider_visible=False,title=f"{paire} - {ot_sym} - 2m LIVE"); st.plotly_chart(fig,use_container_width=True)
# --- HISTORIQUE ---
st.divider(); st.header("📊 Historique")
if not st.session_state.hist: st.info("Aucun signal")
else:
 dfh=pd.DataFrame(st.session_state.hist); f=dfh[dfh["Signal"].isin(["CALL / HAUSSE","PUT / BAISSE"])]; fin=f[f["Résultat"].isin(["GAGNÉ","PERDU"])]; ng=len(fin[fin["Résultat"]=="GAGNÉ"]); np_=len(fin[fin["Résultat"]=="PERDU"]); taux=(ng/(ng+np_)*100) if (ng+np_)>0 else 0; st.metric("🏆 Taux",f"{taux:.1f}%")
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
st.caption("V8.9 LIVE - 0 retard - Analyse uniquement, aucun ordre. Lundi = DÉMO.")
if auto:
 time.sleep(interval); st.rerun()
# FIN V8.9
