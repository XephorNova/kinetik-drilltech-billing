import { useState } from "react";
import { Link } from "react-router-dom";
import { useInvoices } from "../api/invoices";
import { useClients } from "../api/clients";
import { StatusBadge } from "../components/StatusBadge";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

export function InvoiceListPage() {
  const [clientId, setClientId] = useState("");
  const [status, setStatus] = useState("");
  const { data: clients } = useClients();
  const { data: invoices, isLoading } = useInvoices({ clientId: clientId || undefined, status: status || undefined });

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Invoices</CardTitle>
        <Link to="/invoices/new">
          <Button>New Invoice</Button>
        </Link>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex gap-3">
          <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={clientId} onChange={(e) => setClientId(e.target.value)}>
            <option value="">All clients</option>
            {clients?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <select className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="unpaid">Unpaid</option>
            <option value="partial">Partial</option>
            <option value="paid">Paid</option>
          </select>
        </div>

        {isLoading ? (
          <div className="text-slate-500">Loading…</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-2">Invoice No.</th>
                <th className="py-2">Date</th>
                <th className="py-2">Client</th>
                <th className="py-2">Total</th>
                <th className="py-2">Paid</th>
                <th className="py-2">Balance</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices?.map((invoice) => (
                <tr key={invoice.id} className="border-b border-slate-100">
                  <td className="py-2">
                    <Link to={`/invoices/${invoice.id}`} className="text-slate-900 hover:underline">
                      {invoice.invoice_no}
                    </Link>
                  </td>
                  <td className="py-2">{invoice.invoice_date}</td>
                  <td className="py-2">{invoice.client_snapshot.name}</td>
                  <td className="py-2">₹{invoice.grand_total.toFixed(2)}</td>
                  <td className="py-2">₹{invoice.paid_total.toFixed(2)}</td>
                  <td className="py-2">₹{invoice.balance.toFixed(2)}</td>
                  <td className="py-2">
                    <StatusBadge status={invoice.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
