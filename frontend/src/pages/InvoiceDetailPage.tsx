import { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useInvoice, useInvoiceChildren, useDeleteInvoice } from "../api/invoices";
import { useRecordPayment } from "../api/payments";
import { ApiError } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Label } from "../components/ui/Label";
import { Alert } from "../components/ui/Alert";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

const paymentSchema = z.object({
  amount: z.coerce.number().positive("Must be greater than 0"),
  date: z.string().min(1, "Required"),
  mode: z.enum(["Cash", "Bank Transfer", "UPI", "Cheque", "Other"]),
  note: z.string().optional(),
});

type PaymentForm = z.infer<typeof paymentSchema>;

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export function InvoiceDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data: invoice, isLoading } = useInvoice(id);
  const isParent = invoice ? invoice.parent_id === null : true;
  const { data: children } = useInvoiceChildren(isParent ? id : "");
  const recordPayment = useRecordPayment(id);
  const deleteInvoice = useDeleteInvoice();
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PaymentForm>({
    resolver: zodResolver(paymentSchema),
    defaultValues: { date: todayIsoDate(), mode: "Cash" },
  });

  if (isLoading || !invoice) {
    return <div className="text-slate-500">Loading…</div>;
  }

  const onRecordPayment = async (values: PaymentForm) => {
    setPaymentError(null);
    try {
      await recordPayment.mutateAsync(values);
      reset({ amount: undefined, date: todayIsoDate(), mode: "Cash", note: "" });
    } catch (err) {
      setPaymentError(err instanceof ApiError ? err.message : "Failed to record payment");
    }
  };

  const onDelete = async () => {
    if (!window.confirm("Delete this invoice and all its child invoices?")) return;
    await deleteInvoice.mutateAsync(id);
    navigate("/invoices");
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div>
            <CardTitle>{invoice.invoice_no}</CardTitle>
            {invoice.parent_id && (
              <Link to={`/invoices/${invoice.parent_id}`} className="text-sm text-slate-500 hover:underline">
                Ref: Parent Invoice
              </Link>
            )}
          </div>
          <div className="flex items-center gap-3">
            {isParent && <StatusBadge status={invoice.status} />}
            {isParent && (
              <Button variant="destructive" onClick={onDelete}>
                Delete Invoice
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-4 grid grid-cols-2 gap-4 text-sm text-slate-600">
            <div>
              <div className="font-medium text-slate-900">{invoice.client_snapshot.name}</div>
              <div>{invoice.client_snapshot.address}</div>
              <div>GSTIN: {invoice.client_snapshot.gstin}</div>
            </div>
            <div className="text-right">
              <div>Invoice Date: {invoice.invoice_date}</div>
              <div>Due Date: {invoice.due_date}</div>
              <div>Tax Type: {invoice.tax_type === "CGST_SGST" ? "CGST + SGST" : "IGST"}</div>
            </div>
          </div>

          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-2">Description</th>
                <th className="py-2">HSN/SAC</th>
                <th className="py-2">GST %</th>
                <th className="py-2">Qty</th>
                <th className="py-2">Rate</th>
                <th className="py-2">Total</th>
              </tr>
            </thead>
            <tbody>
              {invoice.line_items.map((item, index) => (
                <tr key={index} className="border-b border-slate-100">
                  <td className="py-2">{item.description}</td>
                  <td className="py-2">{item.hsn_sac}</td>
                  <td className="py-2">{item.gst_rate}%</td>
                  <td className="py-2">{item.quantity}</td>
                  <td className="py-2">₹{item.rate.toFixed(2)}</td>
                  <td className="py-2">₹{item.total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="ml-auto mt-4 max-w-xs space-y-1 text-sm">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>₹{invoice.subtotal.toFixed(2)}</span>
            </div>
            {invoice.tax_type === "CGST_SGST" ? (
              <>
                <div className="flex justify-between">
                  <span>CGST</span>
                  <span>₹{invoice.cgst_total.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>SGST</span>
                  <span>₹{invoice.sgst_total.toFixed(2)}</span>
                </div>
              </>
            ) : (
              <div className="flex justify-between">
                <span>IGST</span>
                <span>₹{invoice.igst_total.toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between font-semibold">
              <span>Grand Total</span>
              <span>₹{invoice.grand_total.toFixed(2)}</span>
            </div>
            {isParent && (
              <div className="flex justify-between text-slate-500">
                <span>Balance</span>
                <span>₹{invoice.balance.toFixed(2)}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {isParent && (
        <Card>
          <CardHeader>
            <CardTitle>Payments</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="mb-6 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="py-2">Child Invoice</th>
                  <th className="py-2">Date</th>
                  <th className="py-2">Amount</th>
                </tr>
              </thead>
              <tbody>
                {children?.map((child) => (
                  <tr key={child.id} className="border-b border-slate-100">
                    <td className="py-2">
                      <Link to={`/invoices/${child.id}`} className="text-slate-900 hover:underline">
                        {child.invoice_no}
                      </Link>
                    </td>
                    <td className="py-2">{child.invoice_date}</td>
                    <td className="py-2">₹{child.grand_total.toFixed(2)}</td>
                  </tr>
                ))}
                {children?.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-2 text-slate-500">
                      No payments recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {invoice.balance > 0 && (
              <form className="max-w-sm space-y-3" onSubmit={handleSubmit(onRecordPayment)}>
                <p className="text-sm text-slate-500">Remaining balance: ₹{invoice.balance.toFixed(2)}</p>
                {paymentError && <Alert variant="destructive">{paymentError}</Alert>}
                <div className="space-y-1">
                  <Label htmlFor="amount">Amount</Label>
                  <Input id="amount" type="number" step="0.01" {...register("amount")} />
                  {errors.amount && <p className="text-sm text-red-600">{errors.amount.message}</p>}
                </div>
                <div className="space-y-1">
                  <Label htmlFor="date">Date</Label>
                  <Input id="date" type="date" {...register("date")} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="mode">Mode</Label>
                  <select id="mode" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" {...register("mode")}>
                    <option value="Cash">Cash</option>
                    <option value="Bank Transfer">Bank Transfer</option>
                    <option value="UPI">UPI</option>
                    <option value="Cheque">Cheque</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="note">Note (optional)</Label>
                  <Input id="note" {...register("note")} />
                </div>
                <Button type="submit" disabled={recordPayment.isPending}>
                  {recordPayment.isPending ? "Recording…" : "Record Payment"}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
