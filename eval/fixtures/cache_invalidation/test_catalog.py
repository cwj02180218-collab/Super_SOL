from catalog import Inventory


def test_total_updates_after_restock() -> None:
    inventory = Inventory()
    inventory.restock("paper", 2)
    assert inventory.total_units() == 2
    inventory.restock("ink", 3)
    assert inventory.total_units() == 5
