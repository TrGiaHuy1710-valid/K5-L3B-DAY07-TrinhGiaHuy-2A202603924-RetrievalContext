# Báo cáo Day 7 — Trịnh Gia Huy (2A202603924)

> **Trạng thái (17/11/2026): đã hoàn thành phần cơ bản.**
> - Dữ liệu, benchmark, 6 phương pháp retrieval (dev và test).
> - Agent chạy đủ dev với 2 cấu hình, chấm tay, chốt `hybrid_b2400` **trước** khi chạy test.
> - Test agent: grounded answer 1.6/2 (baseline 1.0/2), citation hỗ trợ 8/8, từ chối đúng 2/2, không từ chối nhầm.
>
> **Thử thách nâng cao:** chưa đạt ngưỡng 90% (test v1 26/30 = 86.67%; test_v2 độc lập 25/30 = 83.33%).

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
  - Tập test không được dùng để chỉnh hệ thống; chỉ chạy một lần sau khi chốt cấu hình (`results/agent/FROZEN_basic.md`).
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
| Cấu hình đã chọn | `hybrid_b2400`: Hybrid RRF (dense + BM25 cặp âm tiết), top-5 cho agent, tối đa 3 chunk mới mỗi lần tìm, 2400 ký tự | Chọn trên dev theo tiêu chí bên dưới (agent: Context Evidence Rate 9/15 so với 3/15) | test | 4/5 (80%) | 4/5 (80%) | Retrieval @2400: 4/5; **agent: 4/5** | 63.9 ms / 0 USD (agent: 10.2 giây/câu, $0.0044 cho 7 câu) |
| Baseline | `base`: dense, top-3, 800 ký tự | | test | 3/5 (60%) | 4/5 (80%) | Retrieval @800: 2/5; **agent: 1/5** | 66.1 ms / 0 USD (agent: 6.1 giây/câu, $0.0032 cho 7 câu) |

**Retrieval trên test** (`results/retrieval/test/summary.md`, chạy sau khi chốt):

| Phương pháp | Hit@1 | Evidence Hit@3 | Hit@10 | MRR | Context @800 / @2400 |
|---|---|---|---|---|---|
| TF-IDF | 2/5 | 2/5 | 2/5 | 0.40 | 1/5 / 2/5 |
| BM25 | 2/5 | 4/5 | 5/5 | 0.60 | 2/5 / 4/5 |
| BM25 cặp âm tiết | 4/5 | **5/5** | 5/5 | **0.87** | 2/5 / 4/5 |
| Dense | 3/5 | 4/5 | 4/5 | 0.70 | 2/5 / 4/5 |
| Hybrid | 3/5 | 4/5 | 4/5 | 0.70 | 2/5 / 4/5 |
| Hybrid cặp âm tiết | 4/5 | 4/5 | 4/5 | 0.80 | 2/5 / 4/5 |

- Câu duy nhất các phương pháp có thành phần dense đều trượt là **t02** (định nghĩa hàm hạt nhân). Chunk gold ở trang 381 nằm giữa công thức, và dense xếp các chunk "hạt nhân tuyến tính / Mercer" lên trên.
- Trên test, BM25 cặp âm tiết tốt hơn hybrid. Với chỉ 5 câu, khác biệt 1 câu chưa đủ để kết luận; cấu hình đã chốt **không** được đổi sau khi thấy kết quả test.

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
| `base` / dev (17 câu) | 17/17 | Tìm sách: 1 lần (8 câu), 2 lần (5), 3 lần (4); LLM: 2–5 lần | 0: 11, 1: 1, 2: 3 → **0.47** | 5/7 | 7/7 câu trả lời | 2/2 | **8/15** |
| `hybrid_b2400` / dev (17 câu) | 17/17 | Tìm sách: 1 lần (14), 2 lần (2), 3 lần (1); LLM: 2–4 lần | 0: 5, 1: 0, 2: 10 → **1.33** | 19/23 | 14/14 | 2/2 | 1/15 |
| `base` (baseline) / test (7 câu) | 7/7 | Tìm sách: 1 lần (3), 2 lần (2), 3 lần (2) | 0: 2, 1: 1, 2: 2 → **1.0** | 3/3 | 3/3 | 2/2 | 2/5 |
| **`hybrid_b2400` (đã chọn) / test** | 7/7 | Tìm sách: 1 lần (5), 2 lần (1), 3 lần (1) | 0: 1, 1: 0, 2: 4 → **1.6** | **8/8** | 5/5 | 2/2 | **0/5** |

