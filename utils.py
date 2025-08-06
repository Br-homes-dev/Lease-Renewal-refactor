def parse_num(value: str) -> float:
    return float(''.join(ch for ch in value if ch in '0123456789.-')) if value else 0.0
