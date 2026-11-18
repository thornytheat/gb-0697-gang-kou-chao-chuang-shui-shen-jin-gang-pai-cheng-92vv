# 接口

`POST /api/run`：{"text":"CSV内容"}，表头须含 `station` 列。同规则版本与输入摘要只产生一条批次（内容寻址，重跑幂等）。

`GET/POST /api/1` 至 `/api/7`：独立样例或自定义文件计算。各模块返回 report、quarantine、balance。

`POST /api/review`：id、整数 revision、decision 取通过或退回。旧版本 409；阻断项不能通过——阻断含排程冲突、无安全窗，以及缺第三站旁证的临时窗（`SCHEDULED_PROVISIONAL`）。

`GET /api/export/{id}`：多段证据 CSV（UTF-8 BOM），含：
1. manifest（对账、决策、失效链摘要）
2. 安全窗采信明细：每窗采信站、缺证站、各站来源行 `station_source_lines`、包络潮高、等级
3. 逐时刻采信与缺证时间轴
4. 内外港潮时差核对
5. 读数更正记录
6. 批次失效链（被取代 / 取代旧批次）
7. 排程结果
8. 隔离记录（含原始行内容）

`GET /api/runs`：历史；`GET /api/runs/{id}`：批次详情，含 `invalidated_by` 与 `invalidates` 双向失效链。`GET /health`：存活检查。

错误：结构/数值 422，版本冲突 409，不存在 404，文件过大 413。逐行异常进入 quarantine；未知站点为 `STATION`。
