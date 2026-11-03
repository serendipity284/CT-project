import os
from pathlib import Path
from urllib import response

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .schemas import ExtractedIntent


# Đọc file .env nằm trong backend-python
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)


def extract_intent(message: str, previous: dict):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "Không tìm thấy GEMINI_API_KEY trong file .env"
        )

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash"
    )

    # Khởi tạo client khi thực sự cần gọi Gemini
    client = genai.Client(api_key=api_key)

    prompt = f"""
    Bạn là module Input Understanding của hệ thống
    trợ lý tìm quán ăn sinh viên HCMUS.

    Nhiệm vụ:
    - Nhận diện ý định tìm kiếm.
    - Trích xuất cơ sở HCMUS.
    - Trích xuất ngân sách VND.
    - Trích xuất khoảng cách mét.
    - Nhận diện loại món ăn.
    - Hiểu ngữ cảnh hội thoại.

    Quy tắc:
    - q5: cơ sở Nguyễn Văn Cừ.
    - lang: cơ sở Làng Đại học.
    - 35k = 35000 VND.
    - 1km = 1000 mét.
    - Không tự suy đoán thông tin chưa được cung cấp.
    - Giữ thông tin cũ nếu người dùng không thay đổi.

    Thông tin trước đó:
    {previous}

    Câu người dùng:
    {message}
    """

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractedIntent,
            temperature=0.1
        )
    )

    if not response.text:
        raise ValueError("Gemini không trả về nội dung.")

    return ExtractedIntent.model_validate_json(response.text)