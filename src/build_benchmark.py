"""Build and VERIFY the Day 7 benchmark over the ML textbook (book_ML.pdf, Day 6 chunks).

Source of truth is the QUESTIONS list below. Running this script
  * checks that every gold evidence is a verbatim substring of ONE chunk on the stated page,
  * checks the split sizes (dev 15 answerable + 2 unanswerable, test 5 + 2),
  * checks that every unanswerable question really has no evidence: its `absence_check` regexes
    must match 0 chunks of the whole corpus (not only top-k),
  * writes data/book/benchmark.json (everything), questions.json (answerable, for retrieval metrics,
    same schema as starter/baseline.py) and cases.json (all 24, for starter/agent_metrics.py).

Gold never goes to the agent or to retrieval: agents get only the `question` (+ optional user `filter`).
Run from the repo root:  python -m src.build_benchmark
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "book"
DOC = "book-ml-co-ban"


def A(qid, split, question, answer, page, evidence, flt=None, alt=(), note=""):
    """`alt` = [(page, evidence), ...] alternative valid evidence (any one counts as a hit)."""
    gold = [{"source_id": DOC, "page": page, "evidence": evidence}]
    gold += [{"source_id": DOC, "page": p, "evidence": e} for p, e in alt]
    q = {"id": qid, "split": split, "question": question, "expected_answer": answer,
         "gold": gold, "answerable": True, "expected_behavior": "search_and_answer"}
    if flt:
        q["filter"] = flt
    if note:
        q["label_note"] = note
    return q


def U(qid, split, question, reason, checks):
    return {"id": qid, "split": split, "question": question, "answerable": False,
            "expected_behavior": "search_and_abstain", "absence_reason": reason, "absence_check": checks}


QUESTIONS = [
    # ------------------------------ DEV: 15 answerable ------------------------------
    A("d01", "dev", "Hàm mất mát của mô hình hồi quy tuyến tính được định nghĩa như thế nào?",
      "L(w) = 1/(2N) Σ (yi − xi^T w)², tức trung bình bình phương sai số giữa đầu ra thật và đầu ra dự đoán; cần tìm w để L(w) nhỏ nhất.",
      101, "Hàm số L(w) chính là hàm mất mát của mô hình hồi quy tuyến tính với tham số θ = w."),
    A("d02", "dev", "Trong chương 9, khi huấn luyện thuật toán K lân cận (KNN) làm gì với dữ liệu huấn luyện?",
      "Gần như không học gì, chỉ ghi nhớ máy móc toàn bộ dữ liệu huấn luyện; mọi tính toán thực hiện ở pha kiểm tra.",
      118, "Khi huấn luyện, thuật toán này gần như không học một điều gì từ dữ liệu huấn luyện mà ghi nhớ lại một cách máy móc toàn bộ dữ liệu đó.",
      {"chapter_no": "9"}),
    A("d03", "dev", "Mục đích của phân cụm K-means là gì?",
      "Phân dữ liệu (không có nhãn) thành các cụm sao cho dữ liệu trong cùng một cụm có tính chất giống nhau; đây là học không giám sát.",
      128, "Mục đích là làm thể nào để phân dữ liệu thành các cụm (cluster) khác nhau sao cho dữ liệu trong cùng một cụm có những tính chất giống nhau."),
    A("d04", "dev", "Trong naive Bayes, khi tập huấn luyện lớn thì xác suất p(c) của một nhãn được ước lượng như thế nào?",
      "Bằng MLE: tỉ lệ giữa số điểm thuộc nhãn c và số điểm trong tập huấn luyện.",
      145, "là tỉ lệ giữa số điểm thuộc nhãn c và số điểm trong tập huấn luyện"),
    A("d05", "dev", "Thế nào là hai tập dữ liệu tách biệt tuyến tính?",
      "Hai tập có thể được phân chia hoàn toàn bằng một siêu phẳng.",
      175, "Nếu hai tập dữ liệu có thể được phân chia hoàn toàn bằng một siêu phẳng, ta nói rằng hai tập đó tách biệt tuyến tính (linearly separable)."),
    A("d06", "dev", "Hàm sigmoid nhận giá trị trong khoảng nào?",
      "Là hàm liên tục, bị chặn trong khoảng (0, 1).",
      187, "Là các hàm số liên tục nhận giá trị thực, bị chặn trong khoảng (0, 1)."),
    A("d07", "dev", "Các đầu ra của mô hình hồi quy softmax có tính chất gì?",
      "Đều là các số dương và có tổng bằng một, nên đóng vai trò như xác suất rơi vào từng lớp.",
      201, "các đầu ra này liên kết với nhau qua việc chúng đều là các số dương và có tổng bằng một"),
    A("d08", "dev", "Ước lượng hợp lý cực đại (MLE) đi tìm điều gì?",
      "Bộ tham số θ làm cực đại xác suất p(x1, ..., xN | θ) của dữ liệu quan sát.",
      68, "Ước lượng hợp lý cực đại là việc đi tìm bộ tham số θ để θ = argmax",
      alt=[(77, "Với MLE, việc xác định tham số θ được thực hiện bằng cách đi tìm các tham số sao cho xác suất của tập huấn luyện")],
      note="v2 (dev error analysis): mục 4.4 Tóm tắt (tr.77) nêu lại đúng định nghĩa MLE; ban đầu thiếu nhãn evidence thay thế này."),
    A("d09", "dev", "Xác thực chéo (cross-validation) chia tập huấn luyện như thế nào?",
      "Chia thành k tập con kích thước gần bằng nhau, không giao nhau; mỗi lần lấy một tập làm xác thực, k−1 tập còn lại để huấn luyện.",
      113, "Trong xác thực chéo, tập huấn luyện được chia thành k tập con có kích thước gần bằng nhau và không giao nhau."),
    A("d10", "dev", "Kết thúc sớm (early stopping) giúp giảm quá khớp bằng cách nào?",
      "Dừng thuật toán trước khi hàm mất mát hội tụ.",
      113, "Một giải pháp giúp giảm quá khớp là dừng thuật toán trước khi nó hội tụ."),
    A("d11", "dev", "Hồi quy tuyến tính có thêm số hạng chính quy hoá L2 theo chuẩn của w còn được gọi là gì?",
      "Hồi quy ridge, với nghiệm w = (XX^T + λI)^(-1) X y.",
      107, "còn được gọi là hồi quy ridge"),
    A("d12", "dev", "Vì sao khi vector đặc trưng rất lớn người ta dùng gradient descent thay vì giải trực tiếp nghiệm của hồi quy tuyến tính?",
      "Vì ma trận XX^T lớn nên tính nghịch đảo tốn kém; gradient descent giúp tránh việc tính ma trận nghịch đảo.",
      107, "Gradient descent sẽ giúp tránh được việc tính ma trận nghịch đảo."),
    A("d13", "dev", "Phân tích thành phần chính (PCA) là phương pháp gì?",
      "Tìm một phép xoay trục toạ độ để có hệ trục mới sao cho thông tin của dữ liệu tập trung chủ yếu ở một vài thành phần; phần còn lại ít thông tin có thể bỏ.",
      275, "là phương pháp đi tìm một phép xoay trục toạ độ để được một hệ trục toạ độ mới sao cho trong hệ mới này, thông tin của dữ liệu chủ yếu tập trung ở một vài thành phần"),
    A("d14", "dev", "Trong phân tích giá trị suy biến (SVD), số phần tử khác không trên đường chéo của Σ bằng gì?",
      "Bằng hạng của ma trận A: r = rank(A).",
      267, "Số lượng các phần tử khác không trong Σ chính là hạng của ma trận A",
      {"chapter_no": "20"}),
    A("d15", "dev", "Mất mát không-một (zero-one loss) trả về giá trị nào cho một điểm dữ liệu?",
      "Trả về không nếu điểm được phân loại đúng và một nếu bị phân loại sai; nó là hàm đếm số điểm bị phân loại sai.",
      369, "Hàm mất mát không-một trả về không nếu một điểm được phân loại đúng và trả về một nếu điểm đó bị phân loại sai."),
    # ------------------------------ DEV: 2 unanswerable ------------------------------
    U("d16", "dev", "Thuật toán gradient boosting (ví dụ XGBoost) xây dựng các mô hình yếu tuần tự như thế nào?",
      "Sách có gradient descent và hồi quy nhưng không có boosting/XGBoost/AdaBoost/LightGBM.",
      [r"boost", r"xgboost", r"lightgbm", r"catboost"]),
    U("d17", "dev", "Mạng LSTM giải quyết vấn đề biến mất gradient trong mạng hồi tiếp (RNN) như thế nào?",
      "Sách chỉ có mạng neuron nhiều tầng/lan truyền ngược, không có RNN, LSTM hay GRU.",
      [r"\blstm\b", r"\brnn\b", r"recurrent", r"\bgru\b", r"hồi tiếp"]),
    # ------------------------------ TEST: 5 answerable ------------------------------
    A("t01", "test", "Với bài toán tối ưu có một ràng buộc đẳng thức, điểm tối ưu thoả mãn điều kiện nào theo phương pháp nhân tử Lagrange?",
      "Gradient của hàm Lagrange theo cả x và λ bằng không: ∇x L = ∇f0 + λ∇f1 = 0 và f1(x) = 0 (chính là ràng buộc).",
      338, "điểm tối ưu của bài toán (25.1) thoả mãn điều kiện"),
    A("t02", "test", "Hàm hạt nhân (kernel) k(x, z) trong SVM được định nghĩa như thế nào?",
      "k(x, z) = Φ(x)^T Φ(z), cho phép tránh tính trực tiếp Φ(x) có số chiều rất lớn hoặc vô hạn.",
      381, "định nghĩa hàm hạt nhân k(x, z) = Φ(x)T Φ(z)"),
    A("t03", "test", "Hàm kích hoạt ReLU cải thiện việc huấn luyện so với tanh như thế nào?",
      "Với mạng dùng ReLU, hàm mất mát giảm rất nhanh sau một vài epoch đầu tiên (hội tụ nhanh hơn tanh).",
      220, "với các mạng sử dụng hàm kích hoạt ReLU, hàm mất mát giảm rất nhanh sau một vài epoch đầu tiên"),
    A("t04", "test", "Phương pháp phổ biến nhất để tối ưu mạng neuron đa tầng là gì?",
      "Gradient descent (GD), áp dụng thông qua lan truyền ngược để tính gradient theo từng ma trận trọng số và vector bias.",
      220, "Phương pháp phổ biến nhất để tối ưu mạng neuron đa tầng chính là gradient descent (GD)."),
    A("t05", "test", "Đánh giá mô hình trên một tập xác thực quá nhỏ có thể gây ra vấn đề gì?",
      "Có thể gây ra hiện tượng thiên lệch; giải pháp là xác thực chéo (cross-validation).",
      112, "Việc đánh giá trên tập xác thực quá nhỏ có thể gây ra hiện tượng thiên lệch."),
    # ------------------------------ TEST: 2 unanswerable ------------------------------
    U("t06", "test", "Cơ chế self-attention trong kiến trúc Transformer/BERT tính trọng số chú ý giữa các từ như thế nào?",
      "Sách không đề cập attention, Transformer (chỉ có TfidfTransformer của sklearn), BERT hay GPT.",
      [r"\battention\b", r"\bbert\b", r"\bgpt\b", r"self.attention"]),
    U("t07", "test", "Thuật toán cây quyết định ID3 chọn thuộc tính để chia nút dựa trên information gain như thế nào?",
      "Sách không có cây quyết định, ID3, information gain; chỉ nhắc rừng ngẫu nhiên một lần trong danh sách đặc trưng.",
      [r"information gain", r"\bid3\b", r"cây (quyết định|phân loại)", r"decision tree"]),
]


def norm(s: str) -> str:
    return " ".join(s.split())


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    chunks = json.loads((DATA / "chunks.json").read_text(encoding="utf-8"))
    by_page: dict[int, list[dict]] = {}
    for c in chunks:
        by_page.setdefault(c["page"], []).append(c)
    errors: list[str] = []

    ids = [q["id"] for q in QUESTIONS]
    if len(set(ids)) != len(ids):
        errors.append("duplicate question id")
    for q in QUESTIONS:
        if q["answerable"]:
            for g in q["gold"]:
                where = [c["id"] for c in by_page.get(g["page"], []) if g["evidence"] in c["text"]]
                if len(where) != 1:
                    errors.append(f"{q['id']}: evidence found in {len(where)} chunks of page {g['page']} (need exactly 1): {g['evidence'][:50]!r}")
                else:
                    g["chunk_id"] = where[0]  # for the report; never shown to the agent
        else:
            q["absence_hits"] = {rx: sum(bool(re.search(rx, c["text"], re.I)) for c in chunks) for rx in q["absence_check"]}
            if any(q["absence_hits"].values()):
                errors.append(f"{q['id']}: NOT absent from corpus: {q['absence_hits']}")

    for split, (na, nu) in {"dev": (15, 2), "test": (5, 2)}.items():
        got = (sum(q["answerable"] for q in QUESTIONS if q["split"] == split),
               sum(not q["answerable"] for q in QUESTIONS if q["split"] == split))
        if got != (na, nu):
            errors.append(f"{split}: expected {na} answerable + {nu} unanswerable, got {got}")
    if errors:
        print("BENCHMARK INVALID:", *errors, sep="\n - ")
        return 1

    answerable = [{k: q[k] for k in ("id", "split", "question", "gold", "expected_answer", "filter") if k in q}
                  for q in QUESTIONS if q["answerable"]]
    cases = [{k: q[k] for k in ("id", "split", "question", "answerable", "expected_behavior", "absence_reason") if k in q}
             for q in QUESTIONS]
    (DATA / "benchmark.json").write_text(json.dumps(QUESTIONS, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "questions.json").write_text(json.dumps(answerable, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pages = sorted({q["gold"][0]["page"] for q in QUESTIONS if q["answerable"]})
    print(f"OK: {len(QUESTIONS)} questions (dev 15+2, test 5+2); gold pages {pages}")
    print("unanswerable absence hits:", {q["id"]: q["absence_hits"] for q in QUESTIONS if not q["answerable"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
