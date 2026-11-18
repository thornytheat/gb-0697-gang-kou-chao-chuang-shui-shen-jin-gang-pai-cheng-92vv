# 多验潮站：包络采信、缺证降级、潮时差、读数更正失效链、批次幂等与证据可追溯
import os
os.environ["DATA_DIR"]="/tmp/tidal-window-pytest-stations"
import shutil
shutil.rmtree("/tmp/tidal-window-pytest-stations",ignore_errors=True)
from decimal import Decimal
from app.pipeline import run
from app import store
from app.exporter import evidence_csv
from app.errors import BusinessError
import pytest

HEADER="id,station,kind,start,end,value,aux,version,unit\n"
def _clock(total_minutes):
    h,m=divmod(total_minutes,60)
    return f"2026-11-18T{h:02d}:{m:02d}:00Z"
def tide(oid,station,hour,value,version=1):
    return f"{oid},{station},tide,{_clock(hour*60)},,{value},,{version},m\n"
def tide30(oid,station,half,v):
    return f"{oid},{station},tide,{_clock(half*30)},,{v},,1,m\n"
def ship(sid,draft=9,dur=30):
    return f"{sid},,ship,2026-11-18T00:00:00Z,2026-11-18T12:00:00Z,{draft},{dur},1,m\n"
PILOT="P1,,pilot,2026-11-18T00:00:00Z,2026-11-18T12:00:00Z,0,,1,m\n"

def two_station_text(anchor=False):
    # 外海读数系统性偏高（3m），内港偏低（2.4m）；阈值=吃水9+余量1-基准8=2m。
    text=HEADER
    for h in range(6):
        text+=tide(f"O{h}","OFFSHORE",h,3)
        text+=tide(f"H{h}","HARBOR",h,2.4)
    if anchor:
        for h in range(6):text+=tide(f"A{h}","OUTER_ANCHOR",h,2.6)
    text+=ship("S1")+PILOT
    return text

def test_envelope_uses_minimum_so_high_station_cannot_open_shallow_window():
    r=run(two_station_text(anchor=True))
    assert r["tide_windows"]
    # 若误用外海 3m 单站曲线，包络会被记成 3；这里必须取到内港的 2.4。
    assert all(Decimal(w["envelope_m"])<=Decimal("2.4") for w in r["tide_windows"])
    assert all(set(w["stations"])=={"OFFSHORE","HARBOR","OUTER_ANCHOR"} for w in r["tide_windows"])
    assert all(w["tier"]=="CONFIRMED" for w in r["tide_windows"])

def test_missing_third_station_downgrades_to_provisional_and_blocks_auto_approval():
    r=run(two_station_text(anchor=False))
    assert all(w["tier"]=="PROVISIONAL" for w in r["tide_windows"])
    assert all("OUTER_ANCHOR" in w["missing"] for w in r["tide_windows"])
    assert r["assigned"][0]["status"]=="SCHEDULED_PROVISIONAL"
    assert r["blocked"] is True
    saved=store.save(two_station_text(anchor=False),r)
    with pytest.raises(BusinessError,match="阻断"):
        store.review(saved["id"],saved["revision"],"通过")

def test_coverage_timeline_names_trusted_and_missing_stations_each_moment():
    r=run(two_station_text(anchor=False))
    points=r["coverage_timeline"]
    assert points, "逐时刻采信时间轴不能为空"
    for c in points:
        assert "OFFSHORE" in c["stations"] and "HARBOR" in c["stations"]
        assert c["missing"]==["OUTER_ANCHOR"]
        assert c["tier"]=="PROVISIONAL"
        assert set(c["lines"])=={"OFFSHORE","HARBOR"}

def test_lag_check_compares_observed_against_nominal_half_hour():
    # 含高/低潮转折点：内港高潮较外海晚 1 小时 -> 偏差超 5 分钟容差。
    text=HEADER
    off_series=[1,3,3,1,1,3]
    har_series=[1,1,3,3,1,1]   # 高潮平台整体右移一小时
    for h,v in enumerate(off_series):text+=tide(f"O{h}","OFFSHORE",h,v)
    for h,v in enumerate(har_series):text+=tide(f"H{h}","HARBOR",h,v)
    text+=ship("S1")+PILOT
    r=run(text)
    assert r["lag_check"], "潮时差核应有转折点结果"
    assert all(x["nominal_lag_s"]==1800 for x in r["lag_check"])
    highs=[x for x in r["lag_check"] if x["feature"]=="HIGH"]
    assert highs and all(x["observed_lag_s"]==3600 and not x["within_tolerance"] for x in highs)

def test_lag_check_within_tolerance_when_half_hour_shift():
    # 半小时刻度、内港滞后恰好 30 分钟 -> 容差内。
    text=HEADER
    off=[1,3,3,1,1,3];har=[1,1,3,3,1,1]   # 半小时刻度，内港整体右移一个刻度（30 分钟）
    for i,v in enumerate(off):text+=tide30(f"O{i}","OFFSHORE",i,v)
    for i,v in enumerate(har):text+=tide30(f"H{i}","HARBOR",i,v)
    text+=ship("S1")+PILOT
    r=run(text)
    highs=[x for x in r["lag_check"] if x["feature"]=="HIGH"]
    assert highs and all(x["observed_lag_s"]==1800 and x["within_tolerance"] for x in highs)

def test_rerun_same_content_keeps_single_batch():
    text=two_station_text(anchor=True)
    a=store.save(text,run(text));b=store.save(text,run(text))
    assert a["id"]==b["id"]
    assert len(store.history())>=1
    assert sum(1 for x in store.history() if x["id"]==a["id"])==1

def test_corrected_reading_invalidates_prior_batch_and_records_link():
    base=two_station_text(anchor=True)
    first=store.save(base,run(base))
    # 同一外海站同一时刻发布 v2 更正值（3 -> 1.5，落进阈值以下）。
    corrected=base+tide("O0","OFFSHORE",0,1.5,version=2)
    second=store.save(corrected,run(corrected))
    assert second["id"]!=first["id"]
    corr=second["result"]["tide_corrections"]
    assert any(c["station"]=="OFFSHORE" and c["effective_version"]==2 and c["status"]=="CORRECTED" for c in corr)
    # 旧批次被新批次标记失效，链路双向可查。
    refreshed=store.get(first["id"])
    assert refreshed["decision"]=="已失效-读数更正"
    assert any(link["successor_id"]==second["id"] for link in refreshed["invalidated_by"])
    assert any(link["predecessor_id"]==first["id"] for link in second["invalidates"])

def test_evidence_export_traces_window_to_station_lines_and_raw_values():
    saved=store.save(two_station_text(anchor=False),run(two_station_text(anchor=False)))
    csv_text=evidence_csv(saved)
    assert saved["digest"] in csv_text
    assert "安全窗采信明细" in csv_text and "逐时刻采信与缺证时间轴" in csv_text
    assert "OFFSHORE" in csv_text and "HARBOR" in csv_text and "OUTER_ANCHOR" in csv_text
    # 站点来源行是 JSON 映射，能回到 reader 保留的物理行号。
    assert "station_source_lines" in csv_text
    assert "批次失效链" in csv_text and "隔离记录" in csv_text

def test_unknown_station_is_quarantined_not_silently_merged():
    text=HEADER+tide("X1","GHOST",0,3)+tide("O0","OFFSHORE",0,3)+tide("O1","OFFSHORE",1,3)+ship("S1")+PILOT
    r=run(text)
    assert any(q["reason"]=="STATION" for q in r["quarantine"])
