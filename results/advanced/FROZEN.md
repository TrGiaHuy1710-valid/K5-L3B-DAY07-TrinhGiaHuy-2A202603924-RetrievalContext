# Cấu hình chốt trước khi chạy test (advanced)

Thời điểm chốt: 2026-11-17T10:07:08 — trước lần chạy test đầu tiên; test chưa được chạy/xem.

- Pipeline: index v2 (text chunks + visual chunks có tên chương), retriever `mm_hybrid` (RRF dense 2 bảng + BM25 bigram, 30 candidates).
- Agent config: `mm_hybrid_v2` (top_k 6, budget 9000 ký tự, max_new_per_search 6, max 5 lần search, max 10 bước), tool `inspect_visual`, RULE_V2.
- Model: Gemini `gemini-3.5-flash-lite` (agent + vision), temperature 0.
- Tiêu chí chọn (công bố trước): tỷ lệ đạt dev theo nhãn đọc tay; hoà thì ít lỗi hệ thống, rồi độ trễ.

| Cấu hình (dev, 18 câu) | Đạt | Lỗi chính |
|---|---|---|
| text_hybrid (không index hình, không inspect) | 14/18 (77.8%) | ad05, ad06, ad08, ad12 |
| mm_hybrid (v1) | 16/18 (88.9%) | ad06 (khẳng định thừa), ad12 (hình bị bỏ do max_new=4) |
| **mm_hybrid_v2** | **17/18 (94.4%)** | ad12 (chọn Hình 26.2 thay 26.1; câu dev mơ hồ) |
