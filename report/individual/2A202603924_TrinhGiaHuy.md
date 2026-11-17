# Báo cáo Day 7 — Trịnh Gia Huy (2A202603924)

> **Trạng thái (17/11/2026):** xong dữ liệu, benchmark, 3 phương pháp retrieval (dev), agent nhiều tool và thử thách nâng cao (test 26/30 = 86.67%, chưa đạt 90%).
> **Phần cơ bản chưa thực hiện:** chạy agent trên toàn bộ dev cho các cấu hình, chấm tay câu trả lời/citation, chốt cấu hình và chạy test. Các ô tương ứng ghi "chưa chạy", không điền số ước đoán.

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

> **Kết quả chính thức: 26/30 = 86.67% trên test, CHƯA đạt ngưỡng 90%.** Không có lỗi hệ thống.
> Một câu test (at26) có **lỗi gold** do mình soạn, phát hiện khi chấm. Nếu sửa nhãn thì được 27/30 = 90.00%, nhưng con số này **chỉ có được sau khi đã xem test**, nên không dùng làm điểm chính thức (xem phân tích bên dưới).

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
- Muốn nhận bonus một cách hợp lệ thì cần một **bộ test mới**, cộng với các cải thiện đã nêu (tool tính toán, đọc lại điều kiện câu hỏi, nhận diện lệnh gọi tool dạng text, kiểm tra thiếu bằng chứng trên toàn corpus).

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
