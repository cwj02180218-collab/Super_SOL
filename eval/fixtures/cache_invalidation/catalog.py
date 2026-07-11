class Inventory:
    def __init__(self) -> None:
        self._stock: dict[str, int] = {}
        self._cached_total: int | None = None

    def restock(self, item: str, units: int) -> None:
        self._stock[item] = self._stock.get(item, 0) + units

    def total_units(self) -> int:
        if self._cached_total is None:
            self._cached_total = sum(self._stock.values())
        return self._cached_total
