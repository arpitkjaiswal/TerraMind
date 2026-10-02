"use client";
import React, { useEffect, useState } from "react";
import type { Farm, User } from "@/types";
import { backendFetch } from "@/lib/api";

interface Props { farm: Farm; user: User; onFarmUpdated: (name: string) => void; }
type Member = Pick<User, "id" | "email" | "role" | "is_active">;
const inputStyle: React.CSSProperties = { width: "100%", background: "var(--bg-deep)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", color: "var(--text-primary)" };

export default function FarmSettings({ farm, user, onFarmUpdated }: Props) {
  const [members, setMembers] = useState<Member[]>([]);
  const [farmName, setFarmName] = useState(farm.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (user.role === "admin" || user.role === "agronomist") {
      backendFetch<Member[]>("farms/me/users").then(setMembers).catch(cause => setError(cause instanceof Error ? cause.message : "Could not load team members."));
    }
  }, [user.role]);

  async function saveFarm(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const updated = await backendFetch<Farm>("farms/me", { method: "PUT", body: JSON.stringify({ name: farmName.trim() }) });
      onFarmUpdated(updated.name); setMessage("Farm name updated.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not update the farm."); }
    finally { setBusy(false); }
  }

  async function inviteMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await backendFetch<Member>("farms/me/users", { method: "POST", body: JSON.stringify({ email: String(form.get("email")).trim(), password: String(form.get("password")) }) });
      formElement.reset();
      const rows = await backendFetch<Member[]>("farms/me/users");
      setMembers(rows); setMessage("Farmer account created for this farm.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not add this team member."); }
    finally { setBusy(false); }
  }

  return <div style={{ display: "grid", gap: 20, marginTop: 18 }}>
    {error && <p role="alert" style={{ color: "#fca5a5" }}>{error}</p>}{message && <p role="status" style={{ color: "var(--green-400)" }}>{message}</p>}
    <div><p style={{ marginBottom: 12 }}>Signed in as <strong>{user.email}</strong> · {user.role}</p><p>Farm: <strong>{farm.name}</strong></p></div>
    {user.role === "admin" && <form onSubmit={saveFarm} style={{ display: "grid", gap: 9 }}><label htmlFor="farm-name">Farm name</label><input id="farm-name" style={inputStyle} value={farmName} onChange={event => setFarmName(event.target.value)} minLength={1} maxLength={255} required /><button className="btn btn-secondary" disabled={busy || farmName.trim() === farm.name}>Save farm name</button></form>}
    {(user.role === "admin" || user.role === "agronomist") && <section style={{ display: "grid", gap: 10 }}><h3 style={{ fontSize: 15 }}>Team ({members.length})</h3>{members.map(member => <div key={member.id} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "9px 11px", background: "var(--bg-deep)", borderRadius: 8, fontSize: 12 }}><span>{member.email}</span><span style={{ color: "var(--text-muted)" }}>{member.role}{member.is_active ? "" : " · inactive"}</span></div>)}
      {user.role === "admin" && <form onSubmit={inviteMember} style={{ display: "grid", gap: 9, marginTop: 6 }}><h4 style={{ fontSize: 13 }}>Add a farmer</h4><label htmlFor="member-email">Email</label><input id="member-email" name="email" type="email" style={inputStyle} required /><label htmlFor="member-password">Temporary password</label><input id="member-password" name="password" type="password" style={inputStyle} minLength={8} autoComplete="new-password" required /><button className="btn btn-primary" disabled={busy}>Create account</button><small style={{ color: "var(--text-muted)" }}>Share the temporary password with the team member securely.</small></form>}
    </section>}
  </div>;
}
