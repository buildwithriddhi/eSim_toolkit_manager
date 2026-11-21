def parse_version(text):
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError:
        return None


def is_at_least(found, minimum):
    a = parse_version(found)
    b = parse_version(minimum)
    if a is None or b is None:
        return None

    length = max(len(a), len(b))
    a = a + (0,) * (length - len(a))
    b = b + (0,) * (length - len(b))
    return a >= b

def check_exact_version(found, expected):
    # Equal means "at least" in both directions (so 45.2 and 45.2.0 match).
    same = is_at_least(found, expected) and is_at_least(expected, found)
    if same:
        return "OK"
    if is_at_least(found, expected) is None:
        return "could not compare"
    return f"WRONG VERSION (need exactly {expected})"