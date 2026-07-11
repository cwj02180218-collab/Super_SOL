from order import checkout


def test_checkout_applies_basis_point_tax() -> None:
    assert checkout((1_000, 2_000), 1_000) == 3_300


def test_checkout_discards_fractional_tax_cents() -> None:
    total = checkout((101,), 500)

    assert total == 106
