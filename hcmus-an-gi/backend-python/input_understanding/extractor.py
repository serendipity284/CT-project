import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .schemas import ExtractedIntent


# Đọc file .env nằm trong backend-python
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)


def extract_intent(message: str, previous: dict):
    """
    Gửi tin nhắn của người dùng (và ngữ cảnh hội thoại trước đó) đến Gemini
    để trích xuất ý định, món ăn, ngân sách, cảm xúc và các thông tin tìm kiếm.

    Returns ExtractedIntent đã được parse từ JSON của Gemini.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "Không tìm thấy GEMINI_API_KEY trong file .env"
        )

    configured_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    # Danh sách model thử nghiệm theo thứ tự ưu tiên
    candidate_models = [configured_model]
    for m in ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"):
        if m not in candidate_models:
            candidate_models.append(m)

    # Khởi tạo client khi thực sự cần gọi Gemini
    client = genai.Client(api_key=api_key)

    prompt = f"""
Bạn là module Input Understanding của hệ thống trợ lý tìm quán ăn sinh viên HCMUS.

## NHIỆM VỤ CHÍNH
Phân tích tin nhắn tiếng Việt (kể cả tiếng lóng, viết tắt) và trả về JSON theo schema cho sẵn.

## TRÍCH XUẤT Ý ĐỊNH (intent)
- "search_food": người dùng muốn tìm quán / món ăn cụ thể
- "refine_search": tinh chỉnh lại tìm kiếm đang có
- "recommendation": chỉ hỏi gợi ý chung, chưa có yêu cầu cụ thể
- "emotion_based_food_suggestion": người dùng bày tỏ cảm xúc kèm mong muốn được gợi ý món ăn
- "other": tin nhắn không liên quan đến ăn uống

## NHẬN DIỆN MÓN ĂN (food_type, food_group, preference) — QUAN TRỌNG
1. **food_type**: Chuẩn hóa tên món cụ thể về định dạng snake_case chuẩn:
   - "cơm tấm", "cơm sườn", "sườn bì chả" -> "com_tam"
   - "cơm gà", "gà xối mỡ" -> "com_ga"
   - "cơm", "cơm trưa", "cơm bình dân" -> "com"
   - "phở", "phở bò", "phở gà" -> "pho"
   - "bún bò", "bún bò huế" -> "bun_bo"
   - "bún thịt nướng" -> "bun_thit_nuong"
   - "bún riêu" -> "bun_rieu"
   - "bún" -> "bun"
   - "bánh mì", "bánh mỳ" -> "banh_mi"
   - "hủ tiếu", "hủ tíu" -> "hu_tieu"
   - "mì", "mì quảng", "mì cay", "ramen" -> "mi"
   - "cháo", "cháo lòng", "cháo gà" -> "chao"
   - "xôi", "xôi mặn", "xôi gà" -> "xoi"
   - "lẩu", "lẩu thái" -> "lau"
   - "trà sữa" -> "tra_sua"
   - "cà phê", "cafe" -> "ca_phe"
   - "bánh tráng trộn" -> "banh_trang_tron"
   - "ăn vặt", "đồ ăn vặt" -> "an_vat"
   - "chay", "cơm chay", "quán chay" -> "chay"
   Ví dụ:
   - "Tìm quán cơm tấm ở Quận 5" -> food_type = "com_tam", campus = "q5"
   - "Tôi muốn ăn phở" -> food_type = "pho"
   - "Tìm quán bún bò dưới 40k" -> food_type = "bun_bo", budget = 40000

2. **food_group**: Nhận diện nhóm món:
   - "mon_nuoc": món nước, có nước, húp nước (phở, bún, hủ tiếu, mì, cháo...)
   - "do_chien": đồ chiên, món chiên, chiên giòn, rán
   - "do_nuong": đồ nướng, món nướng, thịt nướng
   - "do_an_vat": đồ ăn vặt, ăn vặt, tráng miệng
   - "mon_chay": món chay, đồ chay
   - "do_uong": đồ uống, nước giải khát, trà sữa

3. **preference**: Nhận diện sở thích ăn uống nếu có:
   - "cay": cay, nhiều cay, ăn cay
   - "khong_cay": không cay, ít cay, bớt cay
   - "chay": thuần chay, ăn chay
   - "thanh_dam": thanh đạm, ít dầu mỡ, nhẹ nhàng

## TRÍCH XUẤT CƠ SỞ (campus)
- "q5": Cơ sở Quận 5 / Nguyễn Văn Cừ / NVC
- "lang": Làng Đại học / Linh Trung / Thủ Đức

## TRÍCH XUẤT NGÂN SÁCH (budget)
Luôn trả về số nguyên VND:
- "35k" = 35000, "35K" = 35000, "35 K" = 35000
- "35.000" = 35000, "35,000" = 35000
- "35 nghìn" = 35000, "35 ngàn" = 35000
- "0.5 triệu" = 500000, "1 triệu" = 1000000, "1.5tr" = 1500000
- "200000" = 200000
CHÚ Ý: Nếu người dùng không nhắc ngân sách, để null (hệ thống sẽ áp dụng mặc định ở tầng sau).

## TRÍCH XUẤT BÁN KÍNH (radius_m)
- "500m" = 500, "1km" = 1000, "3km" = 3000
CHÚ Ý: Nếu người dùng không nhắc khoảng cách, để null (hệ thống sẽ áp dụng mặc định ở tầng sau).

## NHẬN DIỆN CẢM XÚC (emotion)
- "sadness", "stress", "tiredness", "happiness", "celebration", "boredom", "comfort", "neutral"

## QUY TẮC CHUNG
- Không tự suy đoán thông tin chưa được cung cấp — để null
- Giữ thông tin cũ nếu người dùng không thay đổi

## NGỮ CẢNH HỘI THOẠI TRƯỚC ĐÓ
{previous}

## TIN NHẮN NGƯỜI DÙNG
{message}
"""

    last_err = None
    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedIntent,
                    temperature=0.1
                )
            )
            if response.text:
                return ExtractedIntent.model_validate_json(response.text)
        except Exception as e:
            last_err = e
            continue

    raise ValueError(f"Tất cả các model Gemini đều thất bại: {last_err}")