Ghi chú về các con số:
- Tổng hợp bằng `starter/agent_metrics.py`; nhãn nằm trong `reviews.json` của từng thư mục kết quả.
- Model: `openai/gpt-4o-mini` qua OpenRouter, temperature 0.
- Câu trả lời đúng nhưng context không chứa evidence được chấm **0** ("thiếu evidence" theo BENCHMARK.md), ví dụ `base` d06 và `hybrid_b2400` d04, d12.

**Chấm context trên test** (0 = không có evidence; 1 = có nhưng thiếu điều kiện/nguồn; 2 = đủ evidence và nguồn):

| Cấu hình | Điểm 0 | Điểm 1 | Điểm 2 | Câu |
|---|---|---|---|---|
| `base` | 2 | 1 | 2 | t02, t04: context rỗng hoặc không liên quan (budget 800 không nhận thêm chunk); t03: chỉ có p219\|02 ("huấn luyện nhanh hơn rất nhiều"), thiếu câu về đồ thị trang 220; t01 (evidence thay thế ở trang 402), t05 |
| `hybrid_b2400` | 1 | 0 | 4 | t02: chunk gold trang 381 không được truy xuất; t01, t03, t04, t05 đủ |

**Từng câu test của cấu hình đã chọn** (`hybrid_b2400`), cùng một ví dụ lỗi của baseline:

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| t01 | Có đáp án | 1× `search_book("phương pháp nhân tử Lagrange")`: thêm p338\|01, p402\|00, p402\|01 | ∇ₓL = ∇f₀ + λ∇f₁ = 0 và f₁(x) = 0 `[p338\|01]` | 2: đúng, đủ; citation chứa evidence |
| t02 | Có đáp án | 2× `search_book` ("hàm hạt nhân kernel SVM", "kernel function definition SVM"): thêm p382\|01, p378\|01; lần 2 không có chunk mới | Mô tả "phép biến đổi sang không gian mới", ví dụ hạt nhân tuyến tính k = xᵀz `[p382\|01][p378\|01]` | 0: thiếu định nghĩa k(x, z) = Φ(x)ᵀΦ(z); 2 citation đúng với ý được viết; chunk gold trang 381 không được truy xuất |
| t03 | Có đáp án | 1× `search_book("ReLU tanh")`: thêm p220\|00, p219\|02, p219\|01 | "hàm mất mát giảm rất nhanh sau vài epoch đầu" + ý phụ `[p220\|00][p219\|02][p219\|01]` | 2: đúng; 3/3 citation hỗ trợ |
| t04 | Có đáp án | 1× `search_book("tối ưu mạng neuron đa tầng")`: thêm p216\|01, p220\|01 | Gradient descent, tính ∇W⁽ˡ⁾J và ∇b⁽ˡ⁾J `[p220\|01]` | 2: đúng |
| t05 | Có đáp án | 1× `search_book("đánh giá mô hình trên tập xác thực quá nhỏ")`: thêm p111\|00, p112\|02, p081\|02 | Thiên lệch; giải pháp xác thực chéo `[p112\|02]` | 2: đúng |
| t06 | Thiếu evidence | 1× `search_book("self-attention Transformer BERT")`: 3 chunk không liên quan | "Sách không đề cập…", không citation | Đúng: từ chối, không thêm khẳng định |
| t07 | Thiếu evidence | 3× `search_book` (tiếng Việt và tiếng Anh về ID3 / information gain); lần 2–3 không có chunk mới | "Sách không đề cập…", không citation | Đúng |
| t04 (`base`) | Có đáp án, ví dụ lỗi | 3× `search_book`; budget 800 chỉ nhận p388\|01 (không liên quan) | "Sách không đề cập…" | 0: **từ chối nhầm** vì context quá nhỏ; cùng câu này `hybrid_b2400` đạt 2 |

- **Đường dẫn trace, nhãn, lệnh chạy, thời gian và chi phí:**
  - Retrieval: `results/retrieval/{dev,test}/{summary.md, *.traces.json}`.
  - Agent: `results/agent/{dev,test}/{base,hybrid_b2400}__openrouter/`, gồm:
    - `traces.json`: tool call, tham số, kết quả, context cuối, câu trả lời, citation, token, chi phí, lỗi;
    - `summary.md`: chỉ số tự động;
    - `reviews.json`: nhãn tay;
    - `agent_metrics.json`: output của `starter/agent_metrics.py`.
  - Cấu hình được chốt trước khi chạy test trong `results/agent/FROZEN_basic.md`.

