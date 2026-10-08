import unittest
from hello import greet


class GreetingTest(unittest.TestCase):
    def test_greet(self):
        self.assertEqual(greet(), 'Hello Agent Watchdog')


if __name__ == '__main__':
    unittest.main()
