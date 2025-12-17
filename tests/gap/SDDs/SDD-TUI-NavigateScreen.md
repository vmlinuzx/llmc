# SDD: TUI Navigate Screen Coverage

## 1. Gap Description
The `NavigateScreen` in `llmc/tui/screens/navigate.py` lacks comprehensive testing.
Specifically:
- `action_toggle_tree` is currently a placeholder (`pass`), but `NavigateScreen` is expected to have a CSS-driven layout toggle mechanism (as per architectural memory).
- File selection and content loading logic (`on_directory_tree_file_selected`) is untested.
- Language detection for syntax highlighting is limited to a few extensions.

## 2. Target Location
`tests/tui/test_navigate_screen.py`

## 3. Test Strategy
Use `unittest.mock` (and optionally `textual` testing tools if available) to simulate TUI interactions.
1. **Instantiation Test**: Verify `NavigateScreen` can be instantiated and composed.
2. **Toggle Logic Test**: Verify `action_toggle_tree` toggles the `.expanded` class on the screen or modifies the CSS classes of child widgets (`#tree-panel`, `#nav-grid`). *Note: This test is expected to FAIL on the current code, exposing the missing implementation.*
3. **Content Loading Test**: Mock `DirectoryTree.FileSelected` event and verify that `TextArea` content updates and `language` property is set correctly.
4. **Language Detection Test**: Verify various file extensions map to correct languages (including currently unsupported ones like `.yml`, `.rs` to highlight the gap).

## 4. Implementation Details
```python
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from textual.widgets import TextArea, DirectoryTree
from llmc.tui.screens.navigate import NavigateScreen

class TestNavigateScreen(unittest.TestCase):
    def setUp(self):
        self.screen = NavigateScreen()
        self.screen.app = MagicMock()
        self.screen.app.repo_root = Path("/mock/repo")

        # Mock query_one to return mock widgets
        self.mock_code_view = MagicMock(spec=TextArea)
        self.mock_title = MagicMock()

        def query_side_effect(selector, type=None):
            if selector == "#code-view":
                return self.mock_code_view
            if selector == "#code-title":
                return self.mock_title
            raise ValueError(f"Unknown selector {selector}")

        self.screen.query_one = MagicMock(side_effect=query_side_effect)

    def test_load_file_content(self):
        """Test file content loading and language detection."""
        file_path = Path("test.py")
        with patch.object(Path, "read_text", return_value="print('hello')"):
            self.screen._load_file_content(file_path)

        self.mock_code_view.load_text.assert_called_with("print('hello')")
        self.assertEqual(self.mock_code_view.language, "python")

    def test_toggle_tree(self):
        """Test toggle tree action."""
        # This test expects the screen to have a class toggled.
        # Since implementation is missing, this serves as a regression/gap test.

        # Mock add_class/remove_class if possible, or check classes set
        self.screen.classes = set()

        # Calling the action
        self.screen.action_toggle_tree()

        # Assert expected state (e.g. 'expanded' class added)
        # Verify if 'expanded' is in self.screen.classes
        # Note: In real Textual, classes is a reactive set.
        # Here we might need to mock or inspect implementation.
        # If the code is 'pass', this assertion will fail.
        self.assertIn("expanded", self.screen.classes, "Tree toggle should add 'expanded' class")
```
