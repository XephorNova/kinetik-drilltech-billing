export interface LineItem {
  description: string;
  hsn_sac: string;
  gst_rate: number;
  quantity: number;
  rate: number;
}

export interface LineItemComputed extends LineItem {
  amount: number;
  gst_amount: number;
  total: number;
}

export interface ClientSnapshot {
  name: string;
  address: string;
  gstin: string;
  pan: string;
  email: string;
  phone: string;
  state: string;
}

export type InvoiceStatus = "unpaid" | "partial" | "paid";

export interface Invoice {
  id: string;
  invoice_no: string;
  invoice_date: string;
  due_date: string;
  client_id: string;
  client_snapshot: ClientSnapshot;
  line_items: LineItemComputed[];
  tax_type: "CGST_SGST" | "IGST";
  subtotal: number;
  cgst_total: number;
  sgst_total: number;
  igst_total: number;
  grand_total: number;
  gst_ratio: number;
  parent_id: string | null;
  remaining_line_items: LineItemComputed[] | null;
  paid_total: number;
  balance: number;
  status: InvoiceStatus;
  created_at: string;
  updated_at: string;
}

export interface InvoiceCreateInput {
  invoice_no: string;
  invoice_date: string;
  due_date: string;
  client_id: string;
  tax_type?: "CGST_SGST" | "IGST" | null;
  line_items: LineItem[];
}
