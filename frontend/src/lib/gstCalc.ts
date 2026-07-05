export type TaxType = "CGST_SGST" | "IGST";

export interface LineItemInput {
  description: string;
  hsn_sac: string;
  gst_rate: number;
  quantity: number;
  rate: number;
}

export interface LineItemComputed extends LineItemInput {
  amount: number;
  gst_amount: number;
  total: number;
}

export interface InvoiceTotals {
  subtotal: number;
  cgst_total: number;
  sgst_total: number;
  igst_total: number;
  grand_total: number;
  gst_ratio: number;
}

function round2(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function deriveTaxType(companyState: string, clientState: string): TaxType {
  return companyState.trim().toLowerCase() === clientState.trim().toLowerCase() ? "CGST_SGST" : "IGST";
}

export function computeLineItem(item: LineItemInput): LineItemComputed {
  const amount = round2(item.quantity * item.rate);
  const gstAmount = round2((amount * item.gst_rate) / 100);
  const total = round2(amount + gstAmount);
  return { ...item, amount, gst_amount: gstAmount, total };
}

export function computeInvoiceTotals(lineItemsComputed: LineItemComputed[], taxType: TaxType): InvoiceTotals {
  const subtotal = round2(lineItemsComputed.reduce((sum, li) => sum + li.amount, 0));
  const totalGst = round2(lineItemsComputed.reduce((sum, li) => sum + li.gst_amount, 0));

  let cgstTotal = 0;
  let sgstTotal = 0;
  let igstTotal = 0;

  if (taxType === "CGST_SGST") {
    cgstTotal = round2(totalGst / 2);
    sgstTotal = round2(totalGst - cgstTotal);
  } else {
    igstTotal = totalGst;
  }

  const grandTotal = round2(subtotal + totalGst);
  const gstRatio = grandTotal ? Math.round((totalGst / grandTotal) * 1e6) / 1e6 : 0;

  return {
    subtotal,
    cgst_total: cgstTotal,
    sgst_total: sgstTotal,
    igst_total: igstTotal,
    grand_total: grandTotal,
    gst_ratio: gstRatio,
  };
}
