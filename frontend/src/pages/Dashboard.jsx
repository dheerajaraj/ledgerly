import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { money, moneyShort, monthLabel, shiftMonth, thisMonth } from "../format";
import { ErrorNote } from "../components/ui";

// Recharts sets SVG attributes, which can't read CSS variables, so resolve them once.
function useThemeColors() {
  const read = () => {
    const s = getComputedStyle(document.documentElement);
    const v = (n) => s.getPropertyValue(n).trim();
    return { income: v("--income"), expense: v("--expense"), rule: v("--rule"), muted: v("--muted"), surface: v("--surface"), ink: v("--ink") };
  };
  const [c, setC] = useState(read);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setC(read());
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return c;
}

function Equation({ s }) {
  return (
    <section className="equation" aria-label="This month's profit">
      <div className="term">
        <span className="figure in">{money(s.gross_income_cents)}</span>
        <span className="term-label">paid by clients</span>
      </div>
      <span className="op" aria-hidden>−</span>
      <div className="term">
        <span className="figure fee">{money(s.stripe_fees_cents)}</span>
        <span className="term-label">Stripe fees</span>
      </div>
      <span className="op" aria-hidden>−</span>
      <div className="term">
        <span className="figure out">{money(s.expenses_cents)}</span>
        <span className="term-label">expenses</span>
      </div>
      <span className="op" aria-hidden>=</span>
      <div className="term result">
        <span className={`figure ${s.profit_cents < 0 ? "out" : ""}`}>{money(s.profit_cents)}</span>
        <span className="term-label">you kept</span>
      </div>
    </section>
  );
}

export default function Dashboard() {
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [summarizing, setSummarizing] = useState(false);
  const colors = useThemeColors();

  useEffect(() => {
    setSummary(null);
    api.dashboard(month).then(setData).catch((e) => setError(e.message));
  }, [month]);

  async function writeSummary() {
    setSummarizing(true);
    try {
      setSummary(await api.summary(month));
    } catch (e) {
      setError(e.message);
    } finally {
      setSummarizing(false);
    }
  }

  if (!data) return error ? <ErrorNote error={error} /> : <p className="muted">Loading…</p>;
  const { summary: s, series, expenses_by_category: cats, income_by_client: clients, outstanding } = data;
  const maxCat = Math.max(1, ...cats.map((c) => c.amount_cents));
  const chartData = series.map((p) => ({
    month: monthLabel(p.month, { month: "short" }),
    Income: p.income_cents / 100,
    Expenses: p.expenses_cents / 100,
  }));

  return (
    <div className="page">
      <header className="page-head">
        <div className="month-switch">
          <button className="icon-button" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">‹</button>
          <h1>{monthLabel(month)}</h1>
          <button className="icon-button" onClick={() => setMonth(shiftMonth(month, 1))} disabled={month >= thisMonth()} aria-label="Next month">›</button>
        </div>
      </header>
      <ErrorNote error={error} />

      <Equation s={s} />

      {outstanding.open_count > 0 && (
        <p className="outstanding">
          {money(outstanding.open_cents)} is still out across {outstanding.open_count} invoice{outstanding.open_count > 1 ? "s" : ""}
          {outstanding.overdue_count > 0 && <>, and <strong>{money(outstanding.overdue_cents)} is overdue</strong></>}.{" "}
          <Link to="/invoices">Review invoices</Link>
        </p>
      )}

      <section className="summary-block">
        {summary ? (
          <>
            <p className="summary-text">{summary.summary}</p>
            <p className="muted small">
              {summary.generated_by === "claude" ? "Written by Claude from the figures above." : "Basic summary. Add an Anthropic key for a written one."}
            </p>
          </>
        ) : (
          <button className="button" onClick={writeSummary} disabled={summarizing}>
            {summarizing ? "Writing…" : "Summarize this month"}
          </button>
        )}
      </section>

      <div className="grid-2">
        <section>
          <h2>Last six months</h2>
          <div className="chart">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} barGap={2}>
                <CartesianGrid vertical={false} stroke={colors.rule} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fill: colors.muted, fontSize: 12 }} />
                <YAxis tickLine={false} axisLine={false} width={56} tick={{ fill: colors.muted, fontSize: 12 }}
                  tickFormatter={(v) => moneyShort(v * 100)} />
                <Tooltip formatter={(v) => money(v * 100)} cursor={{ fill: colors.rule, opacity: 0.4 }}
                  contentStyle={{ background: colors.surface, border: `1px solid ${colors.rule}`, borderRadius: 6, color: colors.ink }}
                  labelStyle={{ color: colors.ink, fontWeight: 600 }} />
                <Bar dataKey="Income" fill={colors.income} radius={[2, 2, 0, 0]} />
                <Bar dataKey="Expenses" fill={colors.expense} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="legend"><span className="swatch in" /> Income after fees <span className="swatch out" /> Expenses</p>
        </section>

        <section>
          <h2>Where the money went</h2>
          {cats.length === 0 ? (
            <p className="muted">No expenses this month. <Link to="/expenses">Add one</Link></p>
          ) : (
            <ul className="bars">
              {cats.map((c) => (
                <li key={c.category}>
                  <span className="bar-label">{c.category}</span>
                  <span className="bar-track"><span className="bar-fill" style={{ width: `${(c.amount_cents / maxCat) * 100}%` }} /></span>
                  <span className="num">{money(c.amount_cents)}</span>
                </li>
              ))}
            </ul>
          )}

          <h2 className="spaced">Who paid you</h2>
          {clients.length === 0 ? (
            <p className="muted">No payments this month yet.</p>
          ) : (
            <table className="table compact">
              <tbody>
                {clients.map((c) => (
                  <tr key={c.client}>
                    <td>{c.client}</td>
                    <td className="num">{Math.round(c.share * 100)}%</td>
                    <td className="num">{money(c.gross_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
