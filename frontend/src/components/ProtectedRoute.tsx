import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStatus } from "../api/auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { data, isLoading, isError } = useAuthStatus();

  if (isLoading) {
    return <div className="p-6 text-slate-500">Loading…</div>;
  }

  if (isError || !data) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
