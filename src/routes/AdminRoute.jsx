// src/routes/AdminRoute.jsx
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getSessionOrNull } from "../utils/session";
import { isAdmin } from "../utils/auth";

export default function AdminRoute({ children }) {
  const [status, setStatus] = useState("loading"); // loading | allowed | denied

  useEffect(() => {
    let active = true;

    (async () => {
      const session = await getSessionOrNull();
      if (!active) return;

      if (session && isAdmin(session)) {
        setStatus("allowed");
      } else {
        setStatus("denied");
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  // ---- Renderizado ----
  if (status === "loading") return <div>Cargando…</div>;
  if (status === "denied") return <Navigate to="/no-autorizado" replace />;

  return children;
}