| Lần chạy (gpt-4o-mini, OpenRouter) | Trung vị / tối đa | Token vào + ra | Chi phí (OpenRouter báo) |
|---|---|---|---|
| `base` dev, 17 câu | 4.0 / 16.8 giây | 43,101 + 1,966 | $0.0074 |
| `hybrid_b2400` dev, 17 câu | 5.9 / 17.6 giây | 57,458 + 4,849 | $0.0104 |
| `base` test, 7 câu | 6.1 / 27.7 giây | 18,884 + 940 | $0.0032 |
| `hybrid_b2400` test, 7 câu | 10.2 / 31.8 giây | 26,332 + 2,021 | $0.0044 |

  Thời gian tối đa cao chủ yếu do bắt tay TLS tới OpenRouter (đã có timeout và thử lại).

  Lệnh chạy (conda env `robot`):
  ```bash
  # Day 6 starter: xử lý sách và index
  python -m src.book_ingest
  # Day 7
  python -m src.export_chunks && python -m src.build_benchmark
  python -m src.eval_retrieval --split dev   # và --split test sau khi chốt
  python -m src.run_agent --split dev --config base            # thêm --provider gemini nếu muốn
  python starter/agent_metrics.py --cases data/book/cases.json --traces <traces.json> --reviews <reviews.json> --split dev --output <summary.json>
  python -m src.api [--port 8800]                              # giao diện workbench
  ```
- **Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn:**
  - **Trước/sau ở cấp agent** (`base` → `hybrid_b2400`):

| Chỉ số | Dev | Test |
|---|---|---|
| Context Evidence Rate | 3/15 → 9/15 | 1/5 → 4/5 (tự động); chấm tay điểm 2: 2/5 → 4/5 |
| Grounded answer | 0.47 → 1.33 | 1.0 → 1.6 |
| Từ chối nhầm | 8/15 → 1/15 | 2/5 → 0/5 |

    Nguyên nhân chính: budget 800 ký tự chỉ chứa khoảng 1 chunk, nên agent không có evidence và phải từ chối. Đây đúng là điểm yếu của khung starter, và đã được dự đoán ở bước retrieval (Context @800 so với @2400).
  - **Ví dụ lỗi còn lại của cấu hình chọn:**
    - d02 và t02 (định nghĩa chung trong đoạn có công thức) không được truy xuất, nên câu trả lời thiếu ý chính;
    - d04 và d12: model trả lời đúng bằng kiến thức riêng nhưng chunk được trích không chứa ý đó. Quy tắc kiểm tra "citation nằm trong context" của code **không** bắt được lỗi này; chỉ đọc tay mới phát hiện.
  - **Đánh đổi:**
    - `hybrid_b2400` tốn khoảng 1.4 lần chi phí và chậm hơn khoảng 2–4 giây/câu so với `base`, vì context lớn hơn khoảng 4 lần (khoảng 2,000 so với khoảng 500 ký tự).
    - Đổi lại, từ chối nhầm giảm mạnh và grounded answer tăng.
    - Hybrid chậm hơn dense khoảng 20 ms ở bước retrieval, không đáng kể so với thời gian gọi LLM.
  - **Giới hạn:**
    - Công thức toán bị xáo thứ tự dòng khi trích xuất.
    - Không có overlap giữa chunk.
    - `section` chỉ chính xác tới mức trang.
    - Benchmark cơ bản nhỏ (15 câu dev, 5 câu test có đáp án). Khác biệt 1 câu bằng 20 điểm phần trăm trên test, nên kết luận chỉ mang tính định hướng.
    - Các câu có đáp án của phần cơ bản đều chỉ cần 1 đoạn evidence. Multi-hop được đánh giá ở phần nâng cao.
    - Chưa có bộ câu đánh giá riêng cho việc chọn tool (sách / arXiv / GitHub); arXiv không truy cập được từ mạng hiện tại.
    - Chi phí của Gemini chưa quy ra USD (phần nâng cao ghi theo token).
    - Nhãn chấm tay do trợ lý AI gán sơ bộ, cần người chấm xác nhận.
  - **Giao diện kiểm chứng** (`src/frontend`, chạy bằng `python -m src.api`):
    - chat, xem evidence theo 3 mức retrieved / in context / cited, xem toàn bộ trace;
    - mở trang PDF gốc và tô vị trí chunk; định vị khớp chính xác 881/881 chunk;
    - không hiển thị nhãn "grounded", vì backend chưa chấm mức độ hỗ trợ.

