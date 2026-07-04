def split_remaining_items(
    remaining_line_items: list[dict], payment_amount: float
) -> tuple[list[dict], list[dict]]:
    target = round(payment_amount, 2)
    total_available = round(sum(item["total"] for item in remaining_line_items), 2)
    if target > total_available:
        raise ValueError("payment amount exceeds remaining invoice balance")

    consumed = []
    updated = []
    running_total = 0.0
    split_done = False

    for item in remaining_line_items:
        if split_done:
            updated.append(item)
            continue

        if round(running_total + item["total"], 2) <= target:
            consumed.append(dict(item))
            running_total = round(running_total + item["total"], 2)
            if running_total >= target:
                split_done = True
            continue

        needed = round(target - running_total, 2)
        fraction = needed / item["total"]
        taken_amount = round(item["amount"] * fraction, 2)
        taken_gst = round(needed - taken_amount, 2)
        taken_quantity = round(item["quantity"] * fraction, 6)
        consumed.append({
            "description": item["description"],
            "hsn_sac": item["hsn_sac"],
            "gst_rate": item["gst_rate"],
            "quantity": taken_quantity,
            "rate": item["rate"],
            "amount": taken_amount,
            "gst_amount": taken_gst,
            "total": needed,
        })
        running_total = target
        split_done = True

        leftover_amount = round(item["amount"] - taken_amount, 2)
        leftover_gst = round(item["gst_amount"] - taken_gst, 2)
        leftover_quantity = round(item["quantity"] - taken_quantity, 6)
        leftover_total = round(item["total"] - needed, 2)
        if leftover_total > 0:
            updated.append({
                "description": item["description"],
                "hsn_sac": item["hsn_sac"],
                "gst_rate": item["gst_rate"],
                "quantity": leftover_quantity,
                "rate": item["rate"],
                "amount": leftover_amount,
                "gst_amount": leftover_gst,
                "total": leftover_total,
            })

    return consumed, updated
