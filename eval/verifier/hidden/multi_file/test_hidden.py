from support import call_subject


def test_zero_tax_preserves_subtotal() -> None:
    response = call_subject(
        {
            "kind": "function",
            "module": "order",
            "name": "checkout",
            "args": [[499, 501], 0],
        }
    )
    assert response == {"ok": True, "result": 1_000}


def test_fractional_cent_tax_rounds_down() -> None:
    response = call_subject(
        {
            "kind": "function",
            "module": "order",
            "name": "checkout",
            "args": [[999], 750],
        }
    )
    assert response == {"ok": True, "result": 1_073}
