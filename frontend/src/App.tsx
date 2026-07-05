import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LoginPage } from "./pages/LoginPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ClientsPage } from "./pages/ClientsPage";
import { InvoiceCreatePage } from "./pages/InvoiceCreatePage";
import { InvoiceListPage } from "./pages/InvoiceListPage";
import { InvoiceDetailPage } from "./pages/InvoiceDetailPage";
import { GstReportPage } from "./pages/GstReportPage";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AppShell } from "./components/AppShell";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Routes>
                    <Route path="/" element={<Navigate to="/invoices" replace />} />
                    <Route path="/invoices" element={<InvoiceListPage />} />
                    <Route path="/invoices/new" element={<InvoiceCreatePage />} />
                    <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
                    <Route path="/clients" element={<ClientsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/reports/gst" element={<GstReportPage />} />
                  </Routes>
                </AppShell>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
