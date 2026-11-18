# TRAP-11
# TRAP-07
# TRAP-06
from app.modules.m2_vessels.rules import *
from app.errors import BusinessError
from app.numbers import number
from decimal import Decimal
import pytest

def test_vessel_unit():
    assert depth("１,０００","cm")==10

def test_vessel_timezone():
    assert instant("2026-11-18T08:00:00+08:00")==instant("2026-11-18T00:00:00Z")

def test_vessel_naive():
    with pytest.raises(BusinessError):instant("2026-11-18T00:00:00")

def test_vessel_missing():
    with pytest.raises(BusinessError):depth("N/A","m")

def test_vessel_unknown_unit():
    with pytest.raises(BusinessError):depth("10","ft")

def test_vessel_sample(result):
    assert sum(r["kind"]=="ship" for r in result["effective"])==4

def test_vessel_late(result):
    assert len(result["normalized"])==116
def test_conflicting_same_time_tides_cannot_open_window():
    from app.pipeline import run
    data='id,station,kind,start,end,value,aux,version,unit\nT1,OFFSHORE,tide,2026-11-18T00:00:00Z,,1,,1,m\nT2,OFFSHORE,tide,2026-11-18T00:00:00Z,,3,,1,m\nT3,OFFSHORE,tide,2026-11-18T01:00:00Z,,3,,1,m\nS1,,ship,2026-11-18T00:00:00Z,2026-11-18T01:00:00Z,10,30,1,m\nP1,,pilot,2026-11-18T00:00:00Z,2026-11-18T01:00:00Z,0,,1,m\n'
    r=run(data)
    assert r['assigned'][0]['status']=='NO_SAFE_SLOT'
    assert sum(x['reason']=='TIDE_TIME_CONFLICT' for x in r['quarantine'])==2

def test_different_stations_same_time_are_not_conflicts():
    # 跨站同一时刻读数不同是潮时差的正常现象，不得再合并成一条曲线后隔离。
    from app.pipeline import run
    data='id,station,kind,start,end,value,aux,version,unit\nT1,OFFSHORE,tide,2026-11-18T00:00:00Z,,3,,1,m\nT2,HARBOR,tide,2026-11-18T00:00:00Z,,2.4,,1,m\nT3,OFFSHORE,tide,2026-11-18T01:00:00Z,,3,,1,m\nT4,HARBOR,tide,2026-11-18T01:00:00Z,,2.4,,1,m\nS1,,ship,2026-11-18T00:00:00Z,2026-11-18T01:00:00Z,9,30,1,m\nP1,,pilot,2026-11-18T00:00:00Z,2026-11-18T01:00:00Z,0,,1,m\n'
    r=run(data)
    assert not any(x['reason']=='TIDE_TIME_CONFLICT' for x in r['quarantine'])
    # 包络取内港 2.4m，阈值 2m，窗口成立但缺第三站 -> 临时窗。
    assert r['tide_windows'] and all(w['tier']=='PROVISIONAL' for w in r['tide_windows'])
    assert r['assigned'][0]['status']=='SCHEDULED_PROVISIONAL'

def test_same_id_different_record_kinds_kept(sample):
    from app.pipeline import run
    r=run(sample.replace('P1,,pilot,','SHIP01,,pilot,'))
    assert len(r['assigned'])==4 and any(x['kind']=='pilot' for x in r['effective'])
