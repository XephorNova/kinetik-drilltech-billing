import type { LineItem } from "../types/invoice";
import { computeLineItem } from "../lib/gstCalc";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";

export function LineItemsEditor({ items, onChange }: { items: LineItem[]; onChange: (items: LineItem[]) => void }) {
  const addItem = (item: LineItem) => onChange([...items, item]);

  const addBoreHole = () => {
    const count = items.filter((i) => i.description.startsWith("Bore hole no")).length + 1;
    addItem({ description: `Bore hole no ${count}`, hsn_sac: "995432", gst_rate: 18, quantity: 1, rate: 0 });
  };

  const addMobilization = () => addItem({ description: "Mobilization", hsn_sac: "995432", gst_rate: 18, quantity: 1, rate: 0 });

  const addCustom = () => addItem({ description: "", hsn_sac: "", gst_rate: 18, quantity: 1, rate: 0 });

  const updateItem = (index: number, patch: Partial<LineItem>) => {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Button type="button" variant="outline" onClick={addBoreHole}>
          + Bore Hole
        </Button>
        <Button type="button" variant="outline" onClick={addMobilization}>
          + Mobilization
        </Button>
        <Button type="button" variant="outline" onClick={addCustom}>
          + Custom
        </Button>
      </div>

      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-slate-500">
            <th className="py-2">Description</th>
            <th className="py-2">HSN/SAC</th>
            <th className="py-2">GST %</th>
            <th className="py-2">Qty</th>
            <th className="py-2">Rate</th>
            <th className="py-2">Amount</th>
            <th className="py-2">GST Amt</th>
            <th className="py-2"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const computed = computeLineItem(item);
            return (
              <tr key={index} className="border-b border-slate-100">
                <td className="py-1 pr-2">
                  <Input value={item.description} onChange={(e) => updateItem(index, { description: e.target.value })} />
                </td>
                <td className="py-1 pr-2">
                  <Input value={item.hsn_sac} onChange={(e) => updateItem(index, { hsn_sac: e.target.value })} />
                </td>
                <td className="w-20 py-1 pr-2">
                  <Input type="number" value={item.gst_rate} onChange={(e) => updateItem(index, { gst_rate: Number(e.target.value) })} />
                </td>
                <td className="w-24 py-1 pr-2">
                  <Input type="number" value={item.quantity} onChange={(e) => updateItem(index, { quantity: Number(e.target.value) })} />
                </td>
                <td className="w-28 py-1 pr-2">
                  <Input type="number" value={item.rate} onChange={(e) => updateItem(index, { rate: Number(e.target.value) })} />
                </td>
                <td className="py-1 pr-2 whitespace-nowrap text-slate-700">₹{computed.amount.toFixed(2)}</td>
                <td className="py-1 pr-2 whitespace-nowrap text-slate-700">₹{computed.gst_amount.toFixed(2)}</td>
                <td className="py-1">
                  <Button type="button" variant="ghost" onClick={() => removeItem(index)}>
                    Remove
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
