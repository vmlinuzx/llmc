from pathlib import Path

from llmc.routing.content_type import classify_slice


def test_classify_python():
    res = classify_slice(Path("foo.py"), None, "print('hello')")
    assert res.slice_type == "code"
    assert res.slice_language == "python"
    assert res.confidence == 1.0

def test_classify_shebang():
    res = classify_slice(Path("foo"), None, "#!/usr/bin/env python3")
    assert res.slice_type == "code"
    assert res.slice_language == "python"
    assert res.confidence == 1.0

def test_classify_bash_shebang():
    res = classify_slice(Path("script.sh"), None, "#!/bin/bash")
    assert res.slice_type == "code"
    assert res.slice_language == "shell"

def test_classify_markdown():
    res = classify_slice(Path("README.md"), None, "# Hello")
    assert res.slice_type == "docs"

def test_classify_config():
    res = classify_slice(Path("config.yaml"), None, "foo: bar")
    assert res.slice_type == "config"

def test_classify_data():
    res = classify_slice(Path("data.csv"), None, "a,b,c")
    assert res.slice_type == "data"

def test_classify_unknown():
    res = classify_slice(Path("unknown.xyz"), None, "content")
    assert res.slice_type == "other"
