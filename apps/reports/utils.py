# Score Range
def get_score_range_label(score: int) -> str:
    if score <= 33:
        return "LOW"
    elif score <= 66:
        return "MEDIUM"
    else:
        return "HIGH"