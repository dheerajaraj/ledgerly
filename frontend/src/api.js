const BASE = import.meta.env.VITE_API_URL || "";
const TOKEN_KEY = "ledgerly_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function errorMessage(body, status) {
  if (!body) return `Request failed (${status}).`;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail.map((d) => `${d.loc?.slice(-1)[0] ?? "field"}: ${d.msg}`).join("; ");
  }
  return `Request failed (${status}).`;
}

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event("ledgerly:unauthorized"));
    throw new ApiError(errorMessage(data, res.status), res.status);
  }
  return data;
}

export const api = {
  register: (b) => request("/api/auth/register", { method: "POST", body: b }),
  login: (b) => request("/api/auth/login", { method: "POST", body: b }),
  me: () => request("/api/auth/me"),
  health: () => request("/api/health"),

  clients: () => request("/api/clients"),
  createClient: (b) => request("/api/clients", { method: "POST", body: b }),

  invoices: () => request("/api/invoices"),
  createInvoice: (b) => request("/api/invoices", { method: "POST", body: b }),
  invoice: (id) => request(`/api/invoices/${id}`),
  paymentLink: (id) => request(`/api/invoices/${id}/payment-link`, { method: "POST" }),
  voidInvoice: (id) => request(`/api/invoices/${id}/void`, { method: "POST" }),

  categories: () => request("/api/expenses/categories"),
  expenses: (month) => request(`/api/expenses${month ? `?month=${month}` : ""}`),
  createExpense: (b) => request("/api/expenses", { method: "POST", body: b }),
  updateExpense: (id, b) => request(`/api/expenses/${id}`, { method: "PATCH", body: b }),
  deleteExpense: (id) => request(`/api/expenses/${id}`, { method: "DELETE" }),
  importCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/expenses/import-csv", { method: "POST", form });
  },

  dashboard: (month) => request(`/api/dashboard${month ? `?month=${month}` : ""}`),
  summary: (month) => request(`/api/insights/summary${month ? `?month=${month}` : ""}`, { method: "POST" }),
  ask: (question) => request("/api/insights/ask", { method: "POST", body: { question } }),
};
