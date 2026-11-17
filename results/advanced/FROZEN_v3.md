# Cấu hình chốt cho bộ test mới (test_v2)

Thời điểm chốt: 2026-11-17T10:54:16 — TRƯỚC khi soạn và chạy test_v2 (test_v2 chưa tồn tại).

- Agent config `mm_hybrid_v3` = v2 (index v2, retriever mm_hybrid, top_k 6, budget 9000, max_new 6, 5 search) + max_steps 12
  + tool `calculate` (AST an toàn) + RULE_V3 (đúng đối tượng câu hỏi, đọc biểu đồ theo chú giải, tính bằng tool, không thêm khẳng định khi từ chối)
  + khôi phục final_answer viết dạng text (vòng lặp agent chung).
- Model: Gemini `gemini-3.5-flash-lite` (agent + vision), temperature 0.
- Lý do: test_v1 lộ 4 lớp lỗi; các bản sửa chỉ được thử trên dev (thêm ad19, ad20 để kiểm chứng phần tính toán).

| Cấu hình | Dev | Ghi chú |
|---|---|---|
| mm_hybrid_v2 | 17/18 | (trước khi thêm ad19, ad20) |
| **mm_hybrid_v3** | **19/20 (95%)** | chỉ ad12 (câu dev mơ hồ) |

test_v1 (đã dùng) KHÔNG được dùng để chọn cấu hình này ngoài việc gợi ý các lớp lỗi; điểm báo cáo cho v3 chỉ lấy từ test_v2 chạy một lần.
