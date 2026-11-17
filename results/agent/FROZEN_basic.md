# Cấu hình chốt cho phần cơ bản (trước khi chạy test)

Thời điểm: 2026-11-17T11:42:49 — chưa chạy agent trên test.
Tiêu chí (công bố trước trong báo cáo): (1) Context Evidence Rate dev, (2) grounded answer + citation hợp lệ, (3) abstention / từ chối nhầm, (4) thời gian, chi phí.

| Dev (17 câu, gpt-4o-mini qua OpenRouter) | base | hybrid_b2400 |
|---|---|---|
| Context Evidence Rate | 3/15 | 9/15 |
| Grounded answer trung bình /2 | 0.47 | 1.33 |
| Citation hỗ trợ | 5/7 | 19/23 |
| Từ chối nhầm | 8/15 | 1/15 |
| Abstention đúng | 2/2 | 2/2 |
| Trung vị / chi phí | 4.0 s / $0.0074 | 5.9 s / $0.0104 |

**Chọn: hybrid_b2400.** Chạy test cho cả baseline (base) và cấu hình chọn.
