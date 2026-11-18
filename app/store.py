import sqlite3, json, hashlib
from datetime import datetime, timezone
from app.config import DATA_DIR, RULE_VERSION
from app.errors import BusinessError

def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"runs.sqlite", timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE, result TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, decision TEXT NOT NULL DEFAULT '待复核', created TEXT NOT NULL)")
    # 失效链：新批次（successor）因读数更正取代哪些旧批次（predecessor）。
    db.execute("CREATE TABLE IF NOT EXISTS run_links (predecessor_id TEXT NOT NULL, successor_id TEXT NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(predecessor_id, successor_id))")
    db.execute("CREATE TABLE IF NOT EXISTS corrected_obs (run_id TEXT NOT NULL, station TEXT NOT NULL, t_s TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY(run_id, station, t_s))")
    return db

def _corrected_keys(result):
    return {(c["station"],str(c["t_s"])) for c in result.get("tide_corrections",[])}

def _link_invalidations(db, ident, result, now):
    """读数更正后，凡采信过同一站点同一时刻旧读数的批次，其安全窗失效并记录链路。"""
    keys=_corrected_keys(result)
    if not keys:return []
    invalidated=[]
    for row in db.execute("SELECT id,result FROM runs WHERE id<>?",(ident,)):
        old=json.loads(row["result"])
        old_corr={(c["station"],str(c["t_s"])):c for c in old.get("tide_corrections",[])}
        touched=[]
        for station,t_s in keys:
            # 旧批次在该站该时刻有过观测（无论当时是否已是更正值），都受本次更正影响。
            if any((station,t_s)==(c["station"],str(c["t_s"])) for c in old_corr) or \
               any(str(obs.get("a"))==t_s and obs.get("station")==station for obs in old.get("effective",[]) if obs.get("kind")=="tide"):
                touched.append(f"{station}@{t_s}")
        if touched:
            db.execute("INSERT OR IGNORE INTO run_links VALUES(?,?,?,?)",(row["id"],ident,"TIDE_CORRECTION:"+";".join(sorted(touched)),now))
            db.execute("UPDATE runs SET decision='已失效-读数更正' WHERE id=?",(row["id"],))
            invalidated.append(row["id"])
    for station,t_s in sorted(keys):
        db.execute("INSERT OR IGNORE INTO corrected_obs VALUES(?,?,?,?)",
                   (ident,station,t_s,next((c["effective_version"] for c in result["tide_corrections"] if c["station"]==station and str(c["t_s"])==t_s),0)))
    return invalidated

def save(text, result):
    digest=hashlib.sha256((RULE_VERSION+"\n"+text).encode()).hexdigest()
    ident=digest[:16]
    now=datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,digest,result,created) VALUES(?,?,?,?)",(ident,digest,json.dumps(dict(result,rule_version=RULE_VERSION),ensure_ascii=False),now))
        # 同一内容重跑命中已有行，绝不产生第二条批次；仅新批次才登记失效链。
        if db.execute("SELECT changes()").fetchone()[0]:
            _link_invalidations(db,ident,result,now)
    return get(ident)

def get(ident):
    with connect() as db:
        row=db.execute("SELECT * FROM runs WHERE id=?",(ident,)).fetchone()
    if row is None: raise BusinessError("NOT_FOUND","批次不存在",404)
    item=dict(row);item["result"]=json.loads(item["result"]);item["rule_version"]=item["result"].get("rule_version","2026.11.18.1")
    item["invalidated_by"]=invalidated_by(ident)
    item["invalidates"]=invalidates(ident)
    return item

def invalidated_by(ident):
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT successor_id,reason,created FROM run_links WHERE predecessor_id=? ORDER BY created",(ident,))]

def invalidates(ident):
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT predecessor_id,reason,created FROM run_links WHERE successor_id=? ORDER BY predecessor_id",(ident,))]

def history():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id,revision,decision,created FROM runs ORDER BY created DESC LIMIT 40")]

def review(ident,revision,decision):
    if not isinstance(decision,str) or decision not in {"通过","退回"}: raise BusinessError("DECISION","复核决定无效")
    current=get(ident)
    if decision=="通过" and current["result"].get("blocked"):
        raise BusinessError("BLOCKED","存在阻断项（含临时窗/无安全窗），请先修正数据或人工复核",409)
    with connect() as db:
        changed=db.execute("UPDATE runs SET revision=revision+1,decision=? WHERE id=? AND revision=?",(decision,ident,revision)).rowcount
        if not changed: raise BusinessError("STALE","版本已更新，请刷新",409)
    return get(ident)
