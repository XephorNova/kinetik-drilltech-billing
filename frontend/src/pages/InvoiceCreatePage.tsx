import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useClients } from "../api/clients";
import { useCompanyProfile } from "../api/company";
import { useSuggestInvoiceNumber, useCreateInvoice } from "../api/invoices";
import { ApiError } from "../api/client";
import { deriveTaxType, computeLineItem, computeInvoiceTotals } from "../lib/gstCalc";
import { todayIsoDate, addDays } from "../lib/date";
import type { LineItem } from "../types/invoice";
import { ClientCombobox } from "../components/ClientCombobox";
import { LineItemsEditor } from "../components/LineItemsEditor";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Label } from "../components/ui/Label";
import { Alert } from "../components/ui/Alert";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

export function InvoiceCreatePage() {
  const navigate = useNavigate();
  const { data: clients } = useClients();
  const { data: company } = useCompanyProfile();
  const createInvoice = useCreateInvoice();

  const [clientId, setClientId] = useState<string | null>(null);
  const [invoiceDate, setInvoiceDate] = useState(todayIsoDate());
  const [dueDate, setDueDate] = useState(addDays(todayIsoDate(), 7));
  const [invoiceNo, setInvoiceNo] = useState("");
  const [items, setItems] = useState<LineItem[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: suggestion } = useSuggestInvoiceNumber(clientId, invoiceDate);

  const [taxTypeOverride, setTaxTypeOverride] = useState<"auto" | "CGST_SGST" | "IGST">("auto");

  const selectedClient = clients?.find((c) => c.id === clientId) ?? null;

  const autoTaxType = useMemo(() => {
    if (!company || !selectedClient) return null;
    return deriveTaxType(company.state, selectedClient.state);
  }, [company, selectedClient]);

  const taxType = taxTypeOverride === "auto" ? autoTaxType : taxTypeOverride;

  const totals = useMemo(() => {
    if (!taxType) return null;
    return computeInvoiceTotals(items.map(computeLineItem), taxType);
  }, [items, taxType]);

  const effectiveInvoiceNo = invoiceNo || suggestion?.invoice_no || "";

  const onSubmit = async () => {
    setErrorMessage(null);
    if (!clientId) {
      setErrorMessage("Select a client first.");
      return;
    }
    if (!effectiveInvoiceNo) {
      setErrorMessage("Invoice number is required.");
      return;
    }
    try {
      const invoice = await createInvoice.mutateAsync({
        invoice_no: effectiveInvoiceNo,
        invoice_date: invoiceDate,
        due_date: dueDate,
        client_id: clientId,
        tax_type: taxTypeOverride === "auto" ? null : taxTypeOverride,
        line_items: items,
      });
      navigate(`/invoices/${invoice.id}`);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Failed to create invoice");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>New Invoice</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}

        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-1">
            <Label>Client</Label>
            <ClientCombobox clients={clients ?? []} value={clientId} onChange={setClientId} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="invoice_date">Invoice Date</Label>
            <Input id="invoice_date" type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="due_date">Due Date</Label>
            <Input id="due_date" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor="invoice_no">Invoice Number</Label>
          <Input id="invoice_no" value={effectiveInvoiceNo} onChange={(e) => setInvoiceNo(e.target.value)} />
        </div>

        <div className="space-y-1">
          <Label htmlFor="tax_type">Tax Type</Label>
          <select
            id="tax_type"
            className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={taxTypeOverride}
            onChange={(e) => setTaxTypeOverride(e.target.value as "auto" | "CGST_SGST" | "IGST")}
          >
            <option value="auto">
              Auto{autoTaxType ? ` (detected: ${autoTaxType === "CGST_SGST" ? "CGST + SGST" : "IGST"})` : ""}
            </option>
            <option value="CGST_SGST">CGST + SGST</option>
            <option value="IGST">IGST</option>
          </select>
        </div>

        <LineItemsEditor items={items} onChange={setItems} />

        {totals && (
          <div className="ml-auto max-w-xs space-y-1 text-sm">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>₹{totals.subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Total GST</span>
              <span>₹{(totals.cgst_total + totals.sgst_total + totals.igst_total).toFixed(2)}</span>
            </div>
            {taxType === "CGST_SGST" ? (
              <>
                <div className="flex justify-between pl-4 text-slate-500">
                  <span>CGST</span>
                  <span>₹{totals.cgst_total.toFixed(2)}</span>
                </div>
                <div className="flex justify-between pl-4 text-slate-500">
                  <span>SGST</span>
                  <span>₹{totals.sgst_total.toFixed(2)}</span>
                </div>
              </>
            ) : (
              <div className="flex justify-between pl-4 text-slate-500">
                <span>IGST</span>
                <span>₹{totals.igst_total.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between border-t border-slate-200 pt-1 font-semibold">
              <span>Grand Total</span>
              <span>₹{totals.grand_total.toFixed(2)}</span>
            </div>
          </div>
        )}

        <Button onClick={onSubmit} disabled={createInvoice.isPending}>
          {createInvoice.isPending ? "Creating…" : "Create Invoice"}
        </Button>
      </CardContent>
    </Card>
  );
}
