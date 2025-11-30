import pytest
from llmc.routing.router import create_router, DeterministicRouter
from llmc.routing.query_type import classify_query

def test_router_factory_deterministic():
    config = {"routing": {"options": {"router_mode": "deterministic"}}}
    router = create_router(config)
    assert isinstance(router, DeterministicRouter)

def test_router_factory_default():
    config = {}
    router = create_router(config)
    assert isinstance(router, DeterministicRouter)

def test_router_equivalence():
    router = DeterministicRouter({})
    query = "def foo(): return 1"
    
    # Direct call
    expected = classify_query(query)
    
    # Router call
    actual = router.decide_route(query)
    
    assert actual == expected
    assert actual["route_name"] == "code"

def test_router_unknown_mode():
    config = {"routing": {"options": {"router_mode": "magic_ml"}}}
    with pytest.raises(ValueError, match="Unknown router_mode"):
        create_router(config)