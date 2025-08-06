import unittest
from business import get_threshold
from config import (
    THRESHOLD_1_LIMIT, THRESHOLD_2_LIMIT, THRESHOLD_3_LIMIT,
    THRESHOLD_1_VALUE, THRESHOLD_2_VALUE, THRESHOLD_3_VALUE, THRESHOLD_4_VALUE
)

class TestThresholds(unittest.TestCase):

    def test_tier_1_upper_bound(self):
        self.assertEqual(get_threshold(THRESHOLD_1_LIMIT), THRESHOLD_1_VALUE)

    def test_tier_2_lower_bound(self):
        self.assertEqual(get_threshold(THRESHOLD_1_LIMIT + 1), THRESHOLD_2_VALUE)

    def test_tier_2_upper_bound(self):
        self.assertEqual(get_threshold(THRESHOLD_2_LIMIT), THRESHOLD_2_VALUE)

    def test_tier_3_lower_bound(self):
        self.assertEqual(get_threshold(THRESHOLD_2_LIMIT + 1), THRESHOLD_3_VALUE)

    def test_tier_3_upper_bound(self):
        self.assertEqual(get_threshold(THRESHOLD_3_LIMIT), THRESHOLD_3_VALUE)

    def test_tier_4_lower_bound(self):
        self.assertEqual(get_threshold(THRESHOLD_3_LIMIT + 1), THRESHOLD_4_VALUE)

    def test_extremely_high_price(self):
        self.assertEqual(get_threshold(1_000_000), THRESHOLD_4_VALUE)

if __name__ == '__main__':
    unittest.main()