## Thử thách nâng cao (nếu thực hiện)

> **Kết quả: CHƯA đạt ngưỡng 90% → không đủ điều kiện nhận bonus.** Không có lỗi hệ thống ở cả hai bộ test.
> - **test (v1), cấu hình `mm_hybrid_v2`:** 26/30 = 86.67%. Câu at26 có lỗi gold do mình soạn; nếu sửa nhãn thì được 27/30, nhưng con số này chỉ có được sau khi đã xem test, nên không dùng làm điểm.
> - **test_v2 (bộ mới, độc lập), cấu hình `mm_hybrid_v3`** chốt trước khi bộ test được soạn: **25/30 = 83.33%** (mục "Bộ test mới" bên dưới).

- **Tài liệu, nguồn, quyền sử dụng, số trang và phiên bản:**
  - Cùng tài liệu với phần cơ bản: *Machine Learning cơ bản* (Vũ Hữu Tiệp, bản cập nhật 02/01/2022), `book_ML.pdf`, 422 trang, nguồn https://github.com/tiepvupsu/ebookMLCB.
  - Sách miễn phí nhưng sao chép cần tác giả đồng ý. Vì vậy repo **không nộp ảnh crop** (`data/advanced/crops/` nằm trong `.gitignore`); ảnh được tái tạo chính xác bằng `python -m src.advanced.visual_extract` từ PDF gốc.
  - Sách có đủ nội dung thị giác mang thông tin:

| Loại | Ví dụ |
|---|---|
| 8 bảng có chú thích | 7.1: chiều cao/cân nặng 15 người; 14.1: giờ ôn và kết quả 20 sinh viên; 28.2: hàm hạt nhân; … |
| Biểu đồ có trục/giá trị | 8.2, 12.2–12.5, 15.4, 16.6, 20.3, 29.6, … |
| Ảnh | 10.4: chữ số 7 và giá trị pixel; 20.3: SVD ảnh |
| Sơ đồ | MLP, perceptron, SVM, AI–ML–DL |

- **Cách xử lý text, bảng, ảnh, biểu đồ; phạm vi index và phần chưa xử lý** (code trong `src/advanced/`):
  1. **Text** dùng lại index cơ bản: 881 chunk ở bảng `book_chunks`. Bảng LaTeX, nhãn trục và tiêu đề hình con vốn nằm trong lớp text của PDF nên đã có sẵn ở đây.
  2. **Phát hiện vùng thị giác** (`visual_extract.py`):
     - gộp ảnh nhúng (`get_image_info`) và cụm hình vẽ vector (`cluster_drawings`) nằm gần nhau (khoảng cách ≤ 8 điểm), để các hình con (a)(b) thành một vùng;
     - bỏ đường kẻ, hộp quá nhỏ và khung code (chữ chủ yếu thuộc font mono `VnNimbusMonoL`);
     - gắn chú thích theo bố cục của sách: chú thích "Hình" nằm **dưới/cạnh** hình, chú thích "Bảng" nằm **trên** bảng;
     - cắt vùng **từ PDF gốc** ở độ phóng 2.5×, kèm chú thích.

     Kết quả trên trang 15–404: **270 vùng**. **142/142 chú thích** được gắn (8 bảng, 134 hình), không có chú thích nào bị bỏ sót. Có 28 khung định nghĩa/định lý không chú thích được đánh dấu `text_box`: không gửi cho vision và không index lại vì text đã có.
  3. **Mô tả bằng vision** (`describe.py`): Gemini `gemini-3.5-flash-lite` mô tả từng crop thành JSON {type, title, content}:

