import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "../auth";
import { api } from "../api";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/invoices", label: "Invoices" },
  { to: "/clients", label: "Clients" },
  { to: "/expenses", label: "Expenses" },
  { to: "/ask", label: "Ask" },
];

export default function Layout() {
  const { user, signOut } = useAuth();
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">Ledgerly</div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className="nav-link">
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          {health && (!health.stripe_configured || !health.claude_configured) && (
            <p className="setup-note">
              {!health.stripe_configured && "Add a Stripe test key to create payment links. "}
              {!health.claude_configured && "Add an Anthropic key to turn on AI features."}
            </p>
          )}
          <p className="who">{user?.name || user?.email}</p>
          <button className="link-button" onClick={signOut}>Sign out</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
