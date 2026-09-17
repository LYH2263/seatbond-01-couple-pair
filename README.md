# SeatBond

影院连座锁座：按场次厅图查找连续空座，过道列断开，冲突检测既有持座。支持情侣对登记：成对座位必须整对锁座、整对跳过，不可拆占。

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

1. 在影厅与场次页确认厅图与排期；影厅页可维护情侣对（同排相邻两列，不得跨过道）。
2. 打开座位图查看占用热力（♥ 标记情侣对格子），在锁座页输入连座人数并提交。
3. 订单页查看持座结果（含情侣对列号）；冲突页查看重叠请求，「半对占用」与普通连续空座不足为可区分的失败原因。

种子数据含「情侣厅」（单排 9 座，5-6 列为情侣对）：半对练习场人数 5 触发半对占用失败，整对练习场人数 5 整对纳入成功。

## 开发与测试

```bash
docker compose exec api pytest -q
```
