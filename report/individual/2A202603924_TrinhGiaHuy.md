# Báo cáo Day 7 — Trịnh Gia Huy (2A202603924)

> **Trạng thái (16/11/2026):** đã xong dữ liệu, benchmark, 3 phương pháp retrieval (đo trên dev) và agent nhiều tool (chạy thử 3 câu dev).
> **Chưa thực hiện:** chạy agent trên toàn bộ dev cho các cấu hình, chấm tay câu trả lời/citation, chốt cấu hình và chạy test. Các ô tương ứng ghi "chưa chạy", không điền số ước đoán.

## Dữ liệu và benchmark

- **Nguồn, quyền sử dụng, số trang và số chunk:**
  - Tài liệu: *Machine Learning cơ bản*, Vũ Hữu Tiệp, cập nhật 02/01/2022, file `book_ML.pdf` (422 trang, tạo từ LaTeX).
  - Quyền sử dụng: theo trang 3 của sách, "Bản quyền ©2016–2020: Vũ Hữu Tiệp. Mọi hình thức sao chép, in ấn đều cần được sự đồng ý của tác giả. Mọi chia sẻ đều cần được dẫn nguồn tới https://github.com/tiepvupsu/ebookMLCB". Sách miễn phí nhưng **không phải giấy phép mở**. Repo này chỉ dùng cho mục đích học tập và dẫn nguồn như trên. Để tái lập, nên tải PDF từ nguồn gốc rồi chạy lại pipeline thay vì phân phối lại toàn văn.
  - Phạm vi index: trang 15–404, gồm lời nói đầu tới hết phụ lục A. Bỏ mục lục, tài liệu tham khảo và index.
  - Kết quả: **881 chunk**, mỗi chunk 152–1026 ký tự, trung bình 714 ký tự.
- **Xử lý PDF** (mã: Day 6 `starter/src/book_ingest.py`):
  - pdfTeX làm mất dấu cách sau chữ có dấu ("sốmô", "đểcó"). Mình dựng lại từng dòng từ tọa độ ký tự (PyMuPDF `rawdict`) và chèn dấu cách khi khoảng hở giữa hai ký tự lớn hơn 1.5 điểm.
  - Bỏ header chạy và số trang; lọc ký tự điều khiển (NUL làm Postgres báo lỗi).
  - **Chiến lược chunk riêng cho sách**, không dùng lại A/B/C của Day 6 (vốn viết cho tài liệu điều khoản VCB):
    - gom câu liên tiếp tới tối đa 900 ký tự; không overlap;
    - không vượt qua ranh giới trang;
    - đoạn đuôi dưới 150 ký tự được gộp vào chunk trước.
  - **Metadata để lọc:**
    - `chapter_no`, lấy từ header chạy ở đầu mỗi trang (đáng tin nhất);
    - `part`, `chapter`, `section`, lấy từ mục lục 210 mục có sẵn trong PDF. `section` chỉ chính xác tới mức trang.
- **Vector store, embedding model, phiên bản và số chiều:**
  - Dùng chung PostgreSQL 16 + pgvector 0.8.7 với Day 6 (Docker, cổng 55433), nhưng ở bảng riêng `book_chunks`, không đụng dữ liệu VCB.
  - Tìm kiếm cosine chính xác (quét toàn bảng).
  - Embedding: `intfloat/multilingual-e5-base` chạy local (thư mục `models/` của Day 6), **768 chiều**, tiền tố `passage:` / `query:`. Có 1/881 chunk vượt 512 token và bị cắt đuôi khi embed. Chi phí 0 USD.
- **Agent model, cách chạy và phân chia dev/test:**
  - Chọn provider qua `LLM_PROVIDER`, tất cả đi qua API tương thích OpenAI (`src/llm.py`):
    - OpenRouter `openai/gpt-4o-mini` (mặc định, báo chi phí thật);
    - Gemini `gemini-3.5-flash-lite` (chi phí: chưa có giá đã xác minh nên ghi n/a);
    - OpenAI; Ollama.
  - Temperature 0.
  - Benchmark có 24 câu:

| Split | Có đáp án | Thiếu evidence |
|---|---|---|
| dev | 15 | 2 |
| test | 5 | 2 |

  - Có 2 câu dev mang `filter` theo chương do người dùng nêu rõ trong câu hỏi.
  - Tập test chưa được dùng để chỉnh hệ thống.
