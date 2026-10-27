import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, ErrorNote } from "../components/ui";

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [form, setForm] = useState({ name: "", email: "" });
  const [error, setError] = useState("");

  const load = () => api.clients().then(setClients).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function add(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createClient(form);
      setForm({ name: "", email: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <header className="page-head"><h1>Clients</h1></header>
      <form className="inline-form" onSubmit={add}>
        <label>Name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>Billing email<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <button className="button primary">Add client</button>
      </form>
      <ErrorNote error={error} />
      {clients.length === 0 ? (
        <Empty title="No clients yet">Add the people you bill. Their email is where Stripe sends receipts.</Empty>
      ) : (
        <table className="table">
          <thead><tr><th>Name</th><th>Billing email</th></tr></thead>
          <tbody>
            {clients.map((c) => <tr key={c.id}><td>{c.name}</td><td>{c.email}</td></tr>)}
          </tbody>
        </table>
      )}
    </div>
  );
}
