from support import call_subject


def test_add_handles_mixed_signs() -> None:
    response = call_subject({"kind": "function", "module": "calc", "name": "add", "args": [-3, 8]})
    assert response == {"ok": True, "result": 5}


def test_add_handles_two_negative_values() -> None:
    response = call_subject({"kind": "function", "module": "calc", "name": "add", "args": [-3, -8]})
    assert response == {"ok": True, "result": -11}
