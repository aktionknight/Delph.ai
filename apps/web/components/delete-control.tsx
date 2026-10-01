"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ErrorNotice } from "@/components/ui";

export function DeleteControl({ kind, id, disabled }: { kind: "asset" | "campaign"; id: string; disabled?: boolean }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const client = useQueryClient();
  const router = useRouter();
  async function remove() {
    setBusy(true); setError(null);
    try {
      await api(`/${kind}s/${id}`, "DELETE");
      if (kind === "campaign") router.replace("/campaigns");
      await client.invalidateQueries({ queryKey: ["campaigns"] });
      await client.invalidateQueries({ queryKey: ["campaign"] });
      await client.invalidateQueries({ queryKey: ["analytics"] });
    } catch (err) { setError(err); setBusy(false); }
  }
  return <div><ErrorNotice error={error} />{confirming ? <div className="notice"><div><p>Delete this {kind}{kind === "campaign" ? " and all its assets" : ", versions and related experiments"}? Stored media will be removed and queued posts cancelled. Already-published social posts remain. This cannot be undone.</p><div className="row"><button className="button secondary" disabled={busy} onClick={() => setConfirming(false)}>Keep {kind}</button><button className="button secondary" disabled={busy || disabled} onClick={() => void remove()}>{busy ? "Deleting…" : "Confirm deletion"}</button></div></div></div> : <button className="button secondary" disabled={disabled || busy} onClick={() => setConfirming(true)}>Delete {kind}</button>}</div>;
}
