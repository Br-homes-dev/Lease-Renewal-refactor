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
