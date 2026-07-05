import { useState } from "react";
import { useGstReport, gstReportCsvUrl } from "../api/reports";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Label } from "../components/ui/Label";

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

export function GstReportPage() {
  const [month, setMonth] = useState(currentMonth());
  const { data: report, isLoading } = useGstReport(month);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Monthly GST Report</CardTitle>
        </CardHeader>
        <CardContent className="flex items-end gap-4">
          <div className="space-y-1">
            <Label htmlFor="month">Month</Label>
            <Input id="month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
          </div>
          <a
            href={gstReportCsvUrl(month)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-50"
          >
            Download CSV
          </a>
        </CardContent>
      </Card>

      {isLoading && <div className="text-slate-500">Loading…</div>}

      {report && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <SummaryTile label="Total Received" value={report.summary.total_received} />
            <SummaryTile label="Taxable Value" value={report.summary.taxable_value} />
            <SummaryTile label="Total GST Payable" value={report.summary.total_gst_payable} />
            <SummaryTile label="CGST Payable" value={report.summary.cgst_payable} />
            <SummaryTile label="SGST Payable" value={report.summary.sgst_payable} />
            <SummaryTile label="IGST Payable" value={report.summary.igst_payable} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="py-2">Invoice No.</th>
                    <th className="py-2">Client</th>
                    <th className="py-2">Date</th>
                    <th className="py-2">Amount</th>
                    <th className="py-2">GST</th>
                  </tr>
                </thead>
                <tbody>
                  {report.payments.map((row, index) => (
                    <tr key={index} className="border-b border-slate-100">
                      <td className="py-2">{row.invoice_no}</td>
                      <td className="py-2">{row.client_name}</td>
                      <td className="py-2">{row.date}</td>
                      <td className="py-2">₹{row.amount.toFixed(2)}</td>
                      <td className="py-2">₹{row.gst_portion.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-sm text-slate-500">{label}</div>
        <div className="text-xl font-semibold text-slate-900">₹{value.toFixed(2)}</div>
      </CardContent>
    </Card>
  );
}
