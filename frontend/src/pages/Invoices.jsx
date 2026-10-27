import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { money, shortDate, toCents } from "../format";
import { Empty, ErrorNote, StatusPill } from "../components/ui";

const blank = { client_id: "", description: "", amount: "", due_date: "" };

export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  const load = () => api.invoices().then(setInvoices).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    api.clients().then(setClients).catch(() => {});
  }, []);

  // While any invoice is awaiting payment, poll so the webhook's update shows up on its own.
  useEffect(() => {
    if (!invoices.some((i) => i.status === "open")) return;
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, [invoices]);

  async function create(e) {
    e.preventDefault();
    setError("");
    const amount_cents = toCents(form.amount);
    if (!amount_cents) return setError("Enter an amount greater than zero, like 1200 or 1,200.00.");
    try {
      await api.createInvoice({
        client_id: Number(form.client_id),
        description: form.description,
        amount_cents,
        due_date: form.due_date || null,
      });
      setForm(blank);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function act(id, fn) {
    setBusyId(id);
    setError("");
    try {
      await fn(id);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function copy(inv) {
    await navigator.clipboard.writeText(inv.checkout_url);
    setCopiedId(inv.id);
    setTimeout(() => setCopiedId(null), 1800);
  }

  if (clients.length === 0 && invoices.length === 0) {
    return (
      <div className="page">
        <header className="page-head"><h1>Invoices</h1></header>
        <Empty title="Add a client first">Invoices are billed to a client. <Link to="/clients">Add your first client</Link></Empty>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-head"><h1>Invoices</h1></header>

      <form className="inline-form" onSubmit={create}>
        <label>Client
          <select required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })}>
            <option value="">Choose…</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="grow">What it's for<input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Landing page build" /></label>
        <label>Amount (USD)<input required inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="1,200.00" /></label>
        <label>Due<input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></label>
        <button className="button primary">Create invoice</button>
      </form>
      <ErrorNote error={error} />

      {invoices.length === 0 ? (
        <Empty title="No invoices yet">Create one above, then send your client the payment link.</Empty>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Client</th><th>For</th><th>Due</th><th className="num">Amount</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td>{inv.client_name}</td>
                  <td>{inv.description}</td>
                  <td>{inv.due_date ? shortDate(inv.due_date) : "—"}</td>
                  <td className="num">
                    {money(inv.amount_cents)}
                    {inv.payment && <span className="sub">{money(inv.payment.net_cents)} after fees</span>}
                  </td>
                  <td><StatusPill status={inv.status} /></td>
                  <td className="actions">
                    {["draft", "expired"].includes(inv.status) || (inv.status === "open" && !inv.checkout_url) ? (
                      <button className="button small" disabled={busyId === inv.id} onClick={() => act(inv.id, api.paymentLink)}>
                        {busyId === inv.id ? "Creating…" : "Create payment link"}
                      </button>
                    ) : null}
                    {inv.status === "open" && inv.checkout_url && (
                      <>
                        <button className="button small" onClick={() => copy(inv)}>{copiedId === inv.id ? "Copied" : "Copy link"}</button>
                        <a className="button small ghost" href={inv.checkout_url} target="_blank" rel="noreferrer">Open</a>
                      </>
                    )}
                    {["draft", "open", "expired"].includes(inv.status) && (
                      <button className="link-button" disabled={busyId === inv.id} onClick={() => act(inv.id, api.voidInvoice)}>Void</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small">Invoices switch to Paid when Stripe confirms the payment. In test mode, pay with card 4242 4242 4242 4242, any future date and any CVC.</p>
    </div>
  );
}