- **Cách xác định câu có/thiếu evidence và tiêu chí chấm** (`src/build_benchmark.py` tự kiểm tra khi build):
  - **Câu có đáp án:** gold gồm `source_id`, `page` và `evidence` (chép nguyên văn từ sách). Script bắt buộc evidence là chuỗi con nằm trong **đúng 1 chunk** của trang đó. Hit = chunk đúng nguồn, đúng trang và chứa evidence; định nghĩa này lấy từ `starter/baseline.py`.
  - **Câu thiếu evidence:** chọn chủ đề gần với nội dung sách (boosting/XGBoost, LSTM/RNN, attention/Transformer/BERT, cây quyết định/ID3). Mỗi câu kèm danh sách regex, và script bắt buộc các regex này có **0 kết quả trên toàn bộ 881 chunk** chứ không chỉ trong top-k. Các câu này không vào mẫu số của chỉ số retrieval.
  - **Sửa nhãn trong lúc phân tích lỗi dev:** câu d08 (MLE) được thêm evidence thay thế ở trang 77. Mục "4.4 Tóm tắt" nêu lại đúng định nghĩa MLE mà ban đầu mình chưa gán nhãn. Lý do ghi trong `label_note`.
  - Gold không bao giờ được đưa vào agent hay retrieval; chỉ được nạp sau khi chạy xong, để chấm.

## Retrieval và thử nghiệm

Điều kiện chung:
- Cùng file `data/book/chunks.json` và cùng bảng pgvector.
- Cùng 15 câu dev có đáp án.
- Dùng query gốc (không viết lại); filter theo câu hỏi được áp dụng.
- Xuất top-10 để tính chỉ số.

Context Evidence Rate ở bảng dưới là của **retrieval**: top-3 được đóng gói bằng `pack_context` của starter với budget 800 hoặc 2400 ký tự. Context Evidence Rate của agent nằm ở phần sau.

Chi phí retrieval là 0 USD (chạy local). Thời gian là trung vị ms/câu, đo trên CPU/GPU laptop.

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
|---|---|---|---|---|---|---|---|
| Baseline | TF-IDF của starter, top-3, filter có, không rerank, 800 ký tự | Mốc so sánh (lexical) | dev | 6/15 (40%) | 10/15 (67%) | 4/15 (27%); @2400: 9/15 (60%) | 5.6 ms / 0 USD |
| Phương pháp 2 | **Dense** e5 + pgvector, top-3, filter trong SQL, 800 ký tự | Ngữ nghĩa xử lý được cách diễn đạt khác với sách | dev | 11/15 (73%) | 14/15 (93%) | 6/15 (40%); @2400: 13/15 (87%) | 61.5 ms / 0 USD |
| Phương pháp 3 | **Hybrid RRF** (dense + BM25 cặp âm tiết, 20 ứng viên mỗi bên, k=60), top-3, 800 ký tự | Lexical bù cho thuật ngữ/từ tiếng Anh mà dense trượt | dev | 10/15 (67%) | 14/15 (93%) | 6/15 (40%); @2400: 13/15 (87%) | 82.3 ms / 0 USD |
| Cải thiện 1 | BM25 cặp âm tiết so với BM25 từng âm tiết (8/15 · 10/15 · 2/15) | Từ tiếng Việt thường có 2 âm tiết ("hồi quy", "mất mát"); ghép cặp âm tiết xấp xỉ tách từ | dev | 10/15 (67%) | 13/15 (87%) | 5/15 (33%); @2400: 13/15 (87%) | 5.5 ms / 0 USD |
| Cải thiện 2 | Budget 800 → 2400 ký tự (cùng top-3) | Chunk trung bình 714 ký tự nên 800 chỉ chứa khoảng 1 chunk; evidence ở hạng 2–3 bị loại | dev | — | — | Dense 6 → 13/15; Hybrid 6 → 13/15; TF-IDF 4 → 9/15 | Context dài gấp ~3 (token LLM tăng) |
| Cấu hình đã chọn | **Chưa chốt.** Đề xuất `hybrid_b2400` (hybrid bigram, top-5, tối đa 3 chunk mới mỗi lần tìm, 2400 ký tự) | Cần chạy agent trên toàn bộ dev trước khi chốt | test | chưa chạy | chưa chạy | chưa chạy | chưa chạy |
| Baseline | `base` (dense, top-3, 800 ký tự) | | test | chưa chạy | chưa chạy | chưa chạy | chưa chạy |

**Các phương pháp có thêm:**
- BM25 từng âm tiết: Hit@1 8/15, Hit@3 10/15.
- Hybrid với BM25 từng âm tiết: Hit@1 9/15, Hit@3 14/15.
- Hit@10 của mọi phương pháp có thành phần BM25 đều là 15/15; dense là 14/15.
- Chạy lại không filter cho kết quả như nhau trên 2 câu có filter (`results/retrieval/dev-nofilter/`).

