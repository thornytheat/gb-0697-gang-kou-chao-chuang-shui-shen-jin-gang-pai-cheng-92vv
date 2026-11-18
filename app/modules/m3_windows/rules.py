from decimal import Decimal
from app.report import report
from app.stations import CONFIRMATION_STATIONS, ALL_STATIONS, REGISTRY, MAX_INTERP_GAP_S, LAG_TOLERANCE_S

def safe_segment(a,b,ha,hb,threshold):
    if b<=a or b-a>MAX_INTERP_GAP_S:return None
    if ha>=threshold and hb>=threshold:return (a,b)
    if ha<threshold and hb<threshold:return None
    cross=a+(threshold-ha)*(b-a)/(hb-ha)
    return (cross,b) if hb>ha else (a,cross)

def station_curve(points):
    """单站分段线性曲线：返回 (起,止,起高,止高,起点来源行,终点来源行) 列表，缺口不外推。"""
    segs=[]
    for p,q in zip(points,points[1:]):
        if q[0]-p[0]<=MAX_INTERP_GAP_S:
            segs.append((p[0],q[0],p[1],q[1],p[2],q[2]))
    return segs

def interp(seg,t):
    a,b,ha,hb,_,_=seg
    if t==b:return hb
    return ha+(hb-ha)*(t-a)/(b-a)

def coverage_at(curves,t):
    """某时刻各站采信情况：available 站给出内插值与来源行，missing 站记录缺证原因。"""
    available,missing={},{}
    for code,segs in curves.items():
        hit=next((s for s in segs if s[0]<=t<=s[1]),None)
        if hit is None:
            missing[code]="未回传或观测缺口，不外推"
        else:
            available[code]={"height":interp(hit,t),"line_a":hit[4],"line_b":hit[5]}
    return available,missing

def tier_for(available):
    # 三站齐备才是确认窗；必备两站在但缺第三站旁证 -> 临时窗（可发船但须人工复核）；
    # 连必备站都缺 -> 无安全窗，禁止外推。
    if set(ALL_STATIONS).issubset(available):return "CONFIRMED"
    if set(CONFIRMATION_STATIONS).issubset(available):return "PROVISIONAL"
    if available:return "WEAK"
    return "NONE"

def envelope_windows(curves,threshold,conflicts=()):
    """对各站包络（最小值）求安全时段，并逐段保留采信站点与缺证旁证。"""
    # 事件时刻：各站分段端点 + 冲突断点。每个事件区间内采信集合不变。
    breaks=sorted({t for segs in curves.values() for s in segs for t in (s[0],s[1])} | set(conflicts))
    out=[]
    for a,b in zip(breaks,breaks[1:]):
        if any(a<=t<=b for t in conflicts):continue
        mid=(a+b)/2
        av_a,miss_a=coverage_at(curves,a)
        av_m,miss_m=coverage_at(curves,mid)
        av_b,miss_b=coverage_at(curves,b)
        # 区间内采信站集合恒定，三端一致；缺证取并集说明。
        if not av_m:continue
        heights=[v["height"] for v in av_m.values()]
        if min(heights)<threshold:continue
        stations=sorted(av_m)
        missing=sorted(set(ALL_STATIONS)-set(stations))
        evidence={code:{"line_a":av_m[code]["line_a"],"line_b":av_m[code]["line_b"]} for code in stations}
        out.append({"start_s":a,"end_s":b,"stations":stations,"missing":missing,
                    "tier":tier_for(av_m),"envelope_m":min(heights),
                    "threshold_m":threshold,"evidence_lines":evidence,
                    "coverage_gap":{code:miss_m[code] for code in missing}})
    # 合并相邻同采信集合的时段。
    merged=[]
    for w in out:
        if merged and merged[-1]["end_s"]==w["start_s"] and merged[-1]["stations"]==w["stations"]:
            merged[-1]["end_s"]=w["end_s"]
        else:merged.append(dict(w))
    return merged

def windows(points,threshold,conflicts=()):
    # 兼容旧测试的单曲线入口（无站点维度时使用）。
    out=[]
    for (a,ha),(b,hb) in zip(points,points[1:]):
        if any(a<=t<=b for t in conflicts):continue
        hit=safe_segment(a,b,ha,hb,threshold)
        if hit and hit[0]<hit[1]:
            if out and out[-1][1]==hit[0]:out[-1]=(out[-1][0],hit[1])
            else:out.append(hit)
    return out

