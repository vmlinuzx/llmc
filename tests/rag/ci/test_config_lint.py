from llmc.rag.ci.config_lint import lint_config


def test_valid_config_passes(tmp_path) -> None:
    """Valid config returns True"""
    config_file = tmp_path / "llmc.toml"
    config_file.write_text("""
[repository]
domain = "tech_docs"

[repository.path_overrides]
"src/**" = "code"
    """)
    passed, errors = lint_config(str(config_file))
    assert passed
    assert not errors


def test_missing_repository_fails(tmp_path) -> None:
    """Missing [repository] section fails"""
    config_file = tmp_path / "llmc.toml"
    config_file.write_text("""
[embeddings]
default_profile = "docs"
    """)
    passed, errors = lint_config(str(config_file))
    assert not passed
    assert "Missing [repository] section" in errors


def test_invalid_domain_fails(tmp_path) -> None:
    """Invalid domain value fails"""
    config_file = tmp_path / "llmc.toml"
    config_file.write_text("""
[repository]
domain = "invalid_domain"
    """)
    passed, errors = lint_config(str(config_file))
    assert not passed
    assert any("Invalid domain" in e for e in errors)


def test_invalid_path_override_domain(tmp_path) -> None:
    config_file = tmp_path / "llmc.toml"
    config_file.write_text("""
[repository]
domain = "tech_docs"

[repository.path_overrides]
"docs/**" = "fake_domain"
    """)
    passed, errors = lint_config(str(config_file))
    assert not passed
    assert any("Invalid domain in path_overrides" in e for e in errors)