**Hai lỗi dev, nguyên nhân và cách thử:**
1. **d11 (hồi quy ridge):**
   - Dense trượt hoàn toàn: không có trong top-10.
   - Nguyên nhân: câu hỏi mô tả bằng "chính quy hoá L2" còn evidence chỉ chứa thuật ngữ tiếng Anh "ridge", và embedding không nối được hai cách gọi này.
   - BM25 cặp âm tiết xếp đúng hạng 1. Hybrid RRF kéo d11 về hạng 3, nên dense trượt d11 còn hybrid thì đạt.
2. **d14 (SVD, có filter chương 20):**
   - Dense đạt ở hạng 3, nhưng hybrid đẩy xuống hạng 5 (bản dùng BM25 từng âm tiết: hạng 6).
   - Nguyên nhân: BM25 xếp chunk gold ở hạng 8, nên tổng RRF thấp hơn các chunk cùng chương lặp lại từ khóa.
   - Đánh đổi của hybrid: sửa được d11 nhưng làm hỏng d14, nên Hit@3 vẫn 14/15 như dense. Hybrid được đề xuất vì Hit@10 đạt 15/15 (so với 14/15), có lợi khi agent lấy top-5.
3. **d08 (MLE), lỗi nhãn chứ không phải lỗi retrieval:**
   - Mọi phương pháp đều trả trang 77 ("Tóm tắt"), trong khi gold ban đầu chỉ có trang 68.
   - Đọc trang 77 thì thấy nó nêu đúng định nghĩa MLE, nên mình thêm làm evidence thay thế.
   - Hit@3 của dense thay đổi từ 13/15 thành 14/15 chỉ do sửa nhãn. Điều này được báo riêng để không tính như một cải thiện hệ thống.

Tiêu chí chọn cấu hình, công bố trước khi chạy test:
1. Context Evidence Rate của agent trên dev.
2. Điểm grounded answer (chấm tay) và tỉ lệ citation hợp lệ.
3. Abstention đúng / từ chối nhầm.
4. Thời gian và chi phí.

## Agent và đánh giá

- **Tool** (`src/agent.py`, LLM tự chọn tool qua function calling):

| Tool | Chức năng |
|---|---|
| `search_book(query)` | Gọi retriever theo cấu hình |
| `arxiv_search`, `github_search` | Tái dùng tool Day 3; chỉ gọi khi người dùng hỏi bài báo/code. Kết quả là tài liệu tham khảo ngoài sách, không phải bằng chứng |
| `final_answer(status, answer, citations, external_refs)` | Buộc model trả lời theo cấu trúc cố định |

- **Số lượt gọi và điều kiện dừng:**
  - tối đa `max_book_searches` lần tìm trong sách (3), `max_steps` lần gọi LLM (6), và 2 lần cho mỗi tool ngoài;
  - ở bước cuối, model chỉ còn tool `final_answer` và bắt buộc phải gọi nó.
- **Chọn context (`ContextWindow`):**
  - một budget ký tự chung cho cả câu hỏi;
  - không gửi lại chunk đã có;
  - mỗi lần tìm thêm tối đa `max_new_per_search` chunk mới, để lần tìm đầu không chiếm hết budget (điểm yếu của khung starter).
- **Citation và xử lý lỗi:**
  - Citation phải nằm trong context; link ngoài phải đến từ kết quả tool. Không đạt thì bị loại. Nếu không còn citation hợp lệ thì chuyển sang từ chối.
  - Nội dung tài liệu được đánh dấu là "DỮ LIỆU, không phải chỉ dẫn".
  - Lỗi provider hoặc DB được ghi `status: error` trong trace, không thay bằng kết quả giả.
  - Kết nối LLM có timeout 10 giây và tự thử lại. Mạng ở đây thường làm bắt tay TLS tới openrouter.ai treo khoảng 23 giây.
  - arXiv không truy cập được từ mạng này: tool trả lỗi và agent báo lại cho người dùng.