| Loại vùng | Nội dung yêu cầu |
|---|---|
| Bảng | Chép lại dạng markdown |
| Biểu đồ | Trục, đơn vị, khoảng giá trị, chú giải, giá trị đọc được kèm chữ "xấp xỉ", xu hướng |
| Sơ đồ / ảnh | Thành phần, nhãn, quan hệ |

     Đã mô tả 242 vùng, không lỗi; 337,865 token vào và 65,674 token ra; trung vị 2.2 giây mỗi vùng; có cache theo hash của ảnh crop. **Mô tả này chỉ dùng để tìm kiếm.**
  4. **Index** (`mm_index.py`):
     - 242 **chunk hình** gồm chú thích, tên chương (từ index v2) và mô tả;
     - metadata giữ `page`, `bbox` (toạ độ PDF), `crop`, `caption_label` để truy ngược về trang gốc;
     - embed bằng **cùng e5-base** và lưu ở bảng pgvector riêng `book_visual`.
  5. **Retrieval** (`mm_retrieval.py`):
     - dense: embed truy vấn một lần, tìm ở cả 2 bảng, gộp theo cosine;
     - BM25 với cặp âm tiết trên toàn bộ text và chunk hình;
     - gộp hai danh sách bằng RRF, 30 ứng viên mỗi bên.
  6. **Agent** (`mm_agent.py`): dùng lại vòng lặp `BookAgent`, thêm tool **`inspect_visual(region_id, question)`**. Tool này gửi **ảnh gốc** của vùng (phải đã có trong context) cùng câu hỏi cụ thể cho model vision. Giá trị ô bảng, số đọc trên biểu đồ và chi tiết sơ đồ được đọc trực tiếp từ ảnh ở bước này; mô tả ở bước 3 chỉ giúp tìm ra vùng.
  - **Kiểm tra với bản gốc:**
    - mình đã đọc đối chiếu crop của mọi vùng dùng trong benchmark;
    - riêng Bảng 7.1, Gemini chép đúng 15/15 hàng;
    - mô tả Hình 8.2 đúng trục và xu hướng, giá trị xấp xỉ hợp lý;
    - lỗi gắn chú thích ở hình xếp chồng (12.2/12.3, 12.4/12.5) được phát hiện khi xem crop và đã sửa bằng quy tắc theo hướng.
  - **Phần chưa xử lý / giới hạn:**
    - công thức trong text bị xáo thứ tự dòng;
    - 27/242 chunk hình dài hơn 512 token nên phần đuôi không được embed (BM25 vẫn thấy);
    - hình bên lề có thể dính một phần chữ lân cận trong crop;
    - mô tả vision không được kiểm chứng cho mọi vùng ngoài benchmark.
- **Cách chia benchmark, schema evidence, model và cấu hình đã chốt trên dev:**
  - `src/advanced/build_benchmark_adv.py` tạo `data/advanced/benchmark_adv.json`, chia dev/test **trước khi chạy**:

| Nhóm | Dev | Test |
|---|---|---|
| Bảng | 3 | 6 |
| Ảnh, sơ đồ | 3 | 5 |
| Biểu đồ | 3 | 5 |
| Multi-hop | 3 | 4 |
| Text | 3 | 4 |
| Thiếu bằng chứng | 3 | 6 |
| **Tổng** | **18** | **30** |

  - Mỗi câu có id, nhóm, câu hỏi, đáp án, lý do, phép tính và dung sai (với biểu đồ). Evidence ghi `{page, kind, ref, detail, region}`.
  - Script tự kiểm tra: evidence dạng text phải nằm nguyên văn trên trang; chú thích bảng/hình phải có đúng trên trang đó; câu thiếu bằng chứng phải có 0 kết quả regex trên các trang liên quan, kèm ghi chú đã xem hình.
  - Gold viết từ **ảnh trang gốc**, không từ mô tả của model. Agent chỉ nhận câu hỏi.
  - **Thử trên dev** (chấm tay đạt/không đạt, Gemini 3.5 flash-lite, temperature 0):

| Cấu hình (dev, 18 câu) | Đạt | Lỗi / nhận xét |
|---|---|---|
| `text_hybrid`: chỉ index text, không `inspect_visual` | 14/18 (77.8%) | ad05 thiếu 2/4 hàm trong chú giải; ad08 đọc nhầm "16 epoch"; ad06 thêm màu sai; ad12 |
| `mm_hybrid` v1: thêm chunk hình + `inspect_visual` | 16/18 (88.9%) | ad06 thêm phương án "hoặc …" không có trong nguồn; ad12 Hình 26.1 ở hạng 5 bị bỏ vì `max_new_per_search = 4` |
| **`mm_hybrid_v2`** (chốt): index v2 thêm tên chương; `max_new_per_search = 6`, budget 9000; quy tắc cấm khẳng định ngoài nguồn | **17/18 (94.4%)** | ad12 chọn Hình 26.2 thay vì 26.1 (câu dev mơ hồ) |

  - Hai câu dev được sửa trong lúc làm, có ghi `revision` trong file:
    - ad10: câu hỏi mơ hồ vì cuối chương có 2 ví dụ; đã thêm điều kiện phân biệt;
    - ad18: regex "laplac" khớp nhầm "làm mềm Laplace" nên được thu hẹp.
  - Cấu hình được chốt trong `results/advanced/FROZEN.md` (2026-11-17 10:07) **trước** khi chạy test. Test chỉ chạy một lần.

