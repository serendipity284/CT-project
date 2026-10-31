# Backend Python + MySQL (gợi ý port)

Frontend zip dùng localStorage để chạy ngay. Khi làm đồ án đầy đủ:

1. Import `../public/hcmus-mysql.sql` vào MySQL 8.
2. Cài: `pip install -r requirements.txt`
3. Copy `.env.example` → `.env`, điền `MYSQL_*`, `GOOGLE_MAPS_API_KEY`, `GEMINI_API_KEY`.
4. Chạy: `uvicorn app:app --reload --port 8000`

API stub trong `app.py`:

- `POST /auth/signup`, `POST /auth/login`
- `GET /places?campus=q5&budget=50000&radius_m=800`
- `POST /chat` — có thể gọi Gemini; mặc định dùng cùng logic hỏi lại như frontend
- `POST /reviews`, `GET /reviews?place_id=`
- `POST /saves/{place_id}`, `GET /saves`
- `GET /history`

**Bảo mật:** chỉ gọi Google/Gemini từ server, không đưa key ra React.