def build_curves(effective):
    curves={}
    for code in ALL_STATIONS:
        pts=sorted((r["a"],r["depth"],r["line"]) for r in effective if r["kind"]=="tide" and r["station"]==code)
        curves[code]=station_curve(pts)
    return curves

def _turning_points(pts):
    """把连续等高潮位合并成平台，识别高/低潮转折点，平台以中点为特征时刻。"""
    if len(pts)<3:return []
    plateaus=[];start=0
    for i in range(1,len(pts)+1):
        if i==len(pts) or pts[i][1]!=pts[start][1]:
            plateaus.append({"t0":pts[start][0],"t1":pts[i-1][0],"h":pts[start][1],"line":pts[start][2]})
            start=i
    out=[]
    for prev,cur,nxt in zip(plateaus,plateaus[1:],plateaus[2:]):
        if cur["h"]>prev["h"] and cur["h"]>nxt["h"]:kind="HIGH"
        elif cur["h"]<prev["h"] and cur["h"]<nxt["h"]:kind="LOW"
        else:continue
        out.append({"kind":kind,"t_s":(cur["t0"]+cur["t1"])/2,"h":cur["h"],"line":cur["line"]})
    return out

def lag_check(effective):
    """核对内外港潮时差：配对两站高/低潮转折点，实测滞后与名义半小时比较。"""
    def pts(code):
        return sorted((r["a"],r["depth"],r["line"]) for r in effective if r["kind"]=="tide" and r["station"]==code)
    off=_turning_points(pts("OFFSHORE"));har=_turning_points(pts("HARBOR"))
    nominal=REGISTRY["HARBOR"].lag_s;out=[]
    for kind in ("HIGH","LOW"):
        of=[p for p in off if p["kind"]==kind];hf=[p for p in har if p["kind"]==kind]
        for o,h in zip(of,hf):
            observed=int(h["t_s"]-o["t_s"])
            out.append({"feature":kind,"offshore_t_s":o["t_s"],"harbor_t_s":h["t_s"],
                        "offshore_line":o["line"],"harbor_line":h["line"],
                        "height_m":h["h"],"nominal_lag_s":nominal,"observed_lag_s":observed,
                        "deviation_s":observed-nominal,
                        "within_tolerance":abs(observed-nominal)<=LAG_TOLERANCE_S})
    return sorted(out,key=lambda x:x["offshore_t_s"])

def station_coverage_timeline(curves,step=1800):
    """逐时刻采信清单：采信了哪些站、缺什么旁证、包络水深与等级。"""
    timeline=[]
    breaks=sorted({t for segs in curves.values() for s in segs for t in (s[0],s[1])})
    if not breaks:return timeline
    t=breaks[0]
    while t<=breaks[-1]:
        av,miss=coverage_at(curves,t)
        timeline.append({"t_s":t,"stations":sorted(av),
                         "missing":sorted(miss),
                         "envelope_m":min((v["height"] for v in av.values()),default=None),
                         "tier":tier_for(av),
                         "lines":{c:av[c]["line_a"] for c in av}})
        t+=step
    return timeline

def apply(ctx):
    curves=build_curves(ctx["effective"])
    ctx["station_curves"]=curves
    ctx["coverage_timeline"]=station_coverage_timeline(curves)
    ctx["lag_check"]=lag_check(ctx["effective"])
    out=[]
    for ship in (r for r in ctx["effective"] if r["kind"]=="ship"):
        threshold=ship["depth"]+Decimal(1)-Decimal(8)
        for w in envelope_windows(curves,threshold,ctx.get("tide_conflict_times",[])):
            a,b=max(w["start_s"],ship["a"]),min(w["end_s"],ship["b"])
            if a<b:
                out.append({"id":ship["id"],"start_s":a,"end_s":b,
                            "threshold_m":threshold,"duration":ship["duration"],"line":ship["line"],
                            "stations":w["stations"],"missing":w["missing"],"tier":w["tier"],
                            "envelope_m":w["envelope_m"],"evidence_lines":w["evidence_lines"],
                            "coverage_gap":w["coverage_gap"]})
    ctx["tide_windows"]=out
    provisional=sum(w["tier"]!="CONFIRMED" for w in out)
    return report(out,潮窗=len(out),确认窗=len(out)-provisional,临时窗=provisional,
                  基准水深="8m",余量="1m",采信原则="各站包络取最小值，缺站降级不外推")
