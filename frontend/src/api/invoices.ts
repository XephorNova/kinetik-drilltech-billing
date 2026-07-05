import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Invoice, InvoiceCreateInput } from "../types/invoice";

export function useSuggestInvoiceNumber(clientId: string | null, invoiceDate: string) {
  return useQuery({
    queryKey: ["invoices", "suggest-number", clientId, invoiceDate],
    queryFn: () => apiFetch<{ invoice_no: string }>(`/invoices/suggest-number?client_id=${clientId}&invoice_date=${invoiceDate}`),
    enabled: Boolean(clientId && invoiceDate),
  });
}

export function useCreateInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InvoiceCreateInput) => apiFetch<Invoice>("/invoices", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["invoices"] }),
  });
}
