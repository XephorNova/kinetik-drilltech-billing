import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface CompanyProfile {
  id: string;
  name: string;
  address: string;
  gstin: string;
  pan: string;
  email: string;
  phone: string;
  bank_details: string;
  logo_url: string | null;
  state: string;
}

export type CompanyProfileInput = Omit<CompanyProfile, "id">;

export function useCompanyProfile() {
  return useQuery({
    queryKey: ["company-profile"],
    queryFn: () => apiFetch<CompanyProfile>("/company-profile"),
  });
}

export function useUpdateCompanyProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CompanyProfileInput) =>
      apiFetch<CompanyProfile>("/company-profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["company-profile"], data);
    },
  });
}
