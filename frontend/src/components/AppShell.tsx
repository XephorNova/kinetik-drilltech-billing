import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useLogout } from "../api/auth";
import { cn } from "../lib/cn";
import { Button } from "./ui/Button";

const NAV_ITEMS = [
  { to: "/invoices", label: "Invoices" },
  { to: "/clients", label: "Clients" },
  { to: "/reports/gst", label: "GST Report" },
  { to: "/settings", label: "Company Settings" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const logout = useLogout();

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white p-4">
        <div className="mb-6 text-lg font-bold text-slate-900">Kinetik Drilltech</div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn("block rounded-md px-3 py-2 text-sm font-medium", isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100")
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <span className="text-sm text-slate-500">Kinetik Drilltech</span>
          <Button variant="ghost" onClick={() => logout.mutate()}>
            Logout
          </Button>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
