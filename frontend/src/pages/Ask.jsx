import { useState } from "react";
import { api } from "../api";
import { ErrorNote } from "../components/ui";

const SUGGESTIONS = [
  "How much did I earn last month after fees?",
  "Which client paid me the most this year?",
  "What did I spend most on in the last three months?",
  "Which invoices are still unpaid?",
];

const TOOL_LABELS = {
  get_period_summary: "totals",
  get_income_by_client: "income by client",
  get_expenses_by_category: "spending by category",
  list_invoices: "invoices",
};

export default function Ask() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(q) {
    const text = (q ?? question).trim();
    if (text.length < 3) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.ask(text);
      setHistory([{ q: text, ...r }, ...history]);
      setQuestion("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page narrow">
      <header className="page-head"><h1>Ask about your money</h1></header>
      <form className="ask-form" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="How much did I spend on software this quarter?" aria-label="Your question" />
        <button className="button primary" disabled={busy}>{busy ? "Looking…" : "Ask"}</button>
      </form>
      {history.length === 0 && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => submit(s)} disabled={busy}>{s}</button>)}
        </div>
      )}
      <ErrorNote error={error} />
      <ol className="answers">
        {history.map((h, i) => (
          <li key={i}>
            <p className="q">{h.q}</p>
            <p className="a">{h.answer}</p>
            {h.tools_used.length > 0 && (
              <p className="muted small">Checked {[...new Set(h.tools_used)].map((t) => TOOL_LABELS[t] ?? t).join(", ")}</p>
            )}
          </li>
        ))}
      </ol>
      <p className="muted small">Answers describe your Ledgerly data. They aren't tax or financial advice.</p>
    </div>
  );
}