| Nhóm test | Đạt / tổng | Tỷ lệ | Lỗi / nhận xét |
|---|---|---|---|
| Bảng | 5/6 | 83.3% | at02: hiểu sai điều kiện, tính người *nặng nhất − nhẹ nhất* (23 kg) thay vì *cao nhất − thấp nhất* (19 kg) |
| Ảnh, sơ đồ | 5/5 | 100% | `inspect_visual` đọc đúng số trong ảnh (độ chính xác theo số nút ẩn, sai số SVD, pixel 254, số nút MLP) |
| Biểu đồ | 4/5 | 80% | at16: đọc giá trị của đường xác thực (≈11) thay vì đường kiểm tra (≈14) ở bậc 8 |
| Multi-hop | 3/4 | 75% | at18: đúng "đỗ" nhưng xác suất chỉ ghi "khoảng 0.9", ngoài dung sai 0.91–0.93 đã công bố, không thực hiện phép tính |
| Text | 4/4 | 100% | |
| Thiếu bằng chứng | 5/6 | 83.3% | at26: **lỗi gold**. Trang 225 có Hình 16.8 "#hidden units = 100, accuracy = 99.33%", agent trả lời đúng theo tài liệu; regex kiểm tra vắng mặt chỉ quét trang 226–231 |
| **Toàn bộ** | **26/30** | **86.67%** | Không đạt ngưỡng 90% (cần ≥ 27/30) |

**Lần chạy lặp (rerun2, 17/11/2026)** — cùng cấu hình đã chốt, cùng 30 câu test. Đây là test **đã xem**, nên lần chạy này **không phải đánh giá độc lập** và **không thay điểm chính thức**; mục đích là đo độ dao động giữa các lần chạy. Kết quả lưu ở `results/advanced/test/mm_hybrid_v2__gemini__rerun2/`.

| Nhóm | Run chính thức | Rerun2 | Câu đổi kết quả |
|---|---|---|---|
| Bảng | 5/6 | 5/6 | at02 không đạt cả hai lần. Rerun: model không gọi tool `final_answer` mà viết khối giả XML vào text, agent chuyển sang từ chối; nội dung bên trong vẫn sai (23 kg) |
| Ảnh, sơ đồ | 5/5 | 5/5 | |
| Biểu đồ | 4/5 | 5/5 | at16: không đạt → đạt (đọc ≈14) |
| Multi-hop | 3/4 | 4/4 | at18: không đạt → đạt (tính ra 0.923) |
| Text | 4/4 | 4/4 | |
| Thiếu bằng chứng | 5/6 | 4/6 | at30: đạt → không đạt (từ chối nhưng thêm khẳng định sai "sách chỉ xét η = 0.1"); at26: lỗi gold, không đạt cả hai lần |
| **Toàn bộ** | **26/30 (86.67%)** | **27/30 (90.00%)** | trung bình 26.5/30 = 88.3% |

Nhận xét:
- 25/30 câu cho cùng kết quả ở cả hai lần; 3 câu đổi kết quả (at16, at18, at30). Dù temperature = 0, Gemini flash-lite vẫn không tất định, nên hệ thống đang dao động **quanh ngưỡng 90%**.
- Lỗi ổn định nhất là **at02**: model hiểu sai điều kiện "cao nhất − thấp nhất".
- Lỗi mới về độ tin cậy khi gọi tool: model đôi khi viết lệnh gọi tool dưới dạng text thay vì gọi tool thật.
- Muốn nhận bonus một cách hợp lệ thì cần một **bộ test mới**, cộng với các cải thiện đã nêu (tool tính toán, đọc lại điều kiện câu hỏi, nhận diện lệnh gọi tool dạng text, kiểm tra thiếu bằng chứng trên toàn corpus). Đã thực hiện ở mục dưới.

### Bộ test mới (test_v2) với cấu hình v3

