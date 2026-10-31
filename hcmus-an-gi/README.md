# HCMUS Ăn Gì

Web tìm quán ăn quanh 2 cơ sở HCMUS (Quận 5 & Làng Đại học): lọc ngân sách + khoảng cách, bản đồ nghiêng 3D, trợ lý chat hỏi lại khi thiếu thông tin, đăng nhập, lưu quán, lịch sử tìm, đánh giá.

## Stack demo (preview đã dựng)

- React 19 + TanStack Router/Start
- MapLibre GL (bản đồ nghiêng, đường chỉ hướng)
- Dữ liệu quán mẫu trong SQL (Postgres/PGLite trên demo; file MySQL đi kèm)
- Trợ lý chat: luật tiếng Việt (hỏi lại cơ sở / ngân sách / bán kính) — **không** nhúng Gemini/Google key trên client

## Chạy nhanh (bản self-contained trong zip)

```bash
cd hcmus-an-gi
npm install
npm run dev
```

Mở `http://localhost:8080`.

> Bản zip này là **source tái tạo** theo thiết kế đã chốt. Môi trường App Builder gốc dùng thêm Postgres (Neon/PGLite) + Better Auth; phần auth/DB thật cần cấu hình riêng khi bạn deploy (xem `docs/DEPLOY.md` và `public/hcmus-mysql.sql`).

## Tính năng

| Tính năng | Mô tả |
|-----------|--------|
| 2 cơ sở | Nguyễn Văn Cừ (Q5), Làng Đại học (Linh Trung) |
| Bộ lọc | Preset + ô tự nhập: ngân sách (VND), bán kính (m) |
| Bản đồ | MapLibre pitch ~58°, marker quán, nét chỉ hướng từ cổng |
| Chat | Hỏi lại nếu thiếu campus / budget / radius → ghim kết quả |
| Auth | Trang đăng nhập/đăng ký (email) — wire Better Auth hoặc backend Python |
| Cá nhân | Lưu quán, lịch sử tìm, đánh giá 1–5 sao |
| Schema MySQL | `public/hcmus-mysql.sql` để port Python + MySQL |

## Google Maps + Gemini (bản Python của bạn)

**Không** đưa API key lên frontend công khai.

1. Backend Python giữ `GOOGLE_MAPS_API_KEY`, `GEMINI_API_KEY` trong env server.
2. Places API / Nearby Search → ghi vào bảng `places` (cột `google_place_id`).
3. Gemini chỉ gọi từ server; client gửi message chat → server trả JSON `{ campus, budget, radiusM, reply }`.
4. Directions API (walking) nếu cần polyline thật thay vì nét thẳng.

## Cấu trúc thư mục

```
hcmus-an-gi/
├── public/hcmus-mysql.sql      # Schema MySQL 8
├── src/
│   ├── lib/
│   │   ├── campuses.ts         # Toạ độ 2 cơ sở, haversine, preset
│   │   ├── chat-intent.ts      # Parse tiếng Việt + hỏi lại
│   │   ├── places-data.ts      # Dữ liệu mẫu 16 quán
│   │   └── storage.ts          # localStorage: saves, history, reviews
│   ├── components/CampusMap.tsx
│   ├── routes/index.tsx        # UI chính
│   ├── routes/login.tsx
│   ├── styles.css
│   └── main.tsx
├── package.json
└── README.md
```

## Port sang Python + MySQL (gợi ý)

- Flask/FastAPI + SQLAlchemy/MySQL
- Bảng: `users`, `places`, `reviews`, `saves`, `search_history` (xem SQL)
- JWT hoặc session cookie cho auth
- Endpoint: `GET /places?campus=&budget=&radius_m=`, `POST /chat`, `POST /reviews`, …

## Giấy phép

Mã nguồn demo cho mục đích học tập / đồ án. Dữ liệu quán là **mẫu**, không phải feed Google Places thật.
