# Xây dựng công thức ranking quán ăn & xử lý case dị ứng của user

---

## Công thức gốc:
$$R = (50\% \cdot \text{Feedback} + 40\% \cdot \text{Giá} + 10\% \cdot \text{Độ mới}) \times 10\% \cdot \text{Khoảng cách}$$
$$\text{Feedback} = \frac{\text{Tổng số sao}}{\text{Tổng số lượt đánh giá}}$$

### Các điểm hạn chế về mặt Toán học & Logic:

1. **Lỗi bài toán mẫu số nhỏ (Cold-start / Small sample bias):**
   * $\text{Feedback} = \frac{\text{Tổng sao}}{\text{Tổng lượt đánh giá}}$ thực chất là **Điểm sao trung bình** ($1.0 \rightarrow 5.0$).
   * Quán mới có $1$ đánh giá $5$ sao nhận điểm Feedback là $5.0$, cao hơn quán nổi tiếng có $1.000$ đánh giá trung bình $4.8$ sao.

2. **Lỗi Thang đo & Đơn vị (Scale & Unit mismatches):**
   * Các thuộc tính **Feedback** (1–5 sao), **Giá** (VND), **Độ mới** (ngày/tháng) và **Khoảng cách** (mét/km) mang thang đo khác nhau. Khi chưa **Chuẩn hóa (Normalization)**, tham số có giá trị tuyệt đối lớn (như Giá tiền VNĐ) sẽ nuốt chửng toàn bộ các thuộc tính còn lại.

3. **Lỗi Triệt tiêu & Đảo ngược do hệ số Khoảng cách ($10\% \times \text{Khoảng cách}$):**
   * Nhân với $10\% \cdot \text{Khoảng cách}$ làm quán càng xa điểm càng cao (cách $1\text{ km} \rightarrow$ nhân $0.1$; cách $10\text{ km} \rightarrow$ nhân $1.0$), đi ngược tâm lý sinh viên (muốn ăn gần).
   * Phép nhân tạo ra tác động quá mạnh (Penalty/Boost Factor), có thể làm triệt tiêu hoặc lệch kết quả chỉ vì chênh lệch vài trăm mét.

4. **Biến "Độ mới thông tin" chưa chuẩn hóa toán học:**
   * Cần quy đổi thời gian trôi qua kể từ lần cập nhật thông tin gần nhất ($T_{\text{updated}}$) về khoảng $[0, 1]$.

---

## 2. Công Thức Ranking Cải Tiến 

Áp dụng phương pháp **Weighted Sum Scoring** với tất cả biến đầu vào được quy đổi về khoảng $[0, 1]$.

### Step 1: Chuẩn hóa các biến về thang điểm $[0, 1]$

1. **Điểm Feedback (Bayesian Average Rating):**
   $$\text{Rating}_{\text{bayesian}} = \frac{v \cdot R + m \cdot C}{v + m} \quad \Rightarrow \quad S_{\text{feedback}} = \frac{\text{Rating}_{\text{bayesian}}}{5.0}$$
   *(Trong đó: $v$ là số lượt đánh giá của quán, $R$ là điểm trung bình của quán, $m=10$ là số lượt đánh giá tối thiểu, $C=4.0$ là điểm đánh giá trung bình hệ thống).*

2. **Điểm Giá cả ($S_{\text{price}}$ - Giá càng rẻ điểm càng cao):**
   $$S_{\text{price}} = 1 - \frac{\text{Price} - \text{Price}_{\min}}{\text{Price}_{\max} - \text{Price}_{\min}}$$

3. **Điểm Khoảng cách ($S_{\text{distance}}$ - Càng gần điểm càng cao):**
   $$S_{\text{distance}} = 1 - \frac{\text{Dist} - \text{Dist}_{\min}}{\text{Dist}_{\max} - \text{Dist}_{\min}}$$

4. **Điểm Độ mới thông tin ($S_{\text{freshness}}$ - Cập nhật dữ liệu trong 3–4 tháng):**
   $$S_{\text{freshness}} = \max\left(0, 1 - \frac{T_{\text{updated}}}{120}\right)$$
   *(Trong đó: $T_{\text{updated}}$ là số ngày kể từ lần cập nhật giá/menu gần nhất; nếu quá $120$ ngày $\approx 4$ tháng thì điểm $= 0$).*

---

### Step 2: Mô hình Tổng Trọng số Chuẩn hóa (Normalized Weighted Sum)

$$R = w_1 \cdot S_{\text{feedback}} + w_2 \cdot S_{\text{price}} + w_3 \cdot S_{\text{distance}} + w_4 \cdot S_{\text{freshness}}$$

#### Trọng số đề xuất:
* $w_1 (\text{Feedback}) = 0.45$ (Bảo đảm chất lượng & uy tín)
* $w_2 (\text{Giá cả}) = 0.30$ (Ưu tiên ngân sách sinh viên)
* $w_3 (\text{Khoảng cách}) = 0.15$ (Độ tiện lợi di chuyển quanh trường)
* $w_4 (\text{Độ mới thông tin}) = 0.10$ (Bổ trợ độ tin cậy của dữ liệu quán hẻm)

---

## 3. Quy Trắc Xử Lý Trường Hợp Người Dùng Bị Dị Ứng (Allergy Handling)

### Nguyên tắc: Phân định Ràng buộc Cứng (Hard Constraint) vs Ràng buộc Mềm (Soft Constraint)

* **Soft Constraints (Ràng buộc mềm):** Giá tiền, khoảng cách, rating, độ mới. Được đưa vào công thức tính điểm $R$ để sắp xếp thứ tự hiển thị.
* **Hard Constraints (Ràng buộc cứng):** An toàn sức khỏe (dị ứng đậu phộng, hải sản, ăn chay...). Quán/món ăn chứa thành phần gây dị ứng sẽ bị **lọc bỏ hoàn toàn (Hard Filter/Exclusion)** ra khỏi CSDL trước khi tính toán xếp hạng.

### Luồng xử lý kỹ thuật 3 tầng (Pipeline Flow):

1. **Tầng hiểu ngữ cảnh (LLM Intent & Entity Extraction):**
   Trích xuất danh sách các thành phần gây dị ứng cần loại bỏ (ví dụ: `excluded_allergens: ["peanut"]`).

2. **Tầng lọc điều kiện cứng (Deterministic Hard Filtering):**
   Thực hiện câu lệnh truy vấn lọc triệt tiêu tại CSDL trước khi tính toán điểm:
   ```sql
   SELECT * FROM Eateries 
   WHERE price <= max_budget 
     AND 'peanut' NOT IN (ingredients_list);
   ```

3. **Tầng an toàn & Cảnh báo (Safety Guardrails - Requirement R7):**
   Đối với các quán chưa rõ danh sách thành phần (dữ liệu mờ nhạt), hệ thống kích hoạt cơ chế dự phòng an toàn bằng cách hiển thị nhãn cảnh báo trực quan cho người dùng (*"Quán chưa xác thực thành phần dị ứng, vui lòng lưu ý khi đặt món"*).