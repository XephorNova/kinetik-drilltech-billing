def derive_tax_type(company_state: str, client_state: str) -> str:
    if company_state.strip().lower() == client_state.strip().lower():
        return "CGST_SGST"
    return "IGST"


def compute_line_item(item) -> dict:
    amount = round(item.quantity * item.rate, 2)
    gst_amount = round(amount * item.gst_rate / 100, 2)
    total = round(amount + gst_amount, 2)
    return {
        "description": item.description,
        "hsn_sac": item.hsn_sac,
        "gst_rate": item.gst_rate,
        "quantity": item.quantity,
        "rate": item.rate,
        "amount": amount,
        "gst_amount": gst_amount,
        "total": total,
    }


def compute_invoice_totals(line_items_computed: list[dict], tax_type: str) -> dict:
    subtotal = round(sum(li["amount"] for li in line_items_computed), 2)
    total_gst = round(sum(li["gst_amount"] for li in line_items_computed), 2)

    if tax_type == "CGST_SGST":
        cgst_total = round(total_gst / 2, 2)
        sgst_total = round(total_gst - cgst_total, 2)
        igst_total = 0.0
    else:
        cgst_total = 0.0
        sgst_total = 0.0
        igst_total = total_gst

    grand_total = round(subtotal + total_gst, 2)
    gst_ratio = round(total_gst / grand_total, 6) if grand_total else 0.0

    return {
        "subtotal": subtotal,
        "cgst_total": cgst_total,
        "sgst_total": sgst_total,
        "igst_total": igst_total,
        "grand_total": grand_total,
        "gst_ratio": gst_ratio,
    }
