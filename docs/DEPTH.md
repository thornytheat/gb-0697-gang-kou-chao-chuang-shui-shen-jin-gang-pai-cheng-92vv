# 深度登记 港口潮窗水深与进港排程

- 规模：中型
- 核心规则：潮位线性插值求达到最低水深的时刻区间，与航道占用和引航窗口求交，安全端点含义明确

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 潮位接收 | 运行潮位接收并核对证据 | `POST /api/1` | `app/modules/m1_tides/rules.py` | `tests/test_tides.py` |
| M2 船舶条件 | 运行船舶条件并核对证据 | `POST /api/2` | `app/modules/m2_vessels/rules.py` | `tests/test_vessels.py` |
| M3 水深求窗 | 运行水深求窗并核对证据 | `POST /api/3` | `app/modules/m3_windows/rules.py` | `tests/test_windows.py` |
| M4 航道冲突 | 运行航道冲突并核对证据 | `POST /api/4` | `app/modules/m4_channel/rules.py` | `tests/test_channel.py` |
| M5 引航排程 | 运行引航排程并核对证据 | `POST /api/5` | `app/modules/m5_schedule/rules.py` | `tests/test_schedule.py` |
| M6 计划对账 | 运行计划对账并核对证据 | `POST /api/6` | `app/modules/m6_balance/rules.py` | `tests/test_balance.py` |
| M7 变更复核 | 运行变更复核并核对证据 | `POST /api/7` | `app/modules/m7_changes/rules.py` | `tests/test_changes.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-02 | BOM | 静默采信错误值 | 消除BOM | `app/modules/m1_tides/rules.py` | `tests/test_tides.py::test_tides_bom` |
| TRAP-06 | 全角单位 | 静默采信错误值 | NFKC归一 | `app/modules/m2_vessels/rules.py` | `tests/test_vessels.py::test_vessel_unit` |
| TRAP-07 | 空值 | 静默采信错误值 | 隔离空值 | `app/modules/m2_vessels/rules.py` | `tests/test_vessels.py::test_vessel_missing` |
| TRAP-11 | 偏移混用 | 静默采信错误值 | 转换UTC秒 | `app/modules/m2_vessels/rules.py` | `tests/test_vessels.py::test_vessel_timezone` |
| TRAP-13 | 乱序潮位 | 静默采信错误值 | 先排序后插值 | `app/modules/m3_windows/rules.py` | `tests/test_windows.py::test_window_sample` |
| TRAP-14 | 同版冲突 | 静默采信错误值 | 同站同号同版隔离，跨站不视为冲突 | `app/modules/m1_tides/rules.py`、`app/modules/m2_vessels/rules.py` | `tests/test_tides.py::test_tides_duplicate` |
| TRAP-23 | 相邻端点 | 静默采信错误值 | 半开区间 | `app/modules/m4_channel/rules.py` | `tests/test_channel.py::test_channel_end` |
| TRAP-25 | 旧修订 | 静默采信错误值 | 拒绝陈旧版本 | `app/modules/m7_changes/rules.py` | `tests/test_changes.py::test_change_stale` |
| TRAP-31 | 两站当一条曲线 | 跨站同时刻不同值全部隔离，丢站 | 各站独立成线，跨站差异按潮时差处理 | `app/modules/m2_vessels/rules.py` | `tests/test_vessels.py::test_different_stations_same_time_are_not_conflicts` |
| TRAP-32 | 高读数站放进浅时段 | 单站曲线高估水深 | 各站包络取最小值，任一不达标不开窗 | `app/modules/m3_windows/rules.py` | `tests/test_stations.py::test_envelope_uses_minimum_so_high_station_cannot_open_shallow_window` |
| TRAP-33 | 第三站未回传 | 等齐三站错过潮窗，或无视缺证自动放行 | 降级临时窗可发船，但阻断自动通过、须人工复核 | `app/modules/m3_windows/rules.py`、`app/store.py` | `tests/test_stations.py::test_missing_third_station_downgrades_to_provisional_and_blocks_auto_approval` |
| TRAP-34 | 半小时潮时差 | 平移读数或忽视时差 | 转折点配对核对偏差，只登记不平移 | `app/modules/m3_windows/rules.py` | `tests/test_stations.py::test_lag_check_compares_observed_against_nominal_half_hour` |
| TRAP-35 | 更正后旧窗仍生效 | 旧批次继续放行 | run_links 失效链，旧批次置“已失效-读数更正” | `app/store.py` | `tests/test_stations.py::test_corrected_reading_invalidates_prior_batch_and_records_link` |
| TRAP-36 | 重跑重复建批 | 同一内容产生多批次 | 内容寻址 digest + UNIQUE，重跑幂等 | `app/store.py` | `tests/test_stations.py::test_rerun_same_content_keeps_single_batch` |

## 对账规则

输入记录=采信记录+隔离记录+空行；重复记录归隔离；算法输出另记业务单位，不冒充输入行数。金额/浓度/时长使用Decimal；证据含原始行号。

## 已知不覆盖

不支持超过2MB输入，不执行生产自动放行；异常值需人员复核。