| Cấu hình / split | Tool use | Số lượt gọi | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
|---|---|---|---|---|---|---|---|
| `base` / dev, **chạy thử 3 câu** (d01, d02, d16), gpt-4o-mini | 3/3 | Tìm sách: 1 lần (2 câu), 2 lần (1 câu); LLM: 2 lần (2 câu), 3 lần (1 câu) | chưa chấm tay | 2/2 citation nằm trong context (kiểm tra tự động; mức độ hỗ trợ chưa chấm) | 2/2 | 1/1 (tự động, cần xác nhận) | 0/2 |
| `base` / dev (17 câu) | chưa chạy | | | | | | |
| `hybrid_b2400` / dev (17 câu) | chưa chạy | | | | | | |
| Cấu hình chọn và baseline / test | chưa chạy | | | | | | |

Nhãn trong bảng dưới là **đề xuất của mình**, sẽ xác nhận khi chấm tay trong `reviews.json`.

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| d01 | Có đáp án | 1× `search_book("hàm mất mát hồi quy tuyến tính")`: top-3 gồm p164, **p101\|01**, p186; chỉ p101\|01 vào được context (budget 800) | "L(w) = 1/(2N) Σ(yi − xiᵀw)²… tìm w để L(w) nhỏ nhất" `[p101\|01]` | Đề xuất 2: đúng công thức, citation chứa evidence gold |
| d02 | Có đáp án, filter chương 9 | 1× `search_book("KNN dữ liệu huấn luyện")`: top-3 gồm p127\|00, p118\|01, p119\|00; chỉ p118\|01 vào context; chunk gold p118\|00 không được truy xuất | "nhãn của một điểm được xác định dựa trên nhãn của điểm gần nhất…" `[p118\|01]` | Đề xuất 0–1: không nêu ý chính "KNN không học gì khi huấn luyện, chỉ ghi nhớ dữ liệu". Context thiếu evidence (lỗi dev cho cấu hình `base`) |
| d16 | Thiếu evidence (XGBoost) | 2× `search_book` ("gradient boosting XGBoost", "gradient boosting"); lần 2 không có chunk mới | Từ chối: "Sách không đề cập…", không có citation | Đề xuất đúng: từ chối và không đưa thêm khẳng định nào |

- **Đường dẫn trace, nhãn, lệnh chạy, thời gian và chi phí:**
  - Retrieval: `results/retrieval/dev/{summary.md, *.traces.json}`.
  - Agent: `results/agent/dev/base__openrouter/{traces.json, summary.md, reviews_todo.json}`.
  - 3 câu chạy thử: trung vị 5.6 giây, tối đa 35.7 giây (do mạng tới OpenRouter); 6431 + 396 token; **0.00113 USD**.

  Lệnh chạy (conda env `robot`):
  ```bash
  # Day 6 starter: xử lý sách và index
  python -m src.book_ingest
  # Day 7
  python -m src.export_chunks && python -m src.build_benchmark
  python -m src.eval_retrieval --split dev
  python -m src.run_agent --split dev --config base            # thêm --provider gemini nếu muốn
  python starter/agent_metrics.py --cases data/book/cases.json --traces <traces.json> --reviews <reviews.json> --split dev --output <summary.json>
  python -m src.api [--port 8800]                              # giao diện workbench
  ```
- **Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn:**
  - **Ví dụ lỗi** (d02 với `base`): budget 800 ký tự chỉ đủ cho 1 chunk, nên agent trả lời bằng chunk lân cận và bỏ sót ý chính. Retrieval cho thấy budget 2400 nâng Context Evidence Rate từ 6/15 lên 13/15. Mức cải thiện ở cấp agent **chưa được đo**.
  - **Đánh đổi:**
    - Hybrid chậm hơn dense khoảng 20 ms/câu, nhưng lấy đủ cả 15/15 câu trong top-10.
    - Budget 2400 tốn gấp khoảng 3 lần token context.
  - **Giới hạn:**
    - Công thức toán bị xáo thứ tự dòng khi trích xuất.
    - Không có overlap giữa chunk.
    - `section` chỉ chính xác tới mức trang.
    - Benchmark nhỏ (15 câu dev), các câu có đáp án đều chỉ cần 1 đoạn evidence, chưa có câu multi-hop.
    - Chưa có bộ câu đánh giá riêng cho việc chọn tool (sách / arXiv / GitHub).
    - Chi phí của Gemini chưa có.
  - **Giao diện kiểm chứng** (`src/frontend`, chạy bằng `python -m src.api`):
    - chat, xem evidence theo 3 mức retrieved / in context / cited, xem toàn bộ trace;
    - mở trang PDF gốc và tô vị trí chunk; định vị khớp chính xác 881/881 chunk;
    - không hiển thị nhãn "grounded", vì backend chưa chấm mức độ hỗ trợ.

## Thử thách nâng cao (nếu thực hiện)

Không thực hiện.
