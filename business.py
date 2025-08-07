from typing import Dict
from config import (
    THRESHOLD_1_LIMIT, THRESHOLD_2_LIMIT, THRESHOLD_3_LIMIT,
    THRESHOLD_1_VALUE, THRESHOLD_2_VALUE, THRESHOLD_3_VALUE, THRESHOLD_4_VALUE
)

def get_threshold(purchase_price: float) -> float:
    """
    Returns the cash flow threshold based on the purchase price.
    """
    if purchase_price <= THRESHOLD_1_LIMIT:
        return THRESHOLD_1_VALUE
    if purchase_price <= THRESHOLD_2_LIMIT:
        return THRESHOLD_2_VALUE
    if purchase_price <= THRESHOLD_3_LIMIT:
        return THRESHOLD_3_VALUE
    return THRESHOLD_4_VALUE


def calculate_cashflow_difference(
    current_rent: float,
    current_cashflow: float,
    threshold: float,
    new_rent: float,
) -> Dict[str, float]:
    """Given current rent, cashflow and threshold, compute the projected
    cashflow after adjusting rent to ``new_rent``.

    Returns a dictionary with the projected cashflow, the difference from the
    threshold (positive if above) and whether the new cashflow meets the
    threshold.
    """
    new_cashflow = current_cashflow + (new_rent - current_rent)
    difference = new_cashflow - threshold
    return {
        "new_cashflow": new_cashflow,
        "difference": difference,
        "meets_threshold": new_cashflow >= threshold,
    }
