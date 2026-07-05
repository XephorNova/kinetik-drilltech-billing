import { useMemo, useState } from "react";
import type { Client } from "../api/clients";
import { Input } from "./ui/Input";
import { cn } from "../lib/cn";

export function ClientCombobox({
  clients,
  value,
  onChange,
}: {
  clients: Client[];
  value: string | null;
  onChange: (clientId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const selected = clients.find((c) => c.id === value) ?? null;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return clients;
    return clients.filter((c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q));
  }, [clients, query]);

  return (
    <div className="relative">
      <Input
        placeholder="Search clients…"
        value={open ? query : selected?.name ?? query}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
      />
      {open && (
        <div className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {filtered.length === 0 && <div className="px-3 py-2 text-sm text-slate-500">No clients found</div>}
          {filtered.map((client) => (
            <button
              key={client.id}
              type="button"
              className={cn("block w-full px-3 py-2 text-left text-sm hover:bg-slate-100", client.id === value && "bg-slate-100")}
              onClick={() => {
                onChange(client.id);
                setQuery("");
                setOpen(false);
              }}
            >
              {client.name} <span className="text-slate-400">({client.code})</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
