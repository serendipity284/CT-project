# Gắn MySQL vào HCMUS Ăn Gì (Windows)

## Kiến trúc

```
React (localhost:8080)  -->  FastAPI (localhost:8000)  -->  MySQL
```

Trình duyệt **không** nối thẳng MySQL.

## Bước 1 — Cài MySQL

Cách dễ: [XAMPP](https://www.apachefriends.org/) → Start **MySQL**.

Hoặc MySQL Installer từ mysql.com (port 3306, nhớ mật khẩu `root`).

## Bước 2 — Tạo database + import schema

Mở **phpMyAdmin** (`http://localhost/phpmyadmin`) hoặc MySQL Command Line:

```sql
CREATE DATABASE hcmus_an_gi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hcmus_an_gi;
SOURCE C:/path/to/hcmus-an-gi/heana_schema.sql;
```

Trong phpMyAdmin: chọn database `hcmus_an_gi` → tab **Import** → chọn file `heana_schema.sql` ở thư mục gốc `hcmus-an-gi`.

File schema chuẩn tạo các bảng cho tìm kiếm, menu, dị ứng, lịch sử, đánh giá và chỉ đường trong hẻm. Nếu database đã tồn tại từ file SQL cũ, cần tạo database mới hoặc nâng cấp schema cũ trước; `CREATE TABLE IF NOT EXISTS` không tự đổi cấu trúc các bảng đã có.

## Bước 3 — Cấu hình backend

```bat
cd C:\Users\ADMIN\Downloads\hcmus-an-gi-source\hcmus-an-gi\backend-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Sửa `.env` cho đúng máy bạn:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=hcmus_an_gi
JWT_SECRET=chuoi-bi-mat-cua-ban
```

XAMPP mặc định `MYSQL_PASSWORD` thường **để trống**.

## Bước 4 — Chạy API

```bat
uvicorn app:app --reload --port 8000
```

Thử trình duyệt:

- http://localhost:8000/health  → `"mysql": true`
- http://localhost:8000/places?campus=q5&budget=50000&radius_m=800
- http://localhost:8000/docs  → Swagger thử API

## Bước 5 — Web gọi API (tuỳ chọn)

Mặc định React vẫn dùng localStorage. Để dùng MySQL:

1. Tạo file `hcmus-an-gi/.env` (Vite):

```env
VITE_API_URL=http://localhost:8000
```

2. Trong code, khi `VITE_API_URL` có giá trị thì `fetch` tới API thay vì `storage.ts`.

Hoặc test trước bằng Swagger / Postman:

```http
POST http://localhost:8000/auth/signup
{"email":"sv@hcmu.edu.vn","password":"12345678","name":"An"}

GET http://localhost:8000/places?campus=lang&budget=40000&radius_m=1000
```

## Bảng dùng cho chức năng nào

| Bảng | Dùng khi |
|------|----------|
| places | Lọc quán theo campus, budget; map |
| users | Đăng ký / đăng nhập |
| reviews | Đánh giá |
| saves | Bookmark quán |
| search_history | Lịch sử tìm / chat |

## Lỗi thường gặp

| Lỗi | Cách xử lý |
|-----|------------|
| `mysql: false` trên /health | MySQL chưa Start; sai password trong `.env` |
| Access denied | Đúng user/password XAMPP |
| Table/column doesn't exist | Import schema `heana_schema.sql`; file `public/hcmus-mysql.sql` là schema demo cũ và không khớp backend hiện tại |
| CORS | API đã bật `allow_origins=["*"]` |
| Port 8000 bận | `uvicorn ... --port 8001` và đổi URL |

## Google Places / Gemini

Chỉ gọi từ **Python** (biến môi trường server), ghi kết quả vào bảng `places`. Không đưa API key vào React.
