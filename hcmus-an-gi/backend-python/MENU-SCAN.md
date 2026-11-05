# Chup menu + AI scan (Gemini Vision)

## Luong
1. User dang nhap, tab Dong gop
2. Chon/chup anh menu
3. POST /menu/scan (JWT) -> Gemini doc mon + gia
4. User sua list mon tren form
5. Gui dong gop -> POST /places/contribute-with-menu
   -> INSERT places + place_dishes

## Can
- GEMINI_API_KEY trong backend-python/.env
- pip install google-genai
- VITE_API_URL + uvicorn dang chay
- (Khuyen nghi) import public/menu-dishes.sql

## Gioi han
- Anh mo / menu viet tay: OCR kem
- Can review thu cong truoc khi luu DB
- Ton quota Gemini
