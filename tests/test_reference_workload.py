import pytest

from kora.benchmarks.reference_workload import clean_orders


def order(key="A-1", quantity=2):
    return {"id": key, "sku": " item-1 ", "quantity": quantity, "unit_price": 1500}


def test_normalize_deduplicate_validate():
    result = clean_orders(
        [
            order(" ａ-１ "),
            order(),
            order("bad!", 2),
            order("B-2", True),
            order("C-3", 0),
            order("D-4", 3),
        ]
    )
    assert result["duplicates"] == [1]
    assert len(result["rejected"]) == 3
    assert result["total"] == 7500
    assert result["orders"][0]["id"] == "A-1"
    assert result["orders"][0]["sku"] == "ITEM-1"


def test_invalid_row_does_not_reserve_id():
    result = clean_orders([order(quantity=-1), order()])
    assert len(result["orders"]) == 1
    assert result["duplicates"] == []


@pytest.mark.parametrize("rows", [None, {}, [None] * 10001])
def test_bounded_input(rows):
    with pytest.raises(ValueError):
        clean_orders(rows)


def test_no_mutation_and_repeat_identity():
    row = order()
    first = clean_orders([row])
    assert row["sku"] == " item-1 "
    assert clean_orders([row]) == first
    row["quantity"] = 3
    assert clean_orders([row])["total"] == 4500
