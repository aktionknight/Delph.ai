"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api, type Brand } from "@/lib/api";
import { ErrorNotice } from "@/components/ui";

export function RemoveBrand({ brand, onRemoved }: { brand: Brand; onRemoved: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api(`/brands/${brand.id}`, "DELETE"),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["brands"] });
      await client.invalidateQueries({ queryKey: ["connections"] });
      onRemoved();
    },
  });
  return <div className="panel">
    <h2>Remove brand</h2>
    <p className="muted">Remove this brand and its source library. Remove its campaigns first to preserve campaign and publication history.</p>
    {confirming ? <div className="notice"><div>
      <p>Remove {brand.name} and its {brand.sources.length} sources? This cannot be undone. Published social posts remain online.</p>
      <div className="row">
        <button type="button" className="button secondary" disabled={mutation.isPending} onClick={() => { setConfirming(false); mutation.reset(); }}>Keep brand</button>
        <button type="button" className="button danger" disabled={mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? "Removing…" : "Confirm removal"}</button>
      </div>
    </div></div> : <button type="button" className="button danger" onClick={() => setConfirming(true)}><Trash2 size={16} /> Remove brand</button>}
    <ErrorNotice error={mutation.error} />
  </div>;
}
