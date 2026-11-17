"""Advanced benchmark (tables / images & diagrams / charts / multi-hop / text / unanswerable) for book_ML.pdf.

    python -m src.advanced.build_benchmark_adv   -> data/advanced/benchmark_adv.json

Gold was written by reading the ORIGINAL page renders (crops of the PDF), not the vision descriptions.
Each answerable item has evidence entries {page, kind, ref, detail}:
  kind=text   -> `detail` must be a verbatim substring of a text chunk on that page (checked here)
  kind=table|figure -> `ref` (e.g. "Bảng 7.1", "Hình 16.10") must be a caption found on that page (checked here);
                       `detail` states the cells / panel / reading used, `region` points to the crop for graders.
Unanswerable items carry `absence_check` regexes that must match nothing on the listed pages (or the whole
text corpus when no pages are given) plus a note on what was inspected visually.
Dev and test were split BEFORE any run. Gold never reaches the pipeline (the runner passes only `question`).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DAY7 = Path(__file__).resolve().parents[2]
OUT = DAY7 / "data" / "advanced" / "benchmark_adv.json"


def T(page, detail):
    return {"page": page, "kind": "text", "ref": "đoạn văn", "detail": detail}


def V(page, kind, ref, detail, region):
    return {"page": page, "kind": kind, "ref": ref, "detail": detail, "region": region}


def A(qid, split, group, question, answer, evidence, reason, calc="", tolerance=""):
    return {"id": qid, "split": split, "group": group, "answerable": True, "question": question, "expected_answer": answer,
            "evidence": evidence, "calc": calc, "tolerance": tolerance, "reason": reason}


def U(qid, split, question, reason, checks, visual_note):
    return {"id": qid, "split": split, "group": "unanswerable", "answerable": False, "question": question,
            "expected_behavior": "abstain", "reason": reason, "absence_check": checks, "visual_check": visual_note}


B = [
    # =============================== DEV (15 answerable + 3 unanswerable) ===============================
    A("ad01", "dev", "table", "Theo bảng các thuật ngữ trong bài toán tối ưu (chương 24), ký hiệu nào biểu diễn đẳng thức ràng buộc và thuật ngữ tiếng Anh tương ứng là gì?",
      "Ký hiệu h_j(x) = 0; tiếng Anh: equality constraint.",
      [V(325, "table", "Bảng 24.1", "hàng 'h_j(x) = 0 | equality constraint | đẳng thức ràng buộc'", "p325|v00")], "Tra một hàng của bảng"),
    A("ad02", "dev", "table", "Trong bảng quy ước ký hiệu của sách, ký hiệu ⊙ có nghĩa là gì?",
      "Hadamard product (elementwise product): phép nhân từng phần tử của hai vector hoặc ma trận cùng kích thước.",
      [V(22, "table", "Bảng 0.1", "hàng ký hiệu ⊙", "p022|v00")], "Tra một hàng của bảng ký hiệu"),
    A("ad03", "dev", "table", "Trong bảng dữ liệu chiều cao và cân nặng ở chương hồi quy tuyến tính, có bao nhiêu người cao từ 170 cm trở lên?",
      "6 người (170, 173, 175, 178, 180, 183 cm).",
      [V(104, "table", "Bảng 7.1", "cột chiều cao: 170, 173, 175, 178, 180, 183 ≥ 170", "p104|v00")], "Đếm theo điều kiện trên một cột", calc="đếm các ô ≥ 170"),
    A("ad04", "dev", "image", "Trong hình minh hoạ bài toán phân loại nhị phân ở đầu chương perceptron, điểm tam giác được phân vào tập nào?",
      "Được phân vào tập các điểm hình tròn (Hình 13.1b).",
      [V(176, "figure", "Hình 13.1", "(b): đường thẳng phân chia, tam giác nằm phía các điểm tròn; chú thích xác nhận", "p176|v00")], "Đọc sơ đồ + chú thích"),
    A("ad05", "dev", "image", "Theo chú giải của hình so sánh các hàm kích hoạt ở chương hồi quy logistic, những hàm nào được vẽ?",
      "4 hàm: hard threshold, f(s) = 1/(1+e^{-s}) (sigmoid), f(s) = e^s/(e^s + e^{-s}), và linear.",
      [V(186, "figure", "Hình 14.2", "chú giải 4 đường: hard threshold, 1/(1+e^-s), e^s/(e^s+e^-s), linear", "p186|v01")], "Đọc chú giải trong hình"),
    A("ad06", "dev", "image", "Ảnh khuôn mặt sau khi phân cụm K-means trong chương 10 được chia thành bao nhiêu cụm màu, là những màu nào?",
      "3 cụm, tương ứng ba màu đỏ, hồng, đen (ảnh màu ở Hình B.4).",
      [V(140, "figure", "Hình 10.8", "ảnh 3 mức xám; chú thích: ba cụm đỏ, hồng, đen", "p140|v00")], "Ảnh + chú thích"),
    A("ad07", "dev", "chart", "Trong đồ thị lịch sử hàm mất mát của SVM đa lớp, giá trị mất mát ban đầu khoảng bao nhiêu và trục hoành kéo dài tới khoảng bao nhiêu vòng lặp?",
      "Bắt đầu khoảng 9; trục số vòng lặp tới khoảng 2500 (mất mát giảm về khoảng 4.5–5).",
      [V(398, "chart", "Hình 29.6", "trục tung loss function 4–9, đường bắt đầu ≈9; trục hoành number of iterations 0–2500", "p398|v00")],
      "Đọc trục và giá trị đầu", tolerance="ban đầu 8.5–9.2; trục ~2500"),
    A("ad08", "dev", "chart", "Trong đồ thị hàm mất mát của ví dụ hồi quy softmax năm lớp, giá trị mất mát ở epoch đầu khoảng bao nhiêu và huấn luyện bao nhiêu epoch?",
      "Khoảng 15–16 ở epoch đầu, giảm gần 0 rất nhanh; trục epoch tới 100.",
      [V(211, "chart", "Hình 15.5", "(a) loss vs number of epochs: bắt đầu ≈15.5, trục 0–100", "p211|v00")], "Đọc trục biểu đồ", tolerance="14.5–16"),
    A("ad09", "dev", "chart", "Trong đồ thị giá trị hàm mất mát của hồi quy logistic (bài toán dự đoán đỗ/trượt), mất mát bắt đầu khoảng bao nhiêu và hội tụ quanh giá trị nào?",
      "Bắt đầu khoảng 1.1, hội tụ quanh khoảng 0.4 (trước khoảng 100 vòng lặp; trục tới 500).",
      [V(192, "chart", "Hình 14.3", "(b) loss function vs number of iterations: ≈1.1 → ≈0.4", "p192|v00")], "Đọc biểu đồ", tolerance="1.0–1.15; 0.38–0.42"),
    A("ad10", "dev", "multihop", "Trong ví dụ cuối chương SVM hạt nhân với tập dữ liệu khoảng 29000 điểm, bộ phân loại dùng hàm hạt nhân nào với gamma bao nhiêu, công thức của hàm đó theo bảng hàm hạt nhân thông dụng là gì, và đạt độ chính xác bao nhiêu?",
      "Hạt nhân rbf, gamma = 0.1 (coef0 = 0); công thức exp(−γ‖x − z‖²₂); độ chính xác 94.22%.",
      [T(386, "gamma=.1, coef0 = 0"), T(386, "Accuracy: 94.22 %"),
       V(383, "table", "Bảng 28.2", "hàng 'rbf': exp(−γ‖x−z‖²₂), γ > 0: gamma (PDF in ký tự & thay cho ‖)", "p383|v00")],
      "Kết hợp code/kết quả trang 386 với bảng trang 383",
      ) | {"revision": "v2: câu v1 mơ hồ (cuối chương có 2 ví dụ: XOR tr.384 và ví dụ 29000 điểm tr.386); thêm điều kiện phân biệt, không đổi đáp án"},
    A("ad11", "dev", "multihop", "Theo bảng thời gian ôn thi của 20 sinh viên, có bao nhiêu sinh viên ôn dưới 2 giờ mà vẫn thi đỗ, và trong đồ thị kết quả thi theo số giờ ôn tập các sinh viên đỗ được biểu diễn bằng ký hiệu gì?",
      "1 sinh viên (1.75 giờ); sinh viên đỗ được biểu diễn bằng hình vuông.",
      [V(185, "table", "Bảng 14.1", "các ô <2 giờ: 0.5,0.75,1,1.25,1.5,1.75(0),1.75(1) → chỉ một ô 1.75 có Đậu=1", "p185|v00"),
       V(186, "figure", "Hình 14.1", "chú thích: 1/pass là các điểm hình vuông", "p186|v00")], "Bảng + hình", calc="đếm"),
    A("ad12", "dev", "multihop", "Theo bảng so sánh mạng neuron và SVM, SVM lề cứng tương đồng với thuật toán nào, và hình minh hoạ ở đầu chương SVM cho thấy điều kiện gì của dữ liệu cùng với bao nhiêu đường phân chia được vẽ?",
      "Tương đồng với PLA (perceptron); dữ liệu hai lớp tách biệt tuyến tính, có vô số đường thẳng phân chia; hình vẽ 3 đường.",
      [V(378, "table", "Bảng 28.1", "hàng PLA | SVM lề cứng | Hai lớp tách biệt tuyến tính", "p378|v00"),
       V(351, "figure", "Hình 26.1", "3 đường thẳng phân chia hai lớp vuông/tròn", "p351|v00")], "Bảng + sơ đồ"),
    A("ad13", "dev", "text", "Theo sách, hạn chế đầu tiên của hồi quy tuyến tính là gì và ví dụ cặp dữ liệu nhiễu nào được dùng để minh hoạ?",
      "Rất nhạy cảm với nhiễu; ví dụ chỉ một cặp nhiễu (150 cm, 90 kg) làm kết quả sai khác rất nhiều.",
      [T(106, "nếu có chỉ một cặp dữ liệu nhiễu (150 cm, 90kg) thì kết quả sẽ sai khác đi rất nhiều")], "Tra đoạn văn"),
    A("ad14", "dev", "text", "Trong phân cụm theo tầng kiểu agglomerative dựa trên K-means, ban đầu K được chọn như thế nào?",
      "Chọn K là một số lớn gần bằng số điểm dữ liệu, sau đó ghép các cụm gần nhau.",
      [T(138, "Ban đầu ta chọn K là một số lớn gần bằng số điểm dữ liệu.")], "Tra đoạn văn có điều kiện"),
    A("ad15", "dev", "text", "Theo phần tóm tắt chương ước lượng tham số, MAP có thể được coi như phương pháp giúp ích trong trường hợp nào?",
      "Giúp tránh thiên lệch khi có ít dữ liệu huấn luyện.",
      [T(77, "MAP có thể được coi như một phương pháp giúp tránh thiên lệch khi có ít dữ liệu huấn luyện.")], "Tra đoạn văn"),
    U("ad16", "dev", "Theo bảng dữ liệu chiều cao và cân nặng của 15 người, tuổi trung bình của nhóm người này là bao nhiêu?",
      "Bảng 7.1 chỉ có chiều cao và cân nặng, không có tuổi.",
      [{"pattern": r"tuổi|\bage\b", "pages": [103, 104, 105, 106]}], "Đã xem Bảng 7.1: chỉ hai cột chiều cao/cân nặng."),
    U("ad17", "dev", "Trong hình lựa chọn mô hình dựa trên sai số xác thực, sai số kiểm tra khi bậc đa thức bằng 10 là bao nhiêu?",
      "Hình 8.2 chỉ vẽ bậc 1–8; text không nêu bậc 10.",
      [{"pattern": r"bậc\s*(=\s*)?10\b|bậc mười", "pages": [110, 111, 112, 113]}], "Đã xem Hình 8.2: trục 'bậc' từ 1 đến 8."),
    U("ad18", "dev", "Theo bảng các hàm hạt nhân thông dụng, công thức của hạt nhân Laplacian là gì?",
      "Bảng 28.2 chỉ có linear, poly, sigmoid, rbf; sách không có hạt nhân Laplacian (chỉ có 'làm mềm Laplace' trong naive Bayes, tr.147/149/155 — bẫy gần chủ đề).",
      [{"pattern": r"laplacian|hạt nhân laplace|laplace kernel"}], "Đã xem Bảng 28.2: 4 hàng."),

    # dev additions (after test-v1 analysis) so the calculation fix of config v3 is validated on DEV, not on test
    A("ad19", "dev", "table", "Trong bảng dữ liệu chiều cao và cân nặng của 15 người, cân nặng trung bình của những người cao không quá 155 cm là bao nhiêu?",
      "50.5 kg (147→49, 150→50, 153→51, 155→52; (49+50+51+52)/4).",
      [V(104, "table", "Bảng 7.1", "4 hàng đầu cột trái", "p104|v00")], "Lọc theo điều kiện + trung bình", calc="(49+50+51+52)/4 = 50.5"),
    A("ad20", "dev", "multihop", "Theo công thức xác suất thi đỗ tìm được bằng hồi quy logistic ở chương 14, xác suất đỗ dự đoán cho sinh viên ôn 1.75 giờ là bao nhiêu, và trong bảng thời gian ôn thi các sinh viên ôn 1.75 giờ có kết quả thế nào?",
      "≈ 0.20 (sigmoid(1.54×1.75 − 4.06) = sigmoid(−1.365)); trong Bảng 14.1 có hai sinh viên ôn 1.75 giờ: một trượt (0), một đỗ (1).",
      [T(191, "probability_of_pass ≈ sigmoid(1.54 * hours_of_studying - 4.06)"), V(185, "table", "Bảng 14.1", "hai ô 1.75: Đậu 0 và 1", "p185|v00")],
      "Công thức + bảng + tính", calc="1/(1+e^1.365) ≈ 0.203", tolerance="0.19–0.21"),

    # =============================== TEST (24 answerable + 6 unanswerable) ===============================
    A("at01", "test", "table", "Theo bảng thời gian ôn thi và kết quả thi của 20 sinh viên, có bao nhiêu sinh viên thi đỗ?",
      "10 sinh viên đỗ (và 10 trượt).",
      [V(185, "table", "Bảng 14.1", "cột Đậu?: 3 + 1 + 4 + 2 giá trị 1 theo bốn cặp cột", "p185|v00")], "Đếm trên toàn bảng", calc="3+1+4+2 = 10"),
    A("at02", "test", "table", "Trong bảng dữ liệu chiều cao và cân nặng của 15 người, cân nặng của người cao nhất hơn người thấp nhất bao nhiêu kg?",
      "19 kg (183 cm nặng 68 kg; 147 cm nặng 49 kg).",
      [V(104, "table", "Bảng 7.1", "147 cm → 49 kg; 183 cm → 68 kg", "p104|v00")], "Tra hai ô + phép trừ", calc="68 − 49 = 19 kg"),
    A("at03", "test", "table", "Theo bảng các hàm hạt nhân thông dụng, hạt nhân 'poly' có công thức gì và cần thiết lập những hệ số nào (tên tham số)?",
      "(r + γ xᵀz)^d; hệ số d: degree, γ: gamma, r: coef0.",
      [V(383, "table", "Bảng 28.2", "hàng 'poly'", "p383|v00")], "Tra một hàng nhiều cột"),
    A("at04", "test", "table", "Theo bảng các gradient cơ bản, gradient theo x của hàm f(x) = ‖Ax − b‖²₂ là gì?",
      "2Aᵀ(Ax − b).",
      [V(49, "table", "Bảng 2.1", "hàng ‖Ax − b‖²₂ → 2Aᵀ(Ax − b)", "p049|v00")], "Tra ô bảng"),
    A("at05", "test", "table", "Trong bảng ví dụ văn bản của bài toán phân loại Bắc hay Nam, văn bản kiểm tra có nội dung gì và tập huấn luyện có bao nhiêu văn bản mỗi nhãn?",
      "d5: 'hanoi hanoi buncha hutiu'; huấn luyện có 3 văn bản nhãn B (d1, d2, d3) và 1 văn bản nhãn N (d4).",
      [V(148, "table", "Bảng 11.1", "hàng d5 (Dữ liệu kiểm tra) và cột Nhãn của d1–d4", "p148|v00")], "Tra ô + đếm"),
    A("at06", "test", "table", "Theo bảng sự tương đồng giữa mạng neuron và SVM, hồi quy softmax tương ứng với loại SVM nào và tính chất chung là gì?",
      "SVM đa lớp; tính chất chung: nhiều lớp dữ liệu, ranh giới tuyến tính.",
      [V(378, "table", "Bảng 28.1", "hàng Hồi quy softmax | SVM đa lớp | Nhiều lớp dữ liệu, ranh giới tuyến tính", "p378|v00")], "Tra một hàng"),
    A("at07", "test", "image", "Trong hình kết quả với số lượng nút ẩn khác nhau (chương mạng neuron đa tầng), độ chính xác khi tầng ẩn có 2, 5, 15 và 30 nút lần lượt là bao nhiêu?",
      "≈59.67% (2 nút), 74.0% (5 nút), ≈94.33% (15 nút), ≈95.33% (30 nút).",
      [V(229, "figure", "Hình 16.10", "tiêu đề 4 hình con: '#hidden units = 2, accuracy = 59.666…%', '= 5, 74.0%', '= 15, 94.333…%', '= 30, 95.333…%'", "p229|v00 + p229|v01")],
      "Đọc chữ trong ảnh (4 hình con)", tolerance="làm tròn 2 chữ số"),
    A("at08", "test", "image", "Mạng MLP với hai tầng ẩn trong chương mạng neuron đa tầng có bao nhiêu nút ở tầng vào, mỗi tầng ẩn và tầng ra?",
      "Tầng vào 3 nút, tầng ẩn thứ nhất 4 nút, tầng ẩn thứ hai 2 nút, tầng ra 3 nút (ma trận W(1), W(2), W(3)).",
      [V(217, "figure", "Hình 16.3", "đếm vòng tròn: 3 | 4 | 2 | 3", "p217|v00")], "Đếm thành phần sơ đồ"),
    A("at09", "test", "image", "Ảnh ví dụ về giá trị pixel trong chương phân cụm K-means là chữ số mấy, và giá trị pixel lớn nhất xuất hiện trong ma trận là bao nhiêu?",
      "Chữ số 7; giá trị lớn nhất 254.",
      [V(136, "figure", "Hình 10.4", "ma trận pixel: giá trị lớn nhất 254 (hàng 5 và các hàng sau)", "p136|v01")], "Đọc ảnh + số trong ảnh"),
    A("at10", "test", "image", "Trong ví dụ SVD cho ảnh, sai số khi xấp xỉ ảnh với k = 5, k = 50 và k = 100 lần lượt là bao nhiêu?",
      "0.0448 (k = 5), 0.0059 (k = 50), 0.0026 (k = 100).",
      [V(272, "figure", "Hình 20.3", "tiêu đề các ảnh (d), (e), (f): 'k = 5: error = 0.0448', 'k = 50: error = 0.0059', 'k = 100: error = 0.0026'", "p272|v02")], "Đọc chữ trên ảnh"),
    A("at11", "test", "image", "Trong hình mối quan hệ giữa AI, ML và DL ở lời nói đầu, Deep Learning bắt đầu ở khoảng thập niên nào và câu mô tả kèm theo là gì?",
      "Khoảng thập niên 2010 (2010's); 'Deep learning breakthroughs drive AI boom.'",
      [V(16, "figure", "Hình 0.1", "khối DEEP LEARNING bắt đầu tại mốc 2010's, dòng chữ 'Deep learning breakthroughs drive AI boom.'", "p016|v00")], "Đọc sơ đồ dòng thời gian"),
    A("at12", "test", "chart", "Trong đồ thị hàm mật độ phân phối beta với α = β, đường nét liền ứng với cặp tham số nào và đỉnh của nó nằm tại λ bằng bao nhiêu?",
      "Cặp (10, 10); đỉnh tại λ = 0.5.",
      [V(76, "chart", "Hình 4.1", "chú giải: nét liền = (10, 10); đỉnh tại 0.50", "p076|v00")], "Đọc chú giải + trục", tolerance="0.5"),
    A("at13", "test", "chart", "Trong hình so sánh hàm ReLU với tanh (b), đường nét liền đạt training error rate 0.25 sau khoảng bao nhiêu epoch và đường nét đứt sau khoảng bao nhiêu epoch?",
      "Nét liền khoảng 6 epoch; nét đứt khoảng 35–36 epoch (nhanh hơn khoảng 6 lần).",
      [V(220, "chart", "Hình 16.6", "(b) Training error rate vs Epochs, ngưỡng 0.25: nét liền ≈6, nét đứt ≈35", "p220|v00")],
      "Đọc giá trị trên trục", tolerance="nét liền 5–7; nét đứt 33–37"),
    A("at14", "test", "chart", "Trong hình so sánh hàm entropy chéo và hàm bình phương khoảng cách, ở trường hợp p = 0.1, điểm cực tiểu toàn cục của hai hàm nằm tại q bằng bao nhiêu và đường nét liền là hàm nào?",
      "Cả hai đạt cực tiểu tại q = 0.1; đường nét liền là hàm entropy chéo.",
      [V(206, "chart", "Hình 15.4", "(b) p = 0.1: hai dấu x tại q = 0.1; chú thích: nét liền = entropy chéo", "p206|v00")], "Đọc biểu đồ + chú thích"),
    A("at15", "test", "chart", "Trong hình kết quả gradient descent với x0 = −5 và η = 0.5, gradient ở vòng lặp cuối cùng hiển thị (100/100) bằng bao nhiêu và thuật toán có hội tụ không?",
      "grad = 4.761 tại iter 100/100; không hội tụ (nghiệm dao động quanh điểm cực tiểu do η quá lớn).",
      [V(163, "chart", "Hình 12.5", "hình con 'iter 100/100, grad = 4.761'; các hình con gradient đổi dấu liên tục", "p163|v01")], "Đọc chữ trong biểu đồ"),
    A("at16", "test", "chart", "Trong hình lựa chọn mô hình dựa trên sai số xác thực, sai số xác thực nhỏ nhất ở bậc nào và sai số kiểm tra ở bậc 8 khoảng bao nhiêu?",
      "Nhỏ nhất ở bậc 3 (≈ 7.8, bậc 4 gần bằng); sai số kiểm tra ở bậc 8 khoảng 14.",
      [V(112, "chart", "Hình 8.2", "đường xác thực thấp nhất ở bậc 3–4 (≈7.8); đường kiểm tra tại bậc 8 ≈ 13.9", "p112|v00")],
      "Đọc giá trị trên trục", tolerance="bậc 3 (chấp nhận 3 hoặc 4); 13.5–14.2"),
    A("at17", "test", "multihop", "Trong ví dụ hồi quy tuyến tính chiều cao–cân nặng, bảng có 15 người nhưng dữ liệu huấn luyện dùng ít hơn; hai người nào không dùng để huấn luyện và mô hình dự đoán sai lệch bao nhiêu kg với mỗi người?",
      "Hai người 155 cm và 160 cm (dữ liệu huấn luyện có 13 điểm). 155 cm: thật 52 kg, dự đoán 52.94 kg → lệch 0.94 kg; 160 cm: thật 56 kg, dự đoán 55.74 kg → lệch 0.26 kg.",
      [V(104, "table", "Bảng 7.1", "15 người, có 155 cm → 52 kg, 160 cm → 56 kg", "p104|v00"),
       T(104, "X = np.array([[147, 150, 153, 158, 163, 165, 168, 170, 173, 175, 178, 180, 183]]).T"),
       T(105, "Input 155cm, true output 52kg, predicted output 52.94kg."), T(105, "Input 160cm, true output 56kg, predicted output 55.74kg.")],
      "Bảng + code + kết quả trên hai trang", calc="|52.94 − 52| = 0.94; |55.74 − 56| = 0.26"),
    A("at18", "test", "multihop", "Theo bảng thời gian ôn thi, sinh viên ôn 4.25 giờ có kết quả gì, và theo công thức xác suất thi đỗ tìm được bằng hồi quy logistic, xác suất đỗ dự đoán cho 4.25 giờ khoảng bao nhiêu?",
      "Thi đỗ (Đậu = 1); xác suất ≈ sigmoid(1.54 × 4.25 − 4.06) = sigmoid(2.485) ≈ 0.92.",
      [V(185, "table", "Bảng 14.1", "ô 4.25 → 1", "p185|v00"), T(191, "probability_of_pass ≈ sigmoid(1.54 * hours_of_studying - 4.06)")],
      "Bảng + công thức + tính toán", calc="1.54·4.25 − 4.06 = 2.485; 1/(1+e^−2.485) ≈ 0.923", tolerance="0.91–0.93"),
    A("at19", "test", "multihop", "Trong ví dụ phân loại Bắc hay Nam, văn bản kiểm tra có nội dung gì và mô hình MultinomialNB dự đoán nó thuộc nhãn nào?",
      "d5 = 'hanoi hanoi buncha hutiu'; MultinomialNB dự đoán nhãn B.",
      [V(148, "table", "Bảng 11.1", "hàng d5", "p148|v00"), T(150, "Predicting class of d5: B")], "Bảng + kết quả code ở trang khác"),
    A("at20", "test", "multihop", "So sánh hai hình gradient descent với η = 0.1: khi x0 = −5 và khi x0 = 5, mỗi trường hợp chạy bao nhiêu vòng lặp và gradient ở vòng cuối bằng bao nhiêu?",
      "x0 = −5: 11 vòng lặp, grad cuối = −0.001; x0 = 5: 29 vòng lặp, grad cuối = 0.001 (cả hai hội tụ, x0 = 5 chậm hơn).",
      [V(162, "chart", "Hình 12.2", "hình con 'iter 11/11, grad = -0.001'", "p162|v00"), V(162, "chart", "Hình 12.3", "hình con 'iter 29/29, grad = 0.001'", "p162|v01")],
      "Kết hợp hai hình"),
    A("at21", "test", "text", "Trong mini-batch gradient descent, nếu N không chia hết cho k thì mini-batch cuối thế nào, một epoch gồm khoảng bao nhiêu vòng lặp, và k thường được chọn trong khoảng nào?",
      "Mini-batch cuối có thể ít hơn k điểm; một epoch gồm xấp xỉ N/k vòng lặp; k từ vài chục đến vài trăm.",
      [T(173, "trừ mini-batch cuối có thể có ít hơn nếu N không chia hết cho k"), T(173, "một epoch bao gồm xấp xỉ N/k vòng lặp"),
       T(173, "được chọn trong khoảng khoảng từ vài chục đến vài trăm")], "Tổng hợp điều kiện từ đoạn văn"),
    A("at22", "test", "text", "Trong SVM lề mềm, nếu hệ số C nhỏ thì thuật toán ưu tiên điều gì và tổng các biến ξ thay đổi thế nào; còn khi C rất lớn và dữ liệu tách biệt tuyến tính thì nghiệm thu được là gì?",
      "C nhỏ: ưu tiên ‖w‖ nhỏ nhất (lề lớn nhất) nên tổng ξ lớn lên; C rất lớn và dữ liệu tách biệt tuyến tính: tổng ξ = 0, nghiệm trùng với SVM lề cứng.",
      [T(364, "Nếu C nhỏ, việc sự hy sinh cao hay thấp không gây ảnh hưởng nhiều tới giá trị của hàm mục tiêu"),
       T(364, "nghiệm thu được cũng chính là nghiệm của SVM lề cứng")], "Điều kiện → kết quả"),
    A("at23", "test", "text", "Khi dùng PCA, nếu muốn giữ lại 99% thông tin thì chọn số chiều K như thế nào?",
      "Chọn K là số tự nhiên nhỏ nhất sao cho r_K = (Σ_{i=1..K} λ_i)/(Σ_{j=1..D} λ_j) ≥ 0.99.",
      [T(282, "ta chỉ cần chọn K là số tự nhiên nhỏ nhất sao cho rK ≥ 0.99")], "Tra điều kiện"),
    A("at24", "test", "text", "Khi áp dụng lan truyền ngược, trong trường hợp nào mini-batch GD được dùng nhiều nhất và trường hợp nào dùng batch GD trực tiếp?",
      "Mini-batch GD với bài toán có tập huấn luyện lớn; dữ liệu nhỏ thì dùng batch GD trực tiếp.",
      [T(224, "Trong thực tế, mini-batch GD được sử dụng nhiều nhất với các bài toán mà tập huấn luyện lớn. Nếu lượng dữ liệu nhỏ, batch GD trực tiếp được sử dụng.")], "Điều kiện từ đoạn văn"),
    U("at25", "test", "Theo bảng thời gian ôn thi của 20 sinh viên, điểm thi (thang 10) trung bình của các sinh viên thi đỗ là bao nhiêu?",
      "Bảng 14.1 chỉ có số giờ và Đậu? (0/1), không có điểm số.",
      [{"pattern": r"thang (điểm|10)|điểm thi|điểm số", "pages": [184, 185, 186, 187, 191, 192]}], "Đã xem Bảng 14.1: chỉ cột Số giờ/Đậu?."),
    U("at26", "test", "Trong hình kết quả với số lượng nút ẩn khác nhau, độ chính xác khi tầng ẩn có 100 nút là bao nhiêu?",
      "Hình 16.10 chỉ có 2, 5, 15, 30 nút ẩn.",
      [{"pattern": r"hidden units = 100|100 nút", "pages": [226, 227, 228, 229, 230, 231]}], "Đã xem Hình 16.10: 4 hình con 2/5/15/30."),
    U("at27", "test", "Trong ví dụ SVD cho ảnh, sai số của ảnh xấp xỉ khi chọn k = 200 là bao nhiêu?",
      "Chỉ có ảnh xấp xỉ k = 5, 50, 100; k = 200 chỉ được nhắc về giá trị suy biến/lượng thông tin, không có sai số.",
      [{"pattern": r"200\s*:\s*error|k\s*=\s*200\s*:", "pages": [270, 271, 272, 273]}], "Đã xem Hình 20.3: ảnh (d)(e)(f) với k = 5, 50, 100."),
    U("at28", "test", "Huấn luyện SVM đa lớp trong hình lịch sử giá trị hàm mất mát mất bao nhiêu giây?",
      "Sách không báo thời gian chạy (giây) cho ví dụ này.",
      [{"pattern": r"giây|seconds|\bsec\b|thời gian chạy", "pages": [395, 396, 397, 398, 399, 400]}], "Đã xem Hình 29.6: chỉ loss theo số vòng lặp."),
    U("at29", "test", "Trong đồ thị phân phối beta ở chương ước lượng tham số, đường ứng với cặp tham số (5, 1) có dạng như thế nào?",
      "Hình 4.1 chỉ có α = β: (2,2), (0.5,0.5), (10,10), (0.1,0.1), (1,1); không có (5, 1).",
      [{"pattern": r"\(\s*5\s*,\s*1\s*\)", "pages": [74, 75, 76, 77]}], "Đã xem chú giải Hình 4.1."),
    U("at30", "test", "Trong các hình minh hoạ gradient descent cho hàm một biến ở chương 12, với η = 0.05 thì cần bao nhiêu vòng lặp để hội tụ?",
      "Chỉ có η = 0.1 (x0 = ±5), 0.01 và 0.5; không có η = 0.05 cho ví dụ này (lr = 0.05 chỉ xuất hiện ở ví dụ logistic chương 14).",
      [{"pattern": r"η\s*=\s*0\.05", "pages": list(range(158, 176))}], "Đã xem Hình 12.2–12.5."),
]


# =============================== TEST_V2 (split "test2", written AFTER config v3 was frozen) ===============================
# New, independent test set: no question/answer reused from dev or test v1. Absence checks use scope "all":
# every text chunk + every figure caption + every vision description (the v1 gold error at26 came from a page-range check).
B += [
    A("n01", "test2", "table", "Trong ma trận tiện ích của ví dụ hệ thống gợi ý bài hát (đánh giá 0–5 sao), có bao nhiêu ô còn thiếu dữ liệu (dấu '?') và người dùng E đánh giá bài 'Con cò bé bé' mấy sao?",
      "12 ô còn thiếu (1 + 4 + 3 + 1 + 3 theo năm bài hát); người dùng E đánh giá 'Con cò bé bé' 4 sao.",
      [V(236, "table", "Hình 17.1", "ma trận 5 bài × 6 người dùng A–F; đếm ô '?' theo hàng: 1, 4, 3, 1, 3; hàng 'Con cò bé bé' cột E = 4", "p236|v00")],
      "Đếm ô + tra ô", calc="1+4+3+1+3 = 12"),
    A("n02", "test2", "table", "Trong ma trận tiện ích dựa trên số sao người dùng đánh giá sản phẩm (chương lọc cộng tác lân cận), người dùng u3 đánh giá sản phẩm i3 mấy sao và hàng của sản phẩm i4 có bao nhiêu ô còn thiếu?",
      "u3 đánh giá i3 = 4 sao; hàng i4 có 3 ô còn thiếu (u3, u4, u5).",
      [V(247, "table", "Hình 18.1", "hàng i3: 2 2 3 4 4 ? 4 (u3 = 4); hàng i4: 2 0 4 ? ? ? 5", "p247|v00")], "Tra ô + đếm"),
    A("n03", "test2", "table", "Theo bảng thời gian ôn thi và kết quả thi của 20 sinh viên, có bao nhiêu sinh viên ôn từ 4 giờ trở lên và trong số đó bao nhiêu người trượt?",
      "7 sinh viên ôn từ 4 giờ trở lên (4, 4, 4.25, 4.5, 4.75, 5, 5.5); 1 người trượt (một sinh viên ôn 4 giờ).",
      [V(185, "table", "Bảng 14.1", "các ô >= 4: 4.5->1, 4.75->1, 4->1, 5->1, 4->0, 4.25->1, 5.5->1", "p185|v00")], "Lọc theo điều kiện + đếm"),
    A("n04", "test2", "table", "Trong bảng dữ liệu chiều cao và cân nặng của 15 người, cân nặng trung bình của 3 người cao nhất là bao nhiêu?",
      "67 kg (178 cm -> 66, 180 cm -> 67, 183 cm -> 68; (66 + 67 + 68)/3).",
      [V(104, "table", "Bảng 7.1", "ba hàng cuối cột phải", "p104|v00")], "Sắp xếp + trung bình", calc="(66+67+68)/3 = 67"),
    A("n05", "test2", "table", "Theo bảng các gradient cơ bản, gradient theo ma trận X của hàm trace(AᵀXB) là gì?",
      "ABᵀ.", [V(49, "table", "Bảng 2.1", "hàng trace(AᵀXB) -> ABᵀ", "p049|v00")], "Tra ô bảng"),
    A("n06", "test2", "table", "Theo bảng các hàm hạt nhân thông dụng, hạt nhân 'sigmoid' có công thức gì và những hệ số nào cần thiết lập?",
      "tanh(γ xᵀz + r); hệ số γ: gamma, r: coef0.", [V(383, "table", "Bảng 28.2", "hàng 'sigmoid'", "p383|v00")], "Tra một hàng"),
    A("n07", "test2", "image", "Trong hình ví dụ cách tính vector điểm số của SVM đa lớp (ảnh con mèo đầu vào), điểm số của các lớp cat, frog, dog là bao nhiêu và ảnh được gán nhãn lớp nào?",
      "cat 285.3, frog −154.5, dog 248.8; nhãn là cat (điểm cao nhất).",
      [V(391, "figure", "Hình 29.3", "vector điểm số z: 285.3 (cat), −154.5 (frog), 248.8 (dog)", "p391|v00")], "Đọc số trong sơ đồ + so sánh"),
    A("n08", "test2", "image", "Trong hình mô phỏng cách tính hàm mất mát và gradient trong SVM đa lớp, vector nhãn y là gì và L_data bằng bao nhiêu (gồm các thành phần nào)?",
      "y = [1, 3, 2]; L_data = 0.5 + 0.7 + 0.3 + 1.5 = 3.0.",
      [V(396, "figure", "Hình 29.5", "dòng 'y = [1, 3, 2]' và 'L_data = 0.5 + 0.7 + 0.3 + 1.5 = 3.0'", "p396|v00")], "Đọc sơ đồ có số"),
    A("n09", "test2", "image", "Mạng neuron đa tầng dùng cho ví dụ dữ liệu giả hai chiều (một tầng ẩn ReLU) được vẽ với bao nhiêu nút ở tầng đầu vào, tầng ẩn và tầng đầu ra, và tầng đầu ra là mô hình gì?",
      "Tầng vào 2 nút, tầng ẩn vẽ 4 nút (số nút ẩn tuỳ ý), tầng ra 3 nút là hồi quy softmax (ba lớp).",
      [V(225, "figure", "Hình 16.9", "đếm vòng tròn 2 | 4 | 3; nhãn 'Tầng đầu ra Hồi quy softmax'; chú thích 'ba phần tử đại diện cho ba lớp'", "p225|v01")], "Đếm thành phần sơ đồ"),
    A("n10", "test2", "image", "Trong hình chất lượng nén ảnh với số lượng cluster khác nhau (K-means), những giá trị K nào được so sánh?",
      "K = 5, 10, 15 và 20.", [V(141, "figure", "Hình 10.9", "4 ảnh với nhãn k = 5, K = 10, K = 15, K = 20", "p141|v00")], "Đọc nhãn ảnh"),
    A("n11", "test2", "image", "Trong hình dữ liệu giả trong không gian hai chiều và ví dụ về các ranh giới tốt, ranh giới ở hình (b) dùng bao nhiêu nút ẩn và đạt độ chính xác bao nhiêu?",
      "100 nút ẩn; độ chính xác ≈ 99.33% (99.333…%).",
      [V(225, "figure", "Hình 16.8", "(b) tiêu đề '#hidden units = 100, accuracy = 99.33333333333333%'", "p225|v00")], "Đọc chữ trên ảnh"),
    A("n12", "test2", "chart", "Trong hình kết quả gradient descent với x0 = −5 và η = 0.01, gradient tại vòng lặp 50/100 và 100/100 bằng bao nhiêu?",
      "iter 50/100: grad = −1.476; iter 100/100: grad = −0.049.",
      [V(163, "chart", "Hình 12.4", "tiêu đề hình con 'iter 50/100, grad = -1.476' và 'iter 100/100, grad = -0.049'", "p163|v00")], "Đọc chữ trên biểu đồ"),
    A("n13", "test2", "chart", "Trong hình minh hoạ chưa khớp và quá khớp trong hồi quy đa thức, bốn hình con dùng những bậc đa thức nào và mỗi bậc được nhận xét thế nào?",
      "Bậc 2: chưa khớp; bậc 4: mô hình tốt; bậc 8: quá khớp; bậc 16: quá khớp.",
      [V(109, "chart", "Hình 8.1", "tiêu đề (a) 'Bậc = 2: Chưa khớp', (b) 'Bậc = 4: Mô hình tốt', (c) 'Bậc = 8: Quá khớp', (d) 'Bậc = 16: Quá khớp'", "p109|v00 + p109|v01")],
      "Đọc tiêu đề các biểu đồ con"),
    A("n14", "test2", "chart", "Theo đồ thị ví dụ của hàm sigmoid và tanh trong chương mạng neuron đa tầng, mỗi hàm nhận giá trị trong khoảng nào và giá trị tại z = 0 là bao nhiêu?",
      "sigmoid: (0, 1), tại z = 0 bằng 0.5; tanh: (−1, 1), tại z = 0 bằng 0.",
      [V(219, "chart", "Hình 16.5", "(a) tiệm cận 0 và 1, tại z = 0 bằng 0.5; (b) tiệm cận −1 và 1, đi qua 0", "p219|v00")], "Đọc trục và giá trị"),
    A("n15", "test2", "chart", "Trong đồ thị hàm mật độ của phân phối chuẩn một chiều ở chương ôn tập xác suất, đường có đỉnh cao nhất ứng với tham số nào và đỉnh cao khoảng bao nhiêu?",
      "μ = 0.5, σ² = 0.5; đỉnh khoảng 0.56.",
      [V(64, "chart", "Hình 3.3", "(a) ba đường: (μ=.5, σ²=.5) đỉnh ≈0.56; (μ=0, σ²=1) ≈0.40; (μ=−1, σ²=2) ≈0.28", "p064|v00")],
      "Đọc nhãn + trục", tolerance="0.53–0.58"),
    A("n16", "test2", "chart", "Trong hình ảnh hưởng của C lên nghiệm của SVM lề mềm, ba hình con đầu tiên (hàng trên trái, hàng trên phải, hàng dưới trái) dùng giá trị C nào, và theo chú thích C càng lớn thì biên thế nào?",
      "C = 0.1, C = 1, C = 10; C càng lớn thì biên càng nhỏ (và ngược lại).",
      [V(376, "chart", "Hình 27.5", "tiêu đề 'C = 0.100000', 'C = 1.000000', 'C = 10.000000'; chú thích", "p376|v00")], "Đọc tiêu đề + chú thích"),
    A("n17", "test2", "multihop", "Trong ví dụ phân loại Bắc hay Nam, từ xuất hiện nhiều lần nhất trong văn bản kiểm tra là từ nào, và theo hình minh hoạ NBC với Multinomial naive Bayes, ước lượng λ̂ của từ đó cho nhãn B và nhãn N là bao nhiêu?",
      "'hanoi' (2 lần trong d5); λ̂_B = 4/20, λ̂_N = 1/13.",
      [V(148, "table", "Bảng 11.1", "d5 = 'hanoi hanoi buncha hutiu'", "p148|v00"), V(149, "figure", "Hình 11.1", "cột 'hanoi': λ̂_B = 4/20, λ̂_N = 1/13", "p149|v00")],
      "Bảng + hình"),
    A("n18", "test2", "multihop", "Độ chính xác của mạng có 100 nút ẩn trong ví dụ ranh giới tốt cao hơn mạng có 30 nút ẩn trong hình so sánh số nút ẩn bao nhiêu điểm phần trăm?",
      "99.33% − 95.33% = 4.0 điểm phần trăm.",
      [V(225, "figure", "Hình 16.8", "(b) 100 nút: 99.333…%", "p225|v00"), V(229, "figure", "Hình 16.10", "(d) 30 nút: 95.333…%", "p229|v01")],
      "Hai hình ở hai trang + phép trừ", calc="99.3333 − 95.3333 = 4.0"),
    A("n19", "test2", "multihop", "Theo công thức xác suất thi đỗ của hồi quy logistic ở chương 14, số giờ ôn mà tại đó xác suất đỗ bằng 0.5 là khoảng bao nhiêu, và theo bảng thời gian ôn thi có bao nhiêu sinh viên ôn nhiều hơn mức đó nhưng vẫn trượt?",
      "≈ 2.64 giờ (1.54·h − 4.06 = 0 ⇒ h = 4.06/1.54); có 2 sinh viên trượt dù ôn nhiều hơn (3.5 giờ và 4 giờ).",
      [T(191, "probability_of_pass ≈ sigmoid(1.54 * hours_of_studying - 4.06)"), V(185, "table", "Bảng 14.1", "ô > 2.64 có Đậu = 0: 3.5 và 4", "p185|v00")],
      "Công thức + bảng + tính", calc="4.06/1.54 ≈ 2.636", tolerance="2.6–2.7"),
    A("n20", "test2", "multihop", "Theo bảng sự tương đồng giữa mạng neuron và SVM, mạng neuron đa tầng tương ứng với loại SVM nào, và theo sách hàm hạt nhân nào được dùng nhiều nhất và là lựa chọn mặc định trong sklearn.svm.SVC?",
      "SVM hạt nhân (bài toán phân loại hai lớp không tách biệt tuyến tính); hạt nhân rbf.",
      [V(378, "table", "Bảng 28.1", "hàng Mạng neuron đa tầng | SVM hạt nhân", "p378|v00"),
       T(385, "các rbf kernel được sử dụng nhiều nhất và cũng là lựa chọn mặc định trong sklearn.svm.SVC")], "Bảng + đoạn văn trang khác"),
    A("n21", "test2", "text", "Trong stochastic gradient descent, sau mỗi epoch cần làm gì với thứ tự dữ liệu, và đó là lý do gì cho chữ 'stochastic' trong tên thuật toán?",
      "Xáo trộn thứ tự lấy dữ liệu sau mỗi epoch để đảm bảo tính ngẫu nhiên; chính sự ngẫu nhiên này là lý do có từ 'stochastic' (cũng ảnh hưởng tới hiệu năng SGD).",
      [T(172, "sau mỗi epoch, thứ tự lấy các dữ liệu cần được xáo trộn để đảm bảo tính ngẫu nhiên"), T(172, "Đây cũng chính là lý do thuật toán này có chứa từ stochastic")], "Tra đoạn văn"),
    A("n22", "test2", "text", "Vì sao thuật toán phân cụm K-means được đảm bảo hội tụ sau một số hữu hạn vòng lặp?",
      "Giá trị hàm mất mát sau mỗi bước là dãy không tăng và bị chặn dưới nên hội tụ; thêm nữa số cách phân cụm toàn bộ dữ liệu là hữu hạn (khi K cố định).",
      [T(132, "Thuật toán này sẽ hội tụ sau một số hữu hạn vòng lặp."), T(132, "là một đại lượng không tăng và bị chặn dưới")], "Lập luận từ đoạn văn"),
    A("n23", "test2", "text", "Theo phần thảo luận hạn chế của K-means, nếu không biết trước số cụm K thì sách gợi ý tham khảo phương pháp nào, và nghiệm cuối cùng phụ thuộc vào yếu tố gì?",
      "Phương pháp elbow; nghiệm cuối cùng phụ thuộc vào các tâm cụm được khởi tạo ban đầu.",
      [T(141, "Bạn đọc có thể tham khảo phương pháp elbow giúp xác định giá trị K này"), T(141, "Nghiệm cuối cùng phụ thuộc vào các tâm cụm được khởi tạo ban đầu.")], "Tra điều kiện"),
    A("n24", "test2", "text", "Vì sao hàm mất mát của hồi quy tuyến tính lấy trung bình trên N điểm dữ liệu thay vì lấy tổng?",
      "Số điểm dữ liệu trong tập huấn luyện có thể thay đổi nên mất mát trên từng điểm hữu ích hơn để đánh giá mô hình; lấy trung bình cũng tránh tràn số khi số điểm dữ liệu lớn.",
      [T(102, "Việc tính toán mất mát trên từng điểm dữ liệu sẽ hữu ích hơn trong việc đánh giá chất lượng mô hình."),
       T(102, "việc lấy trung bình cũng giúp tránh hiện tượng tràn số khi số lượng điểm dữ liệu lớn")], "Tổng hợp lý do"),
    U("n25", "test2", "Trong ví dụ ma trận tiện ích của hệ thống gợi ý bài hát, ca sĩ thể hiện bài 'Mưa nửa đêm' là ai?",
      "Sách chỉ nêu tên bài hát và điểm đánh giá; 'ca sĩ' chỉ xuất hiện ở ví dụ chung (Bích Phương, tr.235) không gắn với bài nào trong ma trận.",
      [{"pattern": r"Mưa nửa đêm.{0,300}ca sĩ|ca sĩ.{0,300}Mưa nửa đêm", "scope": "all"}], "Đã xem Hình 17.1/17.2: chỉ tên bài và số sao."),
    U("n26", "test2", "Theo bảng thời gian ôn thi của 20 sinh viên, các sinh viên này học ngành gì?",
      "Bảng 14.1 chỉ có số giờ ôn và Đậu?; sách không nêu ngành học.",
      [{"pattern": r"ngành học|chuyên ngành", "scope": "all"}], "Đã xem Bảng 14.1."),
    U("n27", "test2", "Trong hình chất lượng nén ảnh K-means, dung lượng file (KB) của ảnh nén với K = 20 là bao nhiêu?",
      "Hình 10.9 chỉ so sánh trực quan theo K; không có dung lượng file.",
      [{"pattern": r"kilobyte|dung lượng|(?-i:\bKB\b)", "scope": "all"}], "Đã xem Hình 10.9: chỉ nhãn K. ('kb' trong công thức tr.353 là k·b, không phải KB)"),
    U("n28", "test2", "Trong hình ảnh hưởng của C lên nghiệm SVM lề mềm, độ chính xác phân loại khi C = 10 là bao nhiêu?",
      "Chương 27 không báo độ chính xác cho các giá trị C; Hình 27.5 chỉ vẽ đường phân chia.",
      [{"pattern": r"accuracy|độ chính xác\s*(là|=|đạt|bằng)", "pages": list(range(360, 378))}], "Đã xem Hình 27.5 và chương 27."),
    U("n29", "test2", "Trong ma trận tiện ích dựa trên số sao (chương lọc cộng tác), người dùng u0 có tên thật là gì?",
      "Người dùng chỉ được ký hiệu u0–u6; không có tên.",
      [{"pattern": r"tên (thật|của) người dùng", "scope": "all"}], "Đã xem Hình 18.1."),
    U("n30", "test2", "Con mèo trong ảnh đầu vào của ví dụ tính vector điểm số SVM đa lớp thuộc giống mèo nào?",
      "Sách không nêu giống mèo.",
      [{"pattern": r"giống mèo|Persian|Siamese|mèo Anh|mèo Ba Tư|mèo Xiêm", "scope": "all"}], "Đã xem Hình 29.3."),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    chunks = json.loads((DAY7 / "data" / "book" / "chunks.json").read_text(encoding="utf-8"))
    regions = json.loads((DAY7 / "data" / "advanced" / "regions.json").read_text(encoding="utf-8"))["regions"]
    by_page: dict[int, str] = {}
    for c in chunks:
        by_page[c["page"]] = by_page.get(c["page"], "") + "\n" + c["text"]
    caps: dict[int, set] = {}
    for r in regions:
        for lab in filter(None, r["caption_label"].split("; ")):
            caps.setdefault(r["page"], set()).add(lab)
    desc = json.loads((DAY7 / "data" / "advanced" / "descriptions.json").read_text(encoding="utf-8"))
    everything = {f"text p{p}": t for p, t in by_page.items()}
    everything.update({f"caption {r['id']}": r["caption"] for r in regions})
    everything.update({f"desc {k}": v.get("content", "") for k, v in desc.items()})
    errors = []
    ids = [q["id"] for q in B]
    if len(set(ids)) != len(ids):
        errors.append("duplicate ids")
    for q in B:
        if q["answerable"]:
            for ev in q["evidence"]:
                if ev["kind"] == "text" and ev["detail"] not in by_page.get(ev["page"], ""):
                    errors.append(f"{q['id']}: text evidence not on page {ev['page']}: {ev['detail'][:50]!r}")
                if ev["kind"] != "text" and ev["ref"] not in caps.get(ev["page"], set()):
                    errors.append(f"{q['id']}: caption {ev['ref']} not found on page {ev['page']} (have {caps.get(ev['page'])})")
        else:
            for chk in q["absence_check"]:
                if chk.get("scope") == "all":  # whole book text + every caption + every vision description
                    hits = [k for k, txt in everything.items() if re.search(chk["pattern"], txt, re.I | re.S)]
                else:
                    pages = chk.get("pages") or sorted(by_page)
                    hits = [p for p in pages if re.search(chk["pattern"], by_page.get(p, ""), re.I)]
                chk["hits"] = hits
                if hits:
                    errors.append(f"{q['id']}: absence pattern {chk['pattern']!r} found on pages {hits}")
    from collections import Counter
    counts = {s: Counter(q["group"] for q in B if q["split"] == s) for s in ("dev", "test", "test2")}
    need_test = {"table": 6, "image": 5, "chart": 5, "multihop": 4, "text": 4, "unanswerable": 6}
    for split in ("test", "test2"):
        for g, n in need_test.items():
            if counts[split][g] < n:
                errors.append(f"{split} needs {n} {g}, has {counts[split][g]}")
    if sum(counts["dev"][g] for g in counts["dev"] if g != "unanswerable") < 15 or counts["dev"]["unanswerable"] < 3:
        errors.append("dev needs >=15 answerable + >=3 unanswerable")
    if errors:
        print("INVALID:", *errors, sep="\n - ")
        return 1
    OUT.write_text(json.dumps(B, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("OK", {s: dict(c) for s, c in counts.items()}, "->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
