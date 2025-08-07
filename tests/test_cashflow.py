import pytest
from business import calculate_cashflow_difference


def test_cashflow_above_threshold():
    res = calculate_cashflow_difference(current_rent=1000, current_cashflow=200, threshold=150, new_rent=1050)
    assert pytest.approx(res["new_cashflow"]) == 250
    assert pytest.approx(res["difference"]) == 100
    assert res["meets_threshold"] is True


def test_cashflow_below_threshold():
    res = calculate_cashflow_difference(current_rent=1000, current_cashflow=100, threshold=150, new_rent=950)
    assert pytest.approx(res["new_cashflow"]) == 50
    assert pytest.approx(res["difference"]) == -100
    assert res["meets_threshold"] is False
