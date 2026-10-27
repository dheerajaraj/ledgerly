import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { money, monthLabel, shiftMonth, shortDate, thisMonth, toCents, today } from "../format";
import { Empty, ErrorNote } from "../components/ui";

export default function Expenses() {
  const [month, setMonth] = useState(thisMonth());
  const [expenses, setExpenses] = useState([]);
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState({ date: today(), description: "", amount: "", category: "" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = () => api.expenses(month).then(setExpenses).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [month]);
  useEffect(() => { api.categories().then(setCategories).catch(() => {}); }, []);

  async function add(e) {
    e.preventDefault();
    setError("");
    const amount_cents = toCents(form.amount);
    if (!amount_cents) return setError("Enter an amount greater than zero.");
    setBusy(true);
    try {
      const exp = await api.createExpense({ date: form.date, description: form.description, amount_cents, category: form.category || null });
      setForm({ ...form, description: "", amount: "", category: "" });
      setNotice(form.category ? "" : `Filed under ${exp.category}. Change it in the table if that's wrong.`);
      setMonth(exp.date.slice(0, 7));
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function importFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.importCsv(file);
      setNotice(`Imported ${r.imported} expense${r.imported === 1 ? "" : "s"}` +
        (r.skipped_rows.length ? `. Skipped rows ${r.skipped_rows.join(", ")} (missing or unreadable values).` : "."));
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function recategorize(exp, category) {
    try {
      const updated = await api.updateExpense(exp.id, { category });
      setExpenses(expenses.map((x) => (x.id === exp.id ? updated : x)));
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(exp) {
    if (!confirm(`Delete "${exp.description}"?`)) return;
    await api.deleteExpense(exp.id).catch((e) => setError(e.message));
    load();
  }

  const total = expenses.reduce((s, e) => s + e.amount_cents, 0);

  return (
    <div className="page">
      <header className="page-head">
        <div className="month-switch">
          <button className="icon-button" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">‹</button>
          <h1>Expenses, {monthLabel(month)}</h1>
          <button className="icon-button" onClick={() => setMonth(shiftMonth(month, 1))} disabled={month >= thisMonth()} aria-label="Next month">›</button>
        </div>
        <div>
          <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={importFile} />
          <button className="button" onClick={() => fileRef.current.click()} disabled={busy}>Import CSV</button>
        </div>
      </header>

      <form className="inline-form" onSubmit={add}>
        <label>Date<input type="date" required value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></label>
        <label className="grow">Description<input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Figma subscription" /></label>
        <label>Amount<input required inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="15.00" /></label>
        <label>Category
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            <option value="">Choose for me</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <button className="button primary" disabled={busy}>{busy ? "Saving…" : "Add expense"}</button>
      </form>
      <ErrorNote error={error} />
      {notice && <p className="notice">{notice}</p>}

      {expenses.length === 0 ? (
        <Empty title="Nothing logged this month">Add an expense above, or import a CSV with date, description and amount columns.</Empty>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Date</th><th>Description</th><th>Category</th><th className="num">Amount</th><th /></tr></thead>
            <tbody>
              {expenses.map((e) => (
                <tr key={e.id}>
                  <td>{shortDate(e.date)}</td>
                  <td>{e.description}</td>
                  <td>
                    <select className="cell-select" value={e.category} onChange={(ev) => recategorize(e, ev.target.value)} aria-label={`Category for ${e.description}`}>
                      {categories.map((c) => <option key={c}>{c}</option>)}
                    </select>
                    {e.category_source === "ai" && <span className="tag" title="Chosen by Claude">auto</span>}
                    {e.category_source === "rule" && <span className="tag" title="Matched by keyword">guess</span>}
                  </td>
                  <td className="num out-text">{money(e.amount_cents)}</td>
                  <td className="actions"><button className="link-button" onClick={() => remove(e)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr><td colSpan={3}>Total</td><td className="num">{money(total)}</td><td /></tr></tfoot>
          </table>
        </div>
      )}
    </div>
  );
}
