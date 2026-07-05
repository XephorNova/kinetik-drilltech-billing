import { Document, Page, Text, View, StyleSheet, Image } from "@react-pdf/renderer";
import type { Invoice } from "../types/invoice";
import type { CompanyProfile } from "../api/company";

const styles = StyleSheet.create({
  page: { padding: 32, fontSize: 10, fontFamily: "Helvetica" },
  header: { flexDirection: "row", justifyContent: "space-between", marginBottom: 16 },
  title: { fontSize: 18, fontWeight: 700 },
  logo: { width: 60, height: 60, objectFit: "contain" },
  box: { flexDirection: "row", justifyContent: "space-between", marginBottom: 12 },
  boxHalf: { width: "48%", border: "1pt solid #ddd", padding: 8, borderRadius: 4 },
  table: { marginTop: 8, border: "1pt solid #ddd" },
  tableRow: { flexDirection: "row", borderBottom: "1pt solid #ddd" },
  tableHeaderCell: { flex: 1, padding: 4, fontWeight: 700, backgroundColor: "#f3f4f6" },
  tableCell: { flex: 1, padding: 4 },
  totals: { marginTop: 12, alignSelf: "flex-end", width: 200 },
  totalsRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 2 },
  totalsGrand: { fontWeight: 700, borderTop: "1pt solid #ddd", paddingTop: 4 },
  refLine: { marginTop: 8, fontSize: 9, color: "#666" },
});

export function InvoicePDF({
  invoice,
  company,
  parentInvoiceNo,
}: {
  invoice: Invoice;
  company: CompanyProfile;
  parentInvoiceNo?: string;
}) {
  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>{company.name}</Text>
            <Text>Invoice No: {invoice.invoice_no}</Text>
            <Text>Invoice Date: {invoice.invoice_date}</Text>
            <Text>Due Date: {invoice.due_date}</Text>
          </View>
          {company.logo_url && <Image style={styles.logo} src={company.logo_url} />}
        </View>

        {parentInvoiceNo && <Text style={styles.refLine}>Ref: Parent Invoice {parentInvoiceNo}</Text>}

        <View style={styles.box}>
          <View style={styles.boxHalf}>
            <Text style={{ fontWeight: 700 }}>Billed By</Text>
            <Text>{company.name}</Text>
            <Text>{company.address}</Text>
            <Text>GSTIN: {company.gstin}</Text>
            <Text>PAN: {company.pan}</Text>
          </View>
          <View style={styles.boxHalf}>
            <Text style={{ fontWeight: 700 }}>Billed To</Text>
            <Text>{invoice.client_snapshot.name}</Text>
            <Text>{invoice.client_snapshot.address}</Text>
            <Text>GSTIN: {invoice.client_snapshot.gstin}</Text>
            <Text>PAN: {invoice.client_snapshot.pan}</Text>
          </View>
        </View>

        <View style={styles.table}>
          <View style={styles.tableRow}>
            <Text style={styles.tableHeaderCell}>Description</Text>
            <Text style={styles.tableHeaderCell}>HSN/SAC</Text>
            <Text style={styles.tableHeaderCell}>GST%</Text>
            <Text style={styles.tableHeaderCell}>Qty</Text>
            <Text style={styles.tableHeaderCell}>Rate</Text>
            <Text style={styles.tableHeaderCell}>Total</Text>
          </View>
          {invoice.line_items.map((item, index) => (
            <View style={styles.tableRow} key={index}>
              <Text style={styles.tableCell}>{item.description}</Text>
              <Text style={styles.tableCell}>{item.hsn_sac}</Text>
              <Text style={styles.tableCell}>{item.gst_rate}%</Text>
              <Text style={styles.tableCell}>{item.quantity}</Text>
              <Text style={styles.tableCell}>{item.rate.toFixed(2)}</Text>
              <Text style={styles.tableCell}>{item.total.toFixed(2)}</Text>
            </View>
          ))}
        </View>

        <View style={styles.totals}>
          <View style={styles.totalsRow}>
            <Text>Subtotal</Text>
            <Text>{invoice.subtotal.toFixed(2)}</Text>
          </View>
          {invoice.tax_type === "CGST_SGST" ? (
            <>
              <View style={styles.totalsRow}>
                <Text>CGST</Text>
                <Text>{invoice.cgst_total.toFixed(2)}</Text>
              </View>
              <View style={styles.totalsRow}>
                <Text>SGST</Text>
                <Text>{invoice.sgst_total.toFixed(2)}</Text>
              </View>
            </>
          ) : (
            <View style={styles.totalsRow}>
              <Text>IGST</Text>
              <Text>{invoice.igst_total.toFixed(2)}</Text>
            </View>
          )}
          <View style={[styles.totalsRow, styles.totalsGrand]}>
            <Text>Grand Total</Text>
            <Text>{invoice.grand_total.toFixed(2)}</Text>
          </View>
        </View>
      </Page>
    </Document>
  );
}
