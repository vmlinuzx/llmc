
import unittest
from llmc_mcp.docgen_engine import DocgenEngine

class TestDocgenEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DocgenEngine()

    def test_simple_function(self):
        code = """
def hello(name):
    '''Says hello.'''
    pass
"""
        result = self.engine.generate(code)
        self.assertIn("#### `def hello(name)`", result)
        self.assertIn("Says hello.", result)

    def test_class(self):
        code = """
class Greeter:
    '''A class that greets.'''
    def greet(self):
        '''Greets.'''
        pass
"""
        result = self.engine.generate(code)
        self.assertIn("### Class `Greeter`", result)
        self.assertIn("A class that greets.", result)
        self.assertIn("#### `def Greeter.greet(self)`", result)

    def test_invalid_syntax(self):
        code = "def bad syntax"
        result = self.engine.generate(code)
        self.assertIn("Error parsing source code", result)

if __name__ == '__main__':
    unittest.main()
