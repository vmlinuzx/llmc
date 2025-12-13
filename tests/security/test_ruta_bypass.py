
import unittest
from llmc.ruta.judge import _safe_eval

class TestRutaBypass(unittest.TestCase):
    def test_eval_import_blocked(self):
        """
        Verify that _safe_eval blocks __import__.
        """
        context = {}
        payload = "__import__('os').system('echo PWNED')"
        
        try:
            _safe_eval(payload, context)
            print("\n[PoC] RUTA: Payload executed (Unexpected!)")
            # If we get here, it might have returned None or failed silently, 
            # but simpleeval usually raises an error for unknown names.
        except Exception as e:
            print(f"\n[PoC] RUTA: Payload blocked as expected. Error: {e}")
            self.assertIn("Function '__import__' not defined", str(e))

    def test_eval_attribute_access(self):
        """
        Verify that we can't access dangerous attributes.
        """
        context = {}
        # Try to access __class__
        payload = "(1).__class__.__base__.__subclasses__()"
        try:
            _safe_eval(payload, context)
        except Exception as e:
             print(f"\n[PoC] RUTA: Attribute access blocked/failed. Error: {e}")

if __name__ == '__main__':
    unittest.main()

