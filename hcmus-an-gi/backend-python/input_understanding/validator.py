def validate_intent(data):
    if data.campus not in (None, "q5", "lang"):
        data.campus = None

    if data.budget is not None:
        if not 5000 <= data.budget <= 500000:
            data.budget = None

    if data.radius_m is not None:
        if not 100 <= data.radius_m <= 10000:
            data.radius_m = None

    return data