**Quy trình:**
1. Chỉ dùng **dev** để sửa 4 nhóm lỗi đã thấy ở test v1:
   - thêm tool `calculate`: biểu thức số học được kiểm tra bằng AST whitelist, không dùng `eval`;
   - thêm quy tắc RULE_V3: đúng đối tượng/điều kiện câu hỏi, đọc biểu đồ theo chú giải, mọi phép tính phải qua tool, không thêm khẳng định khi từ chối;
   - thêm bước nhận diện `final_answer` mà model viết dạng văn bản (khối giả XML/JSON), sau đó vẫn chạy kiểm tra citation như lời gọi tool thật.
2. Thêm 2 câu dev cần tính toán (ad19, ad20) để kiểm chứng phần sửa. Dev v3 đạt **19/20 (95%)**, chỉ không đạt ad12 (câu dev mơ hồ).
3. **Chốt** `mm_hybrid_v3` trong `results/advanced/FROZEN_v3.md` **trước khi** soạn test_v2.
4. Soạn test_v2: 30 câu mới, không trùng câu hỏi hay đáp án với dev/test v1; gold đọc từ ảnh trang gốc.
   - Nhiều câu lấy từ bảng số liệu được trình bày dưới dạng hình (Hình 17.1, 18.1 — ma trận tiện ích) và sơ đồ có số (Hình 29.3, 29.5).
   - Kiểm tra câu thiếu bằng chứng giờ quét **toàn bộ** text, chú thích và mô tả hình (`scope: all`), sửa đúng nguyên nhân lỗi gold at26. Bộ kiểm tra đã bắt được một khớp nhầm ("kb" = k·b trong công thức trang 353) và regex được sửa cho chính xác.
5. Chạy test_v2 **một lần**: `results/advanced/test2/mm_hybrid_v3__gemini/`.

| Nhóm test_v2 | Đạt / tổng | Tỷ lệ | Lỗi / nhận xét |
|---|---|---|---|
| Bảng | 5/6 | 83.3% | n03: đếm thiếu một ô "4 giờ" (bảng có hai ô 4), ra 6 thay vì 7 |
| Ảnh, sơ đồ | 3/5 | 60% | n09: không nêu số nút ẩn được vẽ (4), chỉ ghi "tuỳ ý" theo chú thích, không `inspect_visual`; n11: dùng nhầm Hình 16.10 (5 nút, 74%) dù Hình 16.8 có ở hạng 3 |
| Biểu đồ | 4/5 | 80% | n12: từ chối dù Hình 12.4 đã được truy xuất (hạng 3, lần tìm thứ 3) |
| Multi-hop | 4/4 | 100% | `calculate` được dùng; n18 (99.33 − 95.33 = 4.0), n17, n19, n20 đều đúng |
| Text | 3/4 | 75% | n21: chunk gold `p172|01` không được truy xuất sau 5 lần tìm, model kết luận sai "sách không đề cập" |
| Thiếu bằng chứng | 6/6 | 100% | Không câu nào thêm khẳng định ngoài nguồn |
| **Toàn bộ** | **25/30** | **83.33%** | Không đạt ngưỡng 90% |

**Thời gian và chi phí:** trung vị 6.8 giây/câu (tối đa 68 giây, do mạng); token 476,556 vào + 12,831 ra, cộng 24,414 cho `inspect_visual`; `calculate` được gọi 9 lần; không có lỗi hệ thống.

**Phân tích:**
- So với test v1, các lỗi suy luận đã được nhắm tới (tính toán, multi-hop, từ chối) đều được cải thiện: multi-hop 4/4, thiếu bằng chứng 6/6.
- Nhóm lỗi còn lại là **chọn và đọc đúng vùng hình**:
  - evidence đúng đã có trong kết quả tìm kiếm nhưng agent dùng hình khác (n11) hoặc không xem hình (n09, n12);
  - một lỗi retrieval thật (n21);
  - một lỗi đếm ô trùng giá trị (n03).
- Với model nhỏ (Gemini 3.5 flash-lite) làm cả agent lẫn vision, hệ thống hiện ở mức khoảng 83–90% tuỳ bộ câu và lần chạy, **chưa ổn định trên ngưỡng 90%**.
- Hướng tiếp theo, chưa làm và phải thử trên dev:
  - tự động `inspect_visual` cho vùng hình có hạng cao khi câu hỏi nhắc tới hình/bảng/biểu đồ;
  - rerank theo trùng khớp chú thích với mô tả trong câu hỏi;
  - dùng model mạnh hơn cho bước trả lời;
  - bỏ phiếu nhiều lần (self-consistency) cho câu đếm/đọc số.

