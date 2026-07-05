import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface GstReportRow {
  id: string;
  invoice_no: string;
  client_name: string;
  date: string;
  amount: number;
  taxable_portion: number;
  cgst: number;
  sgst: number;
  igst: number;
  gst_portion: number;
}

export interface GstReportSummary {
  total_received: number;
  taxable_value: number;
  cgst_payable: number;
  sgst_payable: number;
  igst_payable: number;
  total_gst_payable: number;
}

export interface GstReport {
  summary: GstReportSummary;
  payments: GstReportRow[];
}

export function useGstReport(month: string) {
  return useQuery({
    queryKey: ["reports", "gst", month],
    queryFn: () => apiFetch<GstReport>(`/reports/gst?month=${month}`),
    enabled: Boolean(month),
  });
}

export function gstReportCsvUrl(month: string): string {
  const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  return `${apiUrl}/reports/gst/csv?month=${month}`;
}
