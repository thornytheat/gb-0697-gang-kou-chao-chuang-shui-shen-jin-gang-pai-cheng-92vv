from app.report import report
from app.timeops import display

def version_changed(old,new):
    if new<=old:raise ValueError("修订版本必须递增")
    return new-old

def tide_corrections(ctx):
    """同一验潮站同一时刻出现更高版本读数，即一次读数更正；旧窗据此失效重算。"""
    groups={}
    for r in ctx["normalized"]:
        if r["kind"]!="tide":continue
        groups.setdefault((r["station"],r["a"]),[]).append(r)
    out=[]
    for (station,t),group in groups.items():
        versions=sorted({r["version_value"] for r in group})
        if len(versions)<2:continue
        latest=max(group,key=lambda r:r["version_value"])
        out.append({"station":station,"t_s":t,"time":display(t),
                    "superseded_versions":versions[:-1],"effective_version":latest["version_value"],
                    "value_m":latest["depth"],"line":latest["line"],
                    "status":"CORRECTED","id":latest["id"]})
    return sorted(out,key=lambda r:(r["t_s"],r["station"]))

def apply(ctx):
    changes=[]
    for effective in ctx["effective"]:
        older=sorted({r["version_value"] for r in ctx["normalized"] if r["kind"]==effective["kind"] and r["id"]==effective["id"] and r["version_value"]<effective["version_value"]})
        delta=version_changed(older[-1],effective["version_value"]) if older else 0
        changes.append({"id":effective["id"],"effective_version":effective["version_value"],"superseded_versions":older,"revision_delta":delta,"status":"REPLACED" if older else "INITIAL","line":effective["line"]})
    ctx["change_log"]=changes
    ctx["tide_corrections"]=tide_corrections(ctx)
    final=[]
    for r in ctx["checked"]:
        x=dict(r);x["start"]=display(r["start_s"]) if r["start_s"] is not None else "未安排";x["end"]=display(r["end_s"]) if r["end_s"] is not None else "未安排";final.append(x)
    ctx["final"]=final
    provisional=any(r["status"]=="SCHEDULED_PROVISIONAL" for r in final)
    ctx["provisional_blocked"]=provisional
    ctx["blocked"]=bool(ctx["conflicts"]) or provisional or any(r["status"]=="NO_SAFE_SLOT" for r in final)
    return report(changes,修订=sum(r["status"]=="REPLACED" for r in changes),待复核=len(final),
                  读数更正=len(ctx["tide_corrections"]),
                  结论="阻断" if ctx["blocked"] else "可复核")
