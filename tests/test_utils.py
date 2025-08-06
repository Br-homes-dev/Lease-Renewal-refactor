from server import parse_num

def test_parse_num():
    assert parse_num("1,234.56") == 1234.56
    assert parse_num("1,000") == 1000
    assert parse_num("") == 0
    assert parse_num("N/A") == 0