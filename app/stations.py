# 验潮站登记：站点编号、名称、相对外海站的名义潮时差（秒）。
# 外海站 OFFSHORE 为基准（lag_s=0）；内港站 HARBOR 潮时差半小时（1800 秒）。
# 第三站 OUTER_ANCHOR 为锚地旁证站，未回传时窗口只能降级为临时窗。
from dataclasses import dataclass


@dataclass(frozen=True)
class Station:
    code: str
    name: str
    lag_s: int
    required: bool  # 安全窗 CONFIRMED 级别是否必须回传


REGISTRY = {
    "OFFSHORE": Station("OFFSHORE", "外海验潮站", 0, True),
    "HARBOR": Station("HARBOR", "内港验潮站", 1800, True),
    "OUTER_ANCHOR": Station("OUTER_ANCHOR", "第三站（锚地）", 0, False),
}

# 两个必备站齐备才能给出确认窗；缺第三站仅降级不阻断。
CONFIRMATION_STATIONS = tuple(s.code for s in REGISTRY.values() if s.required)
ALL_STATIONS = tuple(REGISTRY.keys())
# 实测潮时差与名义值偏差超过该阈值（秒）时在采信时间轴上标注。
LAG_TOLERANCE_S = 300
MAX_INTERP_GAP_S = 10800


def get(code):
    return REGISTRY.get(code)
