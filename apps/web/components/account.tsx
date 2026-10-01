"use client";
import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ErrorNotice, Loading } from "./ui";

type User = { id: string; name: string; email: string; company?: string; bio?: string; timezone?: string; demo: boolean };

export function AccountGate({ children }: { children: React.ReactNode }) {
  const client = useQueryClient();
  const user = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/me"), retry: false });
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api(register ? "/auth/register" : "/auth/login", "POST", data);
      client.clear(); await user.refetch();
    } catch (err) { setError(err); } finally { setBusy(false); }
  }
  if (user.isPending) return <Loading />;
  if (!user.data) return <main className="main-content"><div className="panel form-panel" style={{ maxWidth: 520, margin: "60px auto" }}><h1>{register ? "Create your workspace" : "Sign in to Delph.ai"}</h1><p className="muted">Your campaigns and Brand Brain belong to your account.</p><form onSubmit={submit} className="form-grid" style={{ gridTemplateColumns: '1fr' }}><fieldset disabled={busy}>{register && <label>Name<input name="name" required maxLength={200} autoComplete="name" /></label>}<label>Email<input name="email" type="email" required maxLength={254} autoComplete="email" /></label><label>Password<input name="password" type="password" required minLength={12} maxLength={128} autoComplete={register ? "new-password" : "current-password"} /></label><p className="small muted">Use at least 12 characters.</p><ErrorNotice error={error || user.error} /><div className="form-footer"><button className="button secondary" type="button" onClick={() => setRegister(!register)}>{register ? "Use existing account" : "Create an account"}</button><button className="button primary" type="submit">{busy ? "Saving…" : register ? "Create account" : "Sign in"}</button></div></fieldset></form></div></main>;
  return <>{children}</>;
}

export function UserProfile() {
  const client = useQueryClient();
  const user = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/me"), retry: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api("/me", "PATCH", data);
      await user.refetch();
    } catch (err) { setError(err); } finally { setBusy(false); }
  }
  async function logout() {
    try { setBusy(true); await api("/auth/logout", "POST"); client.clear(); await user.refetch(); } catch (err) { setError(err); setBusy(false); }
  }
  if (user.isPending) return <Loading />;
  if (!user.data) return null;
  if (user.data.demo) return <div className="panel"><p>Local demo workspace. No user profile available.</p></div>;
  
  return <div className="panel form-panel" style={{ maxWidth: 600, margin: "0 auto" }}>
    <h2>Your profile</h2>
    <p className="muted">{user.data.email}</p>
    <form onSubmit={submit} className="form-grid" style={{ gridTemplateColumns: '1fr' }}>
      <fieldset disabled={busy}>
        <label>Name<input name="name" required maxLength={200} defaultValue={user.data?.name} /></label>
        <label>Company<input name="company" maxLength={200} defaultValue={user.data?.company} /></label>
        <label>Bio<textarea name="bio" maxLength={2000} defaultValue={user.data?.bio} /></label>
        <label>Timezone<input name="timezone" maxLength={100} defaultValue={user.data?.timezone || "UTC"} /></label>
        <ErrorNotice error={error} />
        <div className="form-footer">
          <button className="button secondary" type="button" onClick={logout} disabled={busy}>Sign out</button>
          <button className="button primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button>
        </div>
      </fieldset>
    </form>
  </div>;
}
