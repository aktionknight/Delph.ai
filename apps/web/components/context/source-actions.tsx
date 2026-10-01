"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Source } from "@/lib/api";
import { ErrorNotice } from "@/components/ui";

export function SourceActions({ brandId, source }: { brandId: string; source: Source }) {
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const mutation = useMutation({ mutationFn: () => api(`/brands/${brandId}/sources/${source.id}`, "DELETE"), onSuccess: () => void client.invalidateQueries({ queryKey: ["brands"] }) });
  return <div><p className="small muted">Removing a source excludes it from future retrieval and can invalidate asset grounding. Existing campaign versions retain their historical citations.</p>{source.blob && <a className="button secondary" href={`/api/brands/${brandId}/sources/${source.id}/download`}>Download original</a>}{confirming ? <div className="notice"><div><p>Remove {source.name} from this brand?</p><div className="row"><button type="button" className="button secondary" disabled={mutation.isPending} onClick={() => { setConfirming(false); mutation.reset(); }}>Keep source</button><button type="button" className="button danger" disabled={mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? "Removing…" : "Confirm removal"}</button></div></div></div> : <button type="button" className="button danger" onClick={() => setConfirming(true)}>Remove source</button>}<ErrorNotice error={mutation.error} /></div>;
}
