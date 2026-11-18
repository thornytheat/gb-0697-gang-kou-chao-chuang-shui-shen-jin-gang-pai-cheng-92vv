from app.modules.m4_channel.rules import subtract
from app.report import report
from app.stations import ALL_STATIONS

def first_fit(windows,pilots,duration,occupied):
    # 兼容旧测试的二元组窗口：(start,end) 且返回 (x,y)。
    if windows and not isinstance(windows[0],dict):
        candidates=[]
        for a,b in windows:
            for p,q in pilots:
                lo,hi=max(a,p),min(b,q)
                if lo<hi:
                    for x,y in subtract((lo,hi),occupied):
                        if y-x>=duration:candidates.append((x,x+duration))
        return min(candidates) if candidates else None
    rank={"CONFIRMED":0,"PROVISIONAL":1,"WEAK":2,"NONE":3}
    candidates=[]
    for w in windows:
        a,b=w["start_s"],w["end_s"]
        for p,q in pilots:
            lo,hi=max(a,p),min(b,q)
            if lo<hi:
                for x,y in subtract((lo,hi),occupied):
                    if y-x>=duration:
                        # 优先确认窗，其次临时窗；同级再取最早时刻。
                        candidates.append((rank.get(w.get("tier"),9),x,x+duration,w))
    return min(candidates,key=lambda c:(c[0],c[1],c[2])) if candidates else None

def apply(ctx):
    pilots=[(r["a"],r["b"]) for r in ctx["effective"] if r["kind"]=="pilot"]
    ships=sorted((r for r in ctx["effective"] if r["kind"]=="ship"),key=lambda r:(r["a"],r["id"]))
    assigned=[];occupied=[]
    for ship in ships:
        windows=[w for w in ctx["channel_windows"] if w["id"]==ship["id"]]
        hit=first_fit(windows,pilots,ship["duration"],occupied)
        if hit:
            _,x,y,w=hit
            occupied.append((x,y))
            # 缺第三站等旁证时只能给临时窗，排程可执行但禁止自动通过，需人工复核。
            status="SCHEDULED_PROVISIONAL" if w.get("tier")!="CONFIRMED" else "SCHEDULED"
            assigned.append({"id":ship["id"],"start_s":x,"end_s":y,"status":status,"line":ship["line"],
                             "tier":w.get("tier"),"stations":w.get("stations",[]),
                             "missing":w.get("missing",[]),"evidence_lines":w.get("evidence_lines",{}),
                             "coverage_gap":w.get("coverage_gap",{})})
        else:assigned.append({"id":ship["id"],"start_s":None,"end_s":None,"status":"NO_SAFE_SLOT","line":ship["line"],
                              "tier":"NONE","stations":[],"missing":list(ALL_STATIONS),
                              "evidence_lines":{},"coverage_gap":{"ALL":"无满足阈值的安全时段"}})
    ctx["assigned"]=assigned
    return report(assigned,已排=sum(r["status"].startswith("SCHEDULED") for r in assigned),
                  确认排程=sum(r["status"]=="SCHEDULED" for r in assigned),
                  临时排程=sum(r["status"]=="SCHEDULED_PROVISIONAL" for r in assigned),
                  待排=sum(r["status"]!="SCHEDULED" and r["status"]!="SCHEDULED_PROVISIONAL" for r in assigned))
