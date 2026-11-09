"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthScreen from "@/components/auth/AuthScreen";
import LiveWorkspace from "@/components/dashboard/LiveWorkspace";
import type { User } from "@/types";
export default function LiveFarm() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [sessionError, setSessionError] = useState(false);

  useEffect(() => {
    const expired = () => { setUser(null); };
    window.addEventListener("terramind:session-expired", expired);
    return () => window.removeEventListener("terramind:session-expired", expired);
  }, []);

  useEffect(() => {
    fetch("/api/auth/session", { cache: "no-store" })
      .then(response => { if (!response.ok) throw new Error("Session unavailable"); return response.json(); })
      .then(data => setUser(data.user ?? null))
      .catch(() => setSessionError(true))
      .finally(() => setCheckingSession(false));
  }, []);

  if (checkingSession) return <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", background: "var(--bg-deep)", color: "var(--text-primary)" }}>Checking your session…</main>;
  if (sessionError) return <main style={{ padding: 40 }}><p role="alert">Sign-in is temporarily unavailable. Your session has been preserved.</p><button className="btn btn-primary" onClick={() => window.location.reload()}>Retry</button><Link className="btn btn-secondary" href="/">Explore sandbox</Link></main>;
  if (!user) return <AuthScreen onAuthenticated={setUser} onPreviewDemo={() => router.push("/")} />;
  return <LiveWorkspace user={user} onLogout={async () => { const response = await fetch("/api/auth/session", { method: "DELETE" }); if (!response.ok) { window.alert("Sign-out failed. Please try again."); return; } setUser(null); }} />;
}
