"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, title, type Brand, type ConnectionResponse } from "@/lib/api";
import { Badge, ErrorNotice, PageHeading } from "@/components/ui";

export function IntegrationsPanel({ brands }: { brands: Brand[] }) {
  const [brandId, setBrandId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const selected = brands.find((b) => b.id === brandId)?.id || brands[0]?.id;
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<{ demo: boolean }>("/me") });
  const query = useQuery({ queryKey: ["connections", selected], queryFn: () => api<ConnectionResponse>(`/connections?brand_id=${encodeURIComponent(selected!)}`), enabled: !!selected && me.data?.demo === false });
  useEffect(() => {
    const result = new URLSearchParams(window.location.search).get("oauth");
    if (result) setMessage(result === "connected" ? "Account connected. You can now publish approved content." : "Connection failed or expired. Check your app permissions and callback URL, then try again.");
  }, []);
  async function connect(platform: string) {
    setBusy(true); setError(null);
    try {
      const result = await api<{ authorization_url: string }>(`/connect/${platform}`, "POST", { brand_id: selected });
      window.location.assign(result.authorization_url);
    } catch (err) { setError(err); setBusy(false); }
  }
  async function disconnect(id: string) {
    setBusy(true); setError(null);
    try { await api(`/connections/${id}`, "DELETE"); await query.refetch(); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }
  return <><PageHeading eyebrow="CONNECTED ACCOUNTS" title="Social integrations" description="Connect a social account to each brand, then publish only reviewed and approved versions." />
    {message && <div className="notice" role="status">{message}</div>}
    <ErrorNotice error={error || query.error} />
    {me.data?.demo && <div className="notice">Social OAuth and live publishing require a signed-in MongoDB workspace.</div>}
    {!brands.length && <div className="notice">Add a brand before connecting social accounts.</div>}
    <label>Brand<select value={selected || ""} onChange={(e) => setBrandId(e.target.value)} disabled={busy}>{brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
    <div className="learning-grid">{["x", "linkedin"].map((platform) => {
      const connection = query.data?.connections.find((c) => c.platform === platform);
      const provider = query.data?.providers.find((p) => p.platform === platform);
      return <section className="panel" key={platform}><div className="row"><h2>{platform === "x" ? "X" : "LinkedIn"}</h2><Badge tone={connection?.status === "active" ? "green" : "amber"}>{connection ? title(connection.status) : "Not connected"}</Badge></div>
        {connection && <><p>{connection.display_name}</p><p className="small muted">Token expiry: {new Date(connection.expires_at).toLocaleString()}</p></>}
        <p className="small muted">{platform === "x" ? "Publish posts, threads and a reviewed static. X API usage requires access and may consume paid credits." : "Publish personal-profile posts and a reviewed static. Analytics requires approved member post analytics access. Some accounts need periodic reconnection."}</p>
        {provider?.reason && <div className="notice">{provider.reason}</div>}
        <div className="row"><button className="button primary" disabled={busy || !selected || !provider?.configured || me.data?.demo !== false} onClick={() => void connect(platform)}>{connection ? "Reconnect" : "Connect"}</button>
        {connection?.status === "active" && <button className="button secondary" disabled={busy} onClick={() => void disconnect(connection.id)}>Disconnect</button>}</div>
      </section>;
    })}</div><p className="small muted">Disconnect stops future publishing with this connection. Already-published posts remain on the social platform. Instagram automation is not enabled.</p>
  </>;
}
