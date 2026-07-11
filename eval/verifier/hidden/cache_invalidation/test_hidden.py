from support import call_subject


def test_repeated_restock_invalidates_each_cached_total() -> None:
    response = call_subject(
        {
            "kind": "sequence",
            "module": "catalog",
            "name": "Inventory",
            "calls": [
                ["restock", ["paper", 2]],
                ["total_units", []],
                ["restock", ["paper", 4]],
                ["total_units", []],
                ["restock", ["ink", 1]],
                ["total_units", []],
            ],
        }
    )
    assert response == {"ok": True, "result": [None, 2, None, 6, None, 7]}
