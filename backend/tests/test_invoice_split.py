from app.services.invoice_split import split_remaining_items


def _item(desc, hsn, gst_rate, qty, rate):
    amount = round(qty * rate, 2)
    gst_amount = round(amount * gst_rate / 100, 2)
    total = round(amount + gst_amount, 2)
    return {
        "description": desc, "hsn_sac": hsn, "gst_rate": gst_rate,
        "quantity": qty, "rate": rate, "amount": amount, "gst_amount": gst_amount, "total": total,
    }


def test_consumes_whole_item_when_it_exactly_matches_payment():
    items = [_item("Bore hole no 1", "995432", 18.0, 10, 1000)]
    consumed, updated = split_remaining_items(items, 11800.0)
    assert len(consumed) == 1
    assert consumed[0]["total"] == 11800.0
    assert consumed[0]["quantity"] == 10
    assert updated == []


def test_splits_single_item_by_partial_quantity():
    items = [_item("Bore hole no 1", "995432", 18.0, 10, 1000)]
    consumed, updated = split_remaining_items(items, 5000.0)
    assert len(consumed) == 1
    assert consumed[0]["total"] == 5000.0
    assert round(consumed[0]["amount"] + consumed[0]["gst_amount"], 2) == 5000.0
    assert len(updated) == 1
    assert updated[0]["total"] == 6800.0
    assert round(updated[0]["amount"] + updated[0]["gst_amount"], 2) == 6800.0


def test_consumes_whole_items_then_splits_the_next_one():
    items = [
        _item("Bore hole no 1", "995432", 18.0, 10, 1000),   # total 11800
        _item("Bore hole no 2", "995432", 18.0, 5, 2000),    # total 11800
    ]
    consumed, updated = split_remaining_items(items, 15000.0)
    assert len(consumed) == 2
    assert consumed[0]["total"] == 11800.0
    assert consumed[0]["quantity"] == 10
    assert consumed[1]["total"] == 3200.0
    assert round(sum(c["total"] for c in consumed), 2) == 15000.0

    assert len(updated) == 1
    assert updated[0]["total"] == 8600.0
    assert round(updated[0]["amount"] + updated[0]["gst_amount"], 2) == 8600.0


def test_second_payment_consumes_remaining_leftover_exactly():
    items = [
        _item("Bore hole no 1", "995432", 18.0, 10, 1000),
        _item("Bore hole no 2", "995432", 18.0, 5, 2000),
    ]
    _, updated_after_first = split_remaining_items(items, 15000.0)
    consumed, updated_after_second = split_remaining_items(updated_after_first, 8600.0)
    assert len(consumed) == 1
    assert consumed[0]["total"] == 8600.0
    assert updated_after_second == []


def test_raises_when_payment_exceeds_remaining_balance():
    items = [_item("Bore hole no 1", "995432", 18.0, 10, 1000)]
    try:
        split_remaining_items(items, 11800.01)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "exceeds" in str(exc)


def test_raises_when_no_remaining_items():
    try:
        split_remaining_items([], 100.0)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_items_after_the_split_point_are_carried_through_untouched():
    items = [
        _item("Bore hole no 1", "995432", 18.0, 10, 1000),   # total 11800
        _item("Bore hole no 2", "995432", 18.0, 5, 2000),    # total 11800
        _item("Bore hole no 3", "995432", 18.0, 2, 500),     # total 1180
    ]
    consumed, updated = split_remaining_items(items, 15000.0)
    assert len(consumed) == 2  # item 1 whole, item 2 partially split
    assert len(updated) == 2   # item 2's leftover, plus item 3 untouched
    untouched = [u for u in updated if u["description"] == "Bore hole no 3"]
    assert len(untouched) == 1
    assert untouched[0]["total"] == 1180.0
    assert untouched[0] is not items[2]
