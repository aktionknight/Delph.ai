"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type Source } from "@/lib/api";
import { ErrorNotice } from "@/components/ui";

export function SourceActions({ brandId, source }: { brandId: string; source: Source }) {
  const client = useQueryClient();
  const mutation = useMutation({ mutationFn: () => api(`/brands/${brandId}/sources/${source.id}`, "DELETE"), onSuccess: () => void client.invalidateQueries({ queryKey: ["brands"] }) });
  return <div><p className="small muted">Removing a source excludes it from future retrieval and can invalidate asset grounding.</p>{source.blob && <a className="button secondary" href={`/api/brands/${brandId}/sources/${source.id}/download`}>Download original</a>}<button className="button secondary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>Remove source from retrieval</button><ErrorNotice error={mutation.error} /></div>;
}
