import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import Clients from "./pages/Clients";
import Expenses from "./pages/Expenses";
import Ask from "./pages/Ask";
import PayResult from "./pages/PayResult";

function Protected({ children }) {
  const { user, ready } = useAuth();
  if (!ready) return <p className="loading-screen">Loading…</p>;
  return user ? children : <Navigate to="/signin" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/signin" element={<AuthPage mode="signin" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      {/* Stripe Checkout redirects your client here; it's public on purpose */}
      <Route path="/pay/:result" element={<PayResult />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="invoices" element={<Invoices />} />
        <Route path="clients" element={<Clients />} />
        <Route path="expenses" element={<Expenses />} />
        <Route path="ask" element={<Ask />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
