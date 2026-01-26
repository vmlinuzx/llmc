from llmc.rlm.sandbox.intercept import extract_tool_calls, rewrite_ast

def test_multiple_calls_per_line():
    code = "x = nav_ls('.'); y = nav_ls('..')"
    allowed = {"nav_ls"}
    
    sites, errors = extract_tool_calls(code, allowed)
    print(f"Sites: {len(sites)}")
    for s in sites:
        print(f"  Site: line={s.lineno}, col={s.col_offset}, target={s.target_name}")
    
    if errors:
        print(f"Errors: {errors}")
        
    injections = ["INJ1", "INJ2"]
    new_code = rewrite_ast(code, sites, injections)
    print(f"New code:\n{new_code}")
    
    assert "x = INJ1" in new_code
    assert "y = INJ2" in new_code

if __name__ == "__main__":
    try:
        test_multiple_calls_per_line()
    except Exception as e:
        print(f"FAILED: {e}")
