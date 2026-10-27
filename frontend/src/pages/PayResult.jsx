import { useParams } from "react-router-dom";

export default function PayResult() {
  const { result } = useParams();
  const ok = result === "success";
  return (
    <div className="pay-result">
      <h1>{ok ? "Payment received" : "Payment cancelled"}</h1>
      <p className="muted">
        {ok ? "Thanks. Your payment went through and a receipt is on its way to your email."
            : "No charge was made. You can use the same link again when you're ready."}
      </p>
    </div>
  );
}
