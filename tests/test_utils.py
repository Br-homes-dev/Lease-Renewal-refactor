import unittest
from utils import parse_num

class TestParseNum(unittest.TestCase):
    def test_parse_valid(self):
        self.assertEqual(parse_num("$1,000.00"), 1000.00)

    def test_parse_empty(self):
        self.assertEqual(parse_num(""), 0.0)