- **Trace, nhãn và evidence từng câu; thời gian, chi phí, lỗi hệ thống:**
  - Đường dẫn:
    - trace: `results/advanced/test/mm_hybrid_v2__gemini/traces.json`, gồm mọi tool call và tham số, kết quả tìm kiếm, mỗi lần `inspect_visual` (câu hỏi gửi model, câu trả lời, token), context cuối, câu trả lời, citation;
    - nhãn: `labels.json`, đạt/không đạt kèm lý do đối chiếu trang/vùng gốc cho cả 30 câu;
    - điểm: `score.json`.
  - Nhãn do trợ lý AI (Claude) gán sơ bộ sau khi đọc crop và trang gốc, **cần người chấm xác nhận**. Có 3 trường hợp nhãn khác chỉ số tự động:
    - at12 trích dẫn Hình 3.4(a), cùng đồ thị beta α = β ở chương 3. Đây là evidence thay thế hợp lệ nên đạt;
    - at19 trích dẫn Hình 11.1 (minh hoạ Multinomial NB, kết luận d5 ∈ B) nên đạt;
    - 3 câu thiếu bằng chứng trả lời bằng nội dung từ chối nhưng `status = answered`. Chấm theo nội dung là đạt; nhãn trạng thái chưa ổn định.
  - **Thời gian:** test có trung vị 5.4 giây/câu, tối đa 59.1 giây (at18, do mạng). Dựng index: trích xuất vùng 45 giây, mô tả khoảng 2.5 phút (4 luồng).
  - **Token test:** 346,418 vào + 11,240 ra cho agent, cộng 21,734 cho `inspect_visual`.
  - **Chi phí:** chưa có giá đã xác minh cho `gemini-3.5-flash-lite`, nên ghi theo token. Có thể tính bằng cách đặt `LLM_PRICE_IN` / `LLM_PRICE_OUT`.
  - **Lỗi hệ thống:** 0/30.
- **Phân tích lỗi test** (không dùng để chỉnh hệ thống):
  - 3/4 câu không đạt là **lỗi suy luận của LLM nhỏ**, không phải lỗi retrieval. Cả 3 câu đều có evidence đúng trong context:
    - hiểu sai điều kiện so sánh (at02);
    - nhầm đường trên biểu đồ có 3 đường (at16);
    - không tính toán mà ước lượng (at18).
  - Hướng sửa, phải thử trên dev và cần **bộ test mới** để báo điểm lại:
    - thêm tool tính toán;
    - thêm quy tắc "nhắc lại điều kiện của câu hỏi trước khi trả lời";
    - với biểu đồ nhiều đường, hỏi `inspect_visual` theo từng đường của chú giải;
    - dùng model mạnh hơn cho bước trả lời.
  - Lỗi gold at26 cho thấy kiểm tra "thiếu bằng chứng" bằng regex theo khoảng trang là chưa đủ; cần quét toàn bộ corpus và toàn bộ chú thích.
- **Giới hạn, cách tái lập và đường dẫn benchmark:**
  ```bash
  # conda env robot; Postgres Day 6 (docker) đang chạy; GEMINI_API_KEY trong .env
  python -m src.advanced.visual_extract          # vùng + crop (data/advanced/regions.json, crops/)
  python -m src.advanced.describe --workers 4    # mô tả vision (cache data/advanced/descriptions.json)
  python -m src.advanced.mm_index                # chunk hình -> pgvector book_visual
  python -m src.advanced.build_benchmark_adv     # benchmark dev/test + tự kiểm tra
  python -m src.advanced.run_adv run --split dev  --config mm_hybrid_v2
  python -m src.advanced.run_adv run --split test --config mm_hybrid_v2
  python -m src.advanced.run_adv score --split test --config mm_hybrid_v2   # cần labels.json
  ```
  - Benchmark: `data/advanced/benchmark_adv.json`. Kết quả dev/test và nhãn nằm trong `results/advanced/`.
  - Giới hạn chính:
    - cùng một model nhỏ làm cả agent và vision;
    - kết quả có thể dao động giữa các lần chạy dù temperature = 0;
    - nhãn chưa được người chấm độc lập xác nhận;
    - chi phí chưa quy ra USD.
