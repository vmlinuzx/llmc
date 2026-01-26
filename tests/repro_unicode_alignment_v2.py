from pathlib import Path
import sys

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from llmc.rlm.nav.treesitter_nav import TreeSitterNav


def test_unicode_alignment():
    print("Starting Unicode test...")
    code = "# 🚀 Rocket ship\ndef hello():\n    pass\n"
    try:
        nav = TreeSitterNav(code, language="python")
        print("Nav initialized.")
    except Exception as e:
        print(f"FAILED TO INITIALIZE: {e}")
        return
    
    symbols = nav._symbols
    print(f"Symbols found: {list(symbols.keys())}")
    
    if "hello" in symbols:
        node = symbols["hello"]
        print(f"Signature for 'hello': {repr(node.signature)}")
        if "def hello()" not in node.signature:
            print(f"MISALIGNMENT DETECTED: Expected 'def hello()', got {repr(node.signature)}")
    else:
        print("FAIL: 'hello' not found in symbols")

if __name__ == "__main__":
    test_unicode_alignment()
