import csv,io,json

def _w(writer,section,rows,header):
    writer.writerow([f"# {section}"])
    writer.writerow(header)
    for r in rows:writer.writerow([r.get(k,"") for k in header])
    writer.writerow([])

def evidence_csv(run):
    out=io.StringIO();writer=csv.writer(out)
    res=run["result"]
    writer.writerow(["run_id","sha256","rule_version","section","line","reason","evidence"])
    writer.writerow([run["id"],run["digest"],run["rule_version"],"manifest","","",
                     json.dumps({"balance":res["balance"],"decision":run["decision"],"revision":run["revision"],
                                 "invalidated_by":run.get("invalidated_by",[]),"invalidates":run.get("invalidates",[])},
                                ensure_ascii=False)])
    writer.writerow([])

    # 1) 窗口采信明细：每条安全窗采信了哪些站、缺什么旁证、来源到原始行号与读数。
    window_rows=[]
    for w in res.get("tide_windows",[]):
        window_rows.append({
            "ship_id":w.get("id"),"start_s":w.get("start_s"),"end_s":w.get("end_s"),
            "tier":w.get("tier"),"threshold_m":w.get("threshold_m"),"envelope_m":w.get("envelope_m"),
            "trusted_stations":";".join(w.get("stations",[])),
            "missing_corroboration":";".join(w.get("missing",[])),
            "station_source_lines":json.dumps(w.get("evidence_lines",{}),ensure_ascii=False),
            "gap_reason":json.dumps(w.get("coverage_gap",{}),ensure_ascii=False),
            "input_line":w.get("line","")})
    _w(writer,"安全窗采信明细（可追站点与原始行号）",window_rows,
       ["ship_id","start_s","end_s","tier","threshold_m","envelope_m","trusted_stations","missing_corroboration","station_source_lines","gap_reason","input_line"])

    # 2) 逐时刻采信时间轴：每个半小时点采信站、缺证站、包络水深。
    _w(writer,"逐时刻采信与缺证时间轴",res.get("coverage_timeline",[]),
       ["t_s","stations","missing","envelope_m","tier","lines"])

    # 3) 潮时差核对：外海/内港高/低潮转折点实测滞后与名义半小时偏差。
    _w(writer,"内外港潮时差核对",res.get("lag_check",[]),
       ["feature","offshore_t_s","harbor_t_s","offshore_line","harbor_line","height_m","nominal_lag_s","observed_lag_s","deviation_s","within_tolerance"])

    # 4) 读数更正与失效链。
    _w(writer,"读数更正记录",res.get("tide_corrections",[]),
       ["station","t_s","time","id","superseded_versions","effective_version","value_m","status","line"])
    link_rows=[{"relation":"被取代","ref":x["successor_id"],"reason":x["reason"],"created":x["created"]} for x in run.get("invalidated_by",[])]
    link_rows+=[{"relation":"取代旧批次","ref":x["predecessor_id"],"reason":x["reason"],"created":x["created"]} for x in run.get("invalidates",[])]
    _w(writer,"批次失效链",link_rows,["relation","ref","reason","created"])

    # 5) 排程结果与隔离记录（保留原证据）。
    _w(writer,"排程结果",res.get("final",[]),
       ["id","start_s","end_s","start","end","status","tier","stations","missing","check","line"])
    quarantine_rows=[dict(line=q.get("line",""),reason=q.get("reason",""),payload=json.dumps(q,ensure_ascii=False)) for q in res.get("quarantine",[])]
    _w(writer,"隔离记录",quarantine_rows,["line","reason","payload"])
    return "﻿"+out.getvalue()
