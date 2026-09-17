# SeatBond

影院连座锁座：按场次厅图查找连续空座，过道列断开，冲突检测既有持座。支持情侣座成对编排：同排相邻两列绑定成对，锁座整对写入、搜索整对纳入或整对跳过，人数落单只剩半对时以可区分原因失败。

## 情侣对规则

- 一对绑定同排相邻两列（`start_col`、`start_col+1`），不得跨过道列登记，不得与既有对重叠。
- 连座搜索落窗若会切开某对，则整段跳过该对另寻他段，绝不只写半对。
- 失败原因可区分：`kind=half_pair`（只剩半对可落座）vs `kind=no_contiguous`（普通连续空座不足）vs `kind=overlap`（持座重叠）。
- 锁座单持久化 `couple_cols`（本单纳入的情侣对起始列），订单/票根/锁座结果均可见。

接口：`GET/POST /api/halls/{id}/pairs`、`PUT/DELETE /api/pairs/{id}`；影厅页内联编排，座位图金框标出成对格子。

种子：情侣厅（1×6 无过道）第1排 3-4 列为情侣对，左右各有空座；人数 3 触发半对失败，人数 4 整对纳入成功。一号厅第6排 9-10 亦有一对，SB-1004 为整对持座示范单。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4100 |
| API | http://localhost:9100 |
| API 文档 | http://localhost:9100/docs |
| Postgres | localhost:5442 |

健康检查：`GET http://localhost:9100/api/health`

## 页面

- `/halls` — 影厅
- `/showtimes` — 场次
- `/seatmap` — 座位图（大网格热力）
- `/hold` — 锁座
- `/orders` — 订单
- `/conflicts` — 冲突

## 使用说明

1. 在影厅与场次页确认厅图与排期。
2. 打开座位图查看占用热力，在锁座页输入连座人数并提交。
3. 订单页查看持座结果；冲突页查看重叠请求。

## 开发与测试

```bash
docker compose exec api pytest -q
```
