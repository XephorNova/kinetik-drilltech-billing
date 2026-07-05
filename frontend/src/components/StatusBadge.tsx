import { Badge } from "./ui/Badge";
import type { InvoiceStatus } from "../types/invoice";

const VARIANTS: Record<InvoiceStatus, "default" | "success" | "warning"> = {
  unpaid: "default",
  partial: "warning",
  paid: "success",
};

const LABELS: Record<InvoiceStatus, string> = {
  unpaid: "Unpaid",
  partial: "Partial",
  paid: "Paid",
};

export function StatusBadge({ status }: { status: InvoiceStatus }) {
  return <Badge variant={VARIANTS[status]}>{LABELS[status]}</Badge>;
}
