import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Invoice } from "../types/invoice";

export interface Payment {
  id: string;
  invoice_id: string;
  amount: number;
  date: string;
  mode: "Cash" | "Bank Transfer" | "UPI" | "Cheque" | "Other";
  note: string | null;
  child_invoice_id: string;
  created_at: string;
}

export interface PaymentInput {
  amount: number;
  date: string;
  mode: Payment["mode"];
  note?: string;
  selected_indices?: number[];
}

export interface PaymentCreateResponse {
  payment: Payment;
  child_invoice: Invoice;
}

export function useRecordPayment(invoiceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PaymentInput) =>
      apiFetch<PaymentCreateResponse>(`/invoices/${invoiceId}/payments`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices", "detail", invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "children", invoiceId] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "list"] });
    },
  });
}
