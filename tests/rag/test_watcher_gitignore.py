from llmc.rag.watcher import FileFilter


def test_file_filter_basic(tmp_path):
    # Setup .gitignore
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\nignore_me/\n!not_ignored.log")

    # Initialize filter
    ff = FileFilter(tmp_path)

    # Assertions
    # Basic ignore
    assert ff.should_ignore(tmp_path / "test.log") is True
    # Directory ignore
    assert ff.should_ignore(tmp_path / "ignore_me" / "file.txt") is True
    # Negation
    assert ff.should_ignore(tmp_path / "not_ignored.log") is False
    # Regular file
    assert ff.should_ignore(tmp_path / "regular.txt") is False
    # Always ignored
    assert ff.should_ignore(tmp_path / ".git" / "HEAD") is True
    assert ff.should_ignore(tmp_path / "node_modules" / "package.json") is True


def test_file_filter_no_gitignore(tmp_path):
    ff = FileFilter(tmp_path)
    assert ff.should_ignore(tmp_path / "test.log") is False
    assert ff.should_ignore(tmp_path / ".git" / "HEAD") is True


def test_file_filter_nested_patterns(tmp_path):
    # Setup .gitignore with globstar
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("**/temp/")

    ff = FileFilter(tmp_path)

    assert ff.should_ignore(tmp_path / "a" / "temp" / "file.txt") is True
    assert ff.should_ignore(tmp_path / "temp" / "file.txt") is True
    assert ff.should_ignore(tmp_path / "a" / "b" / "file.txt") is False
