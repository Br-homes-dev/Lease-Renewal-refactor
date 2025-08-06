import unittest
from business import get_threshold

class TestThresholds(unittest.TestCase):
    def test_tier_1(self):
        self.assertEqual(get_threshold(149999), 225.0)

    def test_tier_2(self):
        self.assertEqual(get_threshold(250000), 300.0)

    def test_tier_3(self):
        self.assertEqual(get_threshold(400000), 400.0)

    def test_tier_4(self):
        self.assertEqual(get_threshold(500000), 700.0)

if __name__ == '__main__':
    unittest.main()

