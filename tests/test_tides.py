# TRAP-14
# TRAP-02
from app.modules.m1_tides.rules import *
from app.errors import BusinessError
from app.numbers import number
from decimal import Decimal
import pytest

def test_tides_sample(result):
    # 输入 121 行；列数不符与空行进不了 raw，重号 TO00 同站同版冲突再隔离一条。
    assert len(result["raw"])==118

def test_tides_bom(sample):
    from app.reader import read_rows
    rows,bad,blank=read_rows("\ufeff"+sample,FIELDS)
    assert rows[0]["id"]=="TO00"

def test_tides_badcols(result):
    assert any(x["reason"]=="COLUMN_COUNT" for x in result["quarantine"])

def test_tides_duplicate(result):
    assert any(x["reason"]=="KEY_CONFLICT" for x in result["quarantine"])

def test_tides_empty():
    with pytest.raises(BusinessError):read_rows("",FIELDS)

def test_tides_header():
    with pytest.raises(BusinessError):read_rows(",".join(FIELDS),FIELDS)

def test_tides_order(result):
    assert result["raw"][0]["id"]=="TO00"