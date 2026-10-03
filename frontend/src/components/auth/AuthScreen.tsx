"use client";
import React, { useState } from "react";
import { Leaf, LogIn, UserPlus, ShieldCheck } from "lucide-react";
import { authRequest } from "@/lib/api";
import type { User } from "@/types";
import styles from "./AuthScreen.module.css";

interface Props {
  onAuthenticated: (user: User) => void;
  onPreviewDemo: () => void;
}

export default function AuthScreen({ onAuthenticated, onPreviewDemo }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [farmName, setFarmName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password.length < 8) { setError("Use a password with at least 8 characters."); return; }
    if (mode === "register" && farmName.trim().length < 2) { setError("Enter your farm or organization name."); return; }
    setBusy(true);
    try {
      const user = await authRequest<User>(mode === "login" ? "login" : "register", {
        method: "POST",
        body: JSON.stringify(mode === "login" ? { email: email.trim(), password } : { email: email.trim(), password, farm_name: farmName.trim() }),
      });
      onAuthenticated(user);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not reach the authentication service.");
    } finally { setBusy(false); }
  }

  return <main className={styles.page}>
    <section className={styles.card}>
      <div className={styles.brand}><span className={styles.logo}><Leaf size={21} /></span><span>TerraMind</span></div>
      <div className={styles.icon}><ShieldCheck size={22} /></div>
      <h1>{mode === "login" ? "Sign in to your farm" : "Create your farm account"}</h1>
      <p className={styles.subtitle}>Secure access to your farm records and field tools.</p>
      <form onSubmit={submit} className={styles.form}>
        {mode === "register" && <label>Farm or organization name<input autoComplete="organization" value={farmName} onChange={event => setFarmName(event.target.value)} maxLength={255} required /></label>}
        <label>Email<input type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required maxLength={320} /></label>
        <label>Password<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={event => setPassword(event.target.value)} required minLength={8} /></label>
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button type="submit" className={styles.submit} disabled={busy}>{mode === "login" ? <LogIn size={16} /> : <UserPlus size={16} />}{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
      <button type="button" className={styles.modeButton} onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
        {mode === "login" ? "New to TerraMind? Create an account" : "Already have an account? Sign in"}
      </button>
      <div className={styles.divider}><span>or</span></div>
      <button type="button" className={styles.preview} onClick={onPreviewDemo}>Preview the sample dashboard</button>
      <p className={styles.note}>Secure sign-in needs the TerraMind API configured by the site owner. Sample preview uses no account or real farm data.</p>
    </section>
  </main>;
}
