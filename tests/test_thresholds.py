from config import get_threshold

def test_threshold_values():
    assert get_threshold(120000) == 225
    assert get_threshold(150000) == 225
    assert get_threshold(200000) == 275
    assert get_threshold(300000) == 275
    assert get_threshold(350000) == 400
    assert get_threshold(450000) == 400
    assert get_threshold(500000) == 650