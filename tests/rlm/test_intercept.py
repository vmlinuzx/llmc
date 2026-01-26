from llmc.rlm.sandbox.intercept import extract_tool_calls, rewrite_ast

ALLOWED = {"nav_info", "nav_ls"}

def test_extract_valid_call():
    code = "x = nav_info()"
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert not errors
    assert len(sites) == 1
    assert sites[0].tool_name == "nav_info"
    assert sites[0].target_name == "x"
    assert sites[0].args == []

def test_extract_valid_call_with_args():
    code = 'files = nav_ls("path/to/dir", recursive=True)'
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert not errors
    assert len(sites) == 1
    assert sites[0].tool_name == "nav_ls"
    assert sites[0].args == ["path/to/dir"]
    assert sites[0].kwargs == {"recursive": True}

def test_reject_bare_call():
    code = "nav_info()"
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert len(errors) == 1
    assert "must be assigned" in errors[0]

def test_reject_nested_call():
    code = "print(nav_info())"
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert len(errors) == 1
    assert "nested calls not allowed" in errors[0]

def test_reject_variable_args():
    code = "x = nav_ls(some_var)"
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert len(errors) == 1
    assert "literal constants" in errors[0]

def test_reject_multi_target():
    # x, y = ... is a Tuple target, not simple Name
    code = "x, y = nav_info()"
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert len(errors) == 1
    assert "simple variable name" in errors[0]

def test_reject_chained_assignment():
    # x = y = ... is multiple targets
    code = "x = y = nav_info()"
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert len(errors) == 1
    assert "single variable" in errors[0]

def test_rewrite_ast():
    code = """
x = nav_info()
y = 10
z = nav_ls("foo")
"""
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert len(sites) == 2
    assert not errors
    
    injections = ["__injected_0", "__injected_1"]
    new_code = rewrite_ast(code, sites, injections)
    
    assert "x = __injected_0" in new_code
    assert "y = 10" in new_code
    assert "z = __injected_1" in new_code
    assert "nav_info" not in new_code
    assert "nav_ls" not in new_code

def test_syntax_error():
    code = "x = "
    sites, errors = extract_tool_calls(code, ALLOWED)
    assert len(errors) == 1
    assert "SyntaxError" in errors[0]
