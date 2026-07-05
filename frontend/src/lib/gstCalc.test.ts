import { describe, it, expect } from "vitest";
import { deriveTaxType, computeLineItem, computeInvoiceTotals } from "./gstCalc";

describe("deriveTaxType", () => {
  it("returns CGST_SGST for the same state", () => {
    expect(deriveTaxType("Maharashtra", "Maharashtra")).toBe("CGST_SGST");
  });

  it("returns IGST for different states", () => {
    expect(deriveTaxType("Maharashtra", "Gujarat")).toBe("IGST");
  });

  it("is case and whitespace insensitive", () => {
    expect(deriveTaxType(" Maharashtra ", "maharashtra")).toBe("CGST_SGST");
  });
});

describe("computeLineItem", () => {
  it("matches the Kinetik Drilltech sample invoice's bore hole line item", () => {
    const computed = computeLineItem({
      description: "Bore hole no 1",
      hsn_sac: "995432",
      gst_rate: 18,
      quantity: 20,
      rate: 1400,
    });
    expect(computed.amount).toBe(28000);
    expect(computed.gst_amount).toBe(5040);
    expect(computed.total).toBe(33040);
  });
});

describe("computeInvoiceTotals", () => {
  it("matches the full sample invoice totals", () => {
    const rows: [number, number][] = [
      [20, 1400],
      [20, 1400],
      [30, 1400],
      [20, 1400],
      [17.75, 1400],
      [20, 1400],
      [23, 1400],
      [5, 1400],
    ];
    const lineItems = rows.map(([quantity, rate]) =>
      computeLineItem({ description: "x", hsn_sac: "995432", gst_rate: 18, quantity, rate })
    );
    lineItems.push(
      computeLineItem({ description: "Mobilization", hsn_sac: "995432", gst_rate: 18, quantity: 1, rate: 15000 })
    );

    const totals = computeInvoiceTotals(lineItems, "CGST_SGST");

    expect(totals.subtotal).toBe(233050);
    expect(totals.cgst_total).toBe(20974.5);
    expect(totals.sgst_total).toBe(20974.5);
    expect(totals.igst_total).toBe(0);
    expect(totals.grand_total).toBe(274999);
    expect(Math.round(totals.gst_ratio * 10000) / 10000).toBe(0.1525);
  });

  it("puts all GST into igst_total for IGST invoices", () => {
    const lineItems = [computeLineItem({ description: "x", hsn_sac: "995432", gst_rate: 18, quantity: 1, rate: 1000 })];
    const totals = computeInvoiceTotals(lineItems, "IGST");
    expect(totals.cgst_total).toBe(0);
    expect(totals.sgst_total).toBe(0);
    expect(totals.igst_total).toBe(180);
  });

  it("rounds the same way Python's round() does for a floating-point tie at magnitude ~1 (1.005 rounds to 1, not 1.01)", () => {
    // quantity * rate = 1.005 exactly as a JS/Python double; 1.005 * 100 = 100.499...
    // Math.round(100.499...) = 100 (rounds to nearest even); 100/100 = 1
    // This proves the fix: without the old epsilon correction, we match Python's round(1.005, 2) == 1.0
    const computed = computeLineItem({
      description: "x",
      hsn_sac: "995432",
      gst_rate: 0,
      quantity: 1.005,
      rate: 1,
    });
    expect(computed.amount).toBe(1);
  });
});
