import { useEffect, useState, type ChangeEvent } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCompanyProfile, useUpdateCompanyProfile } from "../api/company";
import { ApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Label } from "../components/ui/Label";
import { Alert } from "../components/ui/Alert";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

const companySchema = z.object({
  name: z.string().min(1, "Required"),
  address: z.string().min(1, "Required"),
  gstin: z.string().min(1, "Required"),
  pan: z.string().min(1, "Required"),
  email: z.string().email("Invalid email"),
  phone: z.string().min(1, "Required"),
  bank_details: z.string().min(1, "Required"),
  state: z.string().min(1, "Required"),
});

type CompanyForm = z.infer<typeof companySchema>;

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export function SettingsPage() {
  const { data: profile, isLoading } = useCompanyProfile();
  const update = useUpdateCompanyProfile();
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CompanyForm>({ resolver: zodResolver(companySchema) });

  useEffect(() => {
    if (profile) {
      reset({
        name: profile.name,
        address: profile.address,
        gstin: profile.gstin,
        pan: profile.pan,
        email: profile.email,
        phone: profile.phone,
        bank_details: profile.bank_details,
        state: profile.state,
      });
      setLogoUrl(profile.logo_url);
    }
  }, [profile, reset]);

  const onLogoChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const dataUrl = await fileToDataUrl(file);
    setLogoUrl(dataUrl);
  };

  const onSubmit = async (values: CompanyForm) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await update.mutateAsync({ ...values, logo_url: logoUrl });
      setSuccessMessage("Company profile saved.");
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Failed to save");
    }
  };

  if (isLoading) {
    return <div className="text-slate-500">Loading…</div>;
  }

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Company Settings</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
          {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}
          {successMessage && <Alert>{successMessage}</Alert>}

          <div className="space-y-1">
            <Label htmlFor="logo">Logo</Label>
            {logoUrl && <img src={logoUrl} alt="Company logo" className="mb-2 h-16 w-auto" />}
            <input id="logo" type="file" accept="image/*" onChange={onLogoChange} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="name">Company Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-red-600">{errors.name.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="state">State</Label>
              <Input id="state" {...register("state")} />
              {errors.state && <p className="text-sm text-red-600">{errors.state.message}</p>}
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="address">Address</Label>
            <Input id="address" {...register("address")} />
            {errors.address && <p className="text-sm text-red-600">{errors.address.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="gstin">GSTIN</Label>
              <Input id="gstin" {...register("gstin")} />
              {errors.gstin && <p className="text-sm text-red-600">{errors.gstin.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="pan">PAN</Label>
              <Input id="pan" {...register("pan")} />
              {errors.pan && <p className="text-sm text-red-600">{errors.pan.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input id="email" {...register("email")} />
              {errors.email && <p className="text-sm text-red-600">{errors.email.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" {...register("phone")} />
              {errors.phone && <p className="text-sm text-red-600">{errors.phone.message}</p>}
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="bank_details">Bank Details</Label>
            <Input id="bank_details" {...register("bank_details")} />
            {errors.bank_details && <p className="text-sm text-red-600">{errors.bank_details.message}</p>}
          </div>

          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
