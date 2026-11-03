
def merge_context(previous, extracted):
    result = previous.copy()
    data = extracted.model_dump()

    # Các thông tin được cập nhật khi người dùng cung cấp giá trị mới
    for key in [
        "intent",
        "campus",
        "budget",
        "radius_m",
        "cuisine",
    ]:
        if data.get(key) is not None:
            result[key] = data[key]

    # Giữ lại từ khóa cũ nếu lượt mới không có từ khóa mới
    if data.get("keywords"):
        result["keywords"] = data["keywords"]
    elif "keywords" not in result:
        result["keywords"] = []

    return result
