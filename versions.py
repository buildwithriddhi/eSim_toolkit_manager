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


def check_version(found, minimum):
    if minimum is None:
        return "no minimum set"
    result = is_at_least(found, minimum)
    if result is None:
        return "could not compare"
    if result:
        return "OK"
    return f"OUTDATED (need {minimum} or newer)"