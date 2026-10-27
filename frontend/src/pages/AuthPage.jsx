import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ErrorNote } from "../components/ui";

export default function AuthPage({ mode }) {
  const { user, signIn, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  if (user) return <Navigate to="/" replace />;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (isRegister) await register(form.name, form.email, form.password);
      else await signIn(form.email, form.password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <div className="auth-intro">
        <h1 className="auth-title">Ledgerly</h1>
        <p className="auth-equation">
          <span className="in">invoices paid</span> − <span className="out">what you spent</span> = what you kept
        </p>
        <p className="muted">Send clients a payment link, log expenses, and see where your month went.</p>
      </div>
      <form className="auth-form" onSubmit={submit}>
        <h2>{isRegister ? "Create your account" : "Sign in"}</h2>
        {isRegister && (
          <label>Your name<input value={form.name} onChange={set("name")} autoComplete="name" /></label>
        )}
        <label>Email<input type="email" required value={form.email} onChange={set("email")} autoComplete="email" /></label>
        <label>
          Password
          <input type="password" required minLength={isRegister ? 8 : undefined} value={form.password}
            onChange={set("password")} autoComplete={isRegister ? "new-password" : "current-password"} />
        </label>
        <ErrorNote error={error} />
        <button className="button primary" disabled={busy}>{busy ? "One moment…" : isRegister ? "Create account" : "Sign in"}</button>
        <p className="muted small">
          {isRegister ? <>Have an account? <Link to="/signin">Sign in</Link></> : <>New here? <Link to="/register">Create an account</Link></>}
        </p>
        {!isRegister && <p className="muted small">Demo: demo@ledgerly.app / demo12345 (after running seed.py)</p>}
      </form>
    </div>
  );
}
