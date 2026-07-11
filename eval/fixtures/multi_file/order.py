from pricing import taxed_total


def checkout(line_totals_cents: tuple[int, ...], tax_basis_points: int) -> int:
    return taxed_total(sum(line_totals_cents), tax_basis_points)
