
import importlib.metadata

def test_torch_installation():
    """
    Verifies that torch is installed and its version is correct.
    """
    try:
        version = importlib.metadata.version('torch')
        assert version == '2.9.1'
    except importlib.metadata.PackageNotFoundError:
        assert False, "Torch is not installed"
    except Exception as e:
        assert False, f"An unexpected error occurred: {e}"
