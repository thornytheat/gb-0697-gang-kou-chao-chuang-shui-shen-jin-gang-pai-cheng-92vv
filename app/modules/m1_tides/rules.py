from app.reader import read_rows
from app.report import report,quarantine
FIELDS="id station kind start end value aux version unit".split()
def apply(ctx):
    rows,bad,blank=read_rows(ctx["text"],FIELDS);ctx["quarantine"].extend(bad);ctx["blank_rows"]=blank;ctx["input_count"]=len(rows)+len(bad)+blank
    kept=[];seen=set()
    for r in rows:
        # 同一站点、同一记录号、同一版本重复才算冲突；不同站点各自独立成线。
        key=(r["station"],r["kind"],r["id"],r["version"])
        if not r["id"]:quarantine(ctx,r,"ID_REQUIRED");continue
        if key in seen:quarantine(ctx,r,"KEY_CONFLICT");continue
        seen.add(key);kept.append(r)
    ctx["raw"]=kept;return report(kept,接收=len(kept),隔离=len(ctx["quarantine"]))
