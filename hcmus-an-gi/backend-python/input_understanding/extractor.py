import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .food import fallback_extract_food, remove_accents
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

## TÊN MÓN VÀ TÊN QUÁN
- food_name: chép nguyên cụm tên món trong tin nhắn hiện tại, kể cả dấu, số, biến thể, topping và tên lạ. Không quy về món phổ biến.
- place_name: chép tên riêng của quán. Phân biệt "tìm quán bán bánh mì que" (chỉ có món) với "tìm quán Cô Ba" (chỉ có tên quán).
- "Tìm bánh mì que ở quán Cô Ba dưới 30k" -> food_name = "bánh mì que", place_name = "Cô Ba".
- Nếu chỉ gửi "bánh mì que", food_name = "bánh mì que". Nếu không nhắc tên ở lượt này, trường tương ứng là null.

**preference**: Nhận diện sở thích ăn uống nếu có:
   - "cay": cay, nhiều cay, ăn cay
   - "khong_cay": không cay, ít cay, bớt cay
   - "chay": thuần chay, ăn chay
   - "thanh_dam": thanh đạm, ít dầu mỡ, nhẹ nhàng

## TRÍCH XUẤT CƠ SỞ (campus)
- "q5": Cơ sở Quận 5 / Nguyễn Văn Cừ / NVC
- "lang": Làng Đại học / Linh Trung / Thủ Đức

Chỉ trích xuất thay đổi trong tin nhắn hiện tại cho budget và radius_m.
Nếu người dùng yêu cầu bỏ giới hạn, đặt budget_unlimited hoặc radius_unlimited = true
cho đúng tiêu chí và để giá trị tương ứng null. Nếu không nhắc tiêu chí, để null và cờ false.

## TRÍCH XUẤT NGÂN SÁCH (budget)
Luôn trả về số nguyên VND:
- "35k" = 35000, "35K" = 35000, "35 K" = 35000
- "35.000" = 35000, "35,000" = 35000
- "35 nghìn" = 35000, "35 ngàn" = 35000
- "0.5 triệu" = 500000, "1 triệu" = 1000000, "1.5tr" = 1500000
- "200000" = 200000
CHÚ Ý: Nếu người dùng không nhắc ngân sách, để null (giữ giới hạn người dùng đã đặt, nếu chưa có thì không giới hạn).

## TRÍCH XUẤT BÁN KÍNH (radius_m)
- "500m" = 500, "1km" = 1000, "3km" = 3000
CHÚ Ý: Nếu người dùng không nhắc khoảng cách, để null (giữ giới hạn người dùng đã đặt, nếu chưa có thì không giới hạn).

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
                extracted = ExtractedIntent.model_validate_json(response.text)
                # Recover the original spelling and modifiers if the model shortens a name.
                fallback = fallback_extract_food(message)
                if not extracted.place_name and not extracted.food_name:
                    extracted.place_name = fallback.place_name
                elif extracted.place_name and fallback.place_name:
                    # Preserve the full venue when the model returns only its suffix.
                    full_name = remove_accents(fallback.place_name).casefold()
                    suffix = remove_accents(extracted.place_name).casefold().strip()
                    if full_name.endswith(" " + suffix):
                        extracted.place_name = fallback.place_name
                candidate = fallback.food_name
                if candidate and extracted.food_name:
                    model_words = remove_accents(extracted.food_name).casefold().replace("_", " ").split()
                    source_words = remove_accents(candidate).casefold().split()
                    if model_words and source_words[:len(model_words)] == model_words:
                        extracted.food_name = candidate
                return extracted
        except Exception as e:
            last_err = e
            continue

    raise ValueError(f"Tất cả các model Gemini đều thất bại: {last_err}")
