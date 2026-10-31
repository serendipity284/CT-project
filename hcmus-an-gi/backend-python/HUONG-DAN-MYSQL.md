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
SOURCE C:/Users/ADMIN/Downloads/hcmus-an-gi-source/hcmus-an-gi/public/hcmus-mysql.sql;
```

Trong phpMyAdmin: chọn database → tab **Import** → chọn file `public/hcmus-mysql.sql`.

File SQL đã có bảng + 16 quán mẫu.

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
| Table doesn't exist | Chưa Import `hcmus-mysql.sql` |
| CORS | API đã bật `allow_origins=["*"]` |
| Port 8000 bận | `uvicorn ... --port 8001` và đổi URL |

## Google Places / Gemini

Chỉ gọi từ **Python** (biến môi trường server), ghi kết quả vào bảng `places`. Không đưa API key vào React.
