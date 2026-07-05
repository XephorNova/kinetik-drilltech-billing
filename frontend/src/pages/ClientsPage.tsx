import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useClients, useCreateClient, useUpdateClient, useDeleteClient, type Client } from "../api/clients";
import { ApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Label } from "../components/ui/Label";
import { Alert } from "../components/ui/Alert";
import { Dialog } from "../components/ui/Dialog";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";

const clientSchema = z.object({
  code: z.string().min(1, "Required"),
  name: z.string().min(1, "Required"),
  address: z.string().min(1, "Required"),
  state: z.string().min(1, "Required"),
  gstin: z.string().min(1, "Required"),
  pan: z.string().min(1, "Required"),
  email: z.string().email("Invalid email"),
  phone: z.string().min(1, "Required"),
});

type ClientForm = z.infer<typeof clientSchema>;

export function ClientsPage() {
  const { data: clients, isLoading } = useClients();
  const createClient = useCreateClient();
  const updateClient = useUpdateClient();
  const deleteClient = useDeleteClient();
  const [editing, setEditing] = useState<Client | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ClientForm>({ resolver: zodResolver(clientSchema) });

  const openCreate = () => {
    setEditing(null);
    reset({ code: "", name: "", address: "", state: "", gstin: "", pan: "", email: "", phone: "" });
    setErrorMessage(null);
    setDialogOpen(true);
  };

  const openEdit = (client: Client) => {
    setEditing(client);
    reset(client);
    setErrorMessage(null);
    setDialogOpen(true);
  };

  const onSubmit = async (values: ClientForm) => {
    setErrorMessage(null);
    try {
      if (editing) {
        await updateClient.mutateAsync({ id: editing.id, payload: values });
      } else {
        await createClient.mutateAsync(values);
      }
      setDialogOpen(false);
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : "Failed to save client");
    }
  };

  const onDelete = async (id: string) => {
    if (!window.confirm("Delete this client?")) return;
    await deleteClient.mutateAsync(id);
  };

  if (isLoading) {
    return <div className="text-slate-500">Loading…</div>;
  }

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Clients</CardTitle>
        <Button onClick={openCreate}>New Client</Button>
      </CardHeader>
      <CardContent>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-slate-500">
              <th className="py-2">Code</th>
              <th className="py-2">Name</th>
              <th className="py-2">State</th>
              <th className="py-2">Email</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {clients?.map((client) => (
              <tr key={client.id} className="border-b border-slate-100">
                <td className="py-2">{client.code}</td>
                <td className="py-2">{client.name}</td>
                <td className="py-2">{client.state}</td>
                <td className="py-2">{client.email}</td>
                <td className="space-x-2 py-2 text-right">
                  <Button variant="outline" onClick={() => openEdit(client)}>
                    Edit
                  </Button>
                  <Button variant="destructive" onClick={() => onDelete(client.id)}>
                    Delete
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen} title={editing ? "Edit Client" : "New Client"}>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            {errorMessage && <Alert variant="destructive">{errorMessage}</Alert>}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="code">Code</Label>
                <Input id="code" {...register("code")} />
                {errors.code && <p className="text-sm text-red-600">{errors.code.message}</p>}
              </div>
              <div className="space-y-1">
                <Label htmlFor="state">State</Label>
                <Input id="state" {...register("state")} />
                {errors.state && <p className="text-sm text-red-600">{errors.state.message}</p>}
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register("name")} />
              {errors.name && <p className="text-sm text-red-600">{errors.name.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="address">Address</Label>
              <Input id="address" {...register("address")} />
              {errors.address && <p className="text-sm text-red-600">{errors.address.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-3">
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
            <div className="grid grid-cols-2 gap-3">
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
            <Button type="submit" className="w-full">
              {editing ? "Save Changes" : "Create Client"}
            </Button>
          </form>
        </Dialog>
      </CardContent>
    </Card>
  );
}
