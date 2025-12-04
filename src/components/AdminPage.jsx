// src/components/AdminPage.jsx
import React, { useEffect, useState } from "react";
import { getSessionOrNull } from "../utils/session";
import { isAdmin } from "../utils/auth";
import "./AdminPage.css";
import { toast } from 'react-hot-toast';

const API_BASE =
  "https://" +
  "h6ysn7u0tl" +
  ".execute-api" +
  ".us-east-1" +
  ".amazonaws" +
  ".com" +
  "/dev2";

// Wrapper de fetch con token actualizado
async function apiFetch(url, opts = {}) {
  // Primer intento sin forzar refresh
  let session = await getSessionOrNull(false);
  let token =
    session?.tokens?.accessToken?.toString?.() ||
    session?.tokens?.accessToken?.jwtToken ||
    session?.tokens?.idToken?.toString?.() ||
    session?.tokens?.idToken?.jwtToken ||
    "";

  const makeRequest = async (tk) => {
    const headers = {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
      Authorization: `Bearer ${String(tk).startsWith('Bearer ') ? String(tk).slice(7) : tk}`,
    };
    return fetch(url, { ...opts, headers });
  };

  let res = await makeRequest(token);

  // Si 401, intentar una única vez forzando refresh
  if (res.status === 401) {
    try {
      session = await getSessionOrNull(true); // force refresh
      token =
        session?.tokens?.accessToken?.toString?.() ||
        session?.tokens?.accessToken?.jwtToken ||
        session?.tokens?.idToken?.toString?.() ||
        session?.tokens?.idToken?.jwtToken ||
        "";
      res = await makeRequest(token);
    } catch (e) {
      // ignore y se manejará abajo
    }
  }

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    let body;
    try { body = JSON.parse(txt); } catch { body = txt; }
    const err = new Error(body?.message || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }

  return res.headers.get("content-type")?.includes("application/json")
    ? res.json()
    : res.text();
}

export default function AdminPage() {
  const [session, setSession] = useState(null);
  const [loadingSession, setLoadingSession] = useState(true);

  const [solicitudes, setSolicitudes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Cargar sesión una sola vez
  useEffect(() => {
    let active = true;

    (async () => {
      const s = await getSessionOrNull();
      if (active) {
        setSession(s);
        setLoadingSession(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  // Derived
  const email =
    session?.tokens?.idToken?.payload?.email ??
    session?.tokens?.accessToken?.payload?.username ??
    "";

  const puedeGestionar = isAdmin(session);

  // LOAD solicitudes
  const cargarSolicitudes = async () => {
    setLoading(true);
    setError("");

    try {
      const data = await apiFetch(`${API_BASE}/obtener-solicitudes-rol`, {
        method: "GET",
      });
      setSolicitudes(Array.isArray(data?.solicitudes) ? data.solicitudes : []);
    } catch (err) {
      console.error("cargarSolicitudes", err);
      const msg = err.body?.message || err.message || "Error cargando solicitudes";
      toast.error(msg);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (session && puedeGestionar) cargarSolicitudes();
  }, [session, puedeGestionar]);

  // Acción solicitud
  const accionSolicitud = async (correo, accion) => {
    try {
      await apiFetch(`${API_BASE}/aprobar-rol`, {
        method: "POST",
        body: JSON.stringify({ correo, accion }),
      });

      cargarSolicitudes();
    } catch (err) {
      setError(err.body?.message || err.message || "Error en la acción");
    }
  };

  // ---- Render ----
  if (loadingSession) return <div>Cargando sesión…</div>;

  return (
    <div className="pagina-admin">
      <h1>Panel de Administración</h1>
      <p>Bienvenido, {email}</p>

      <button onClick={cargarSolicitudes} disabled={loading}>
        {loading ? "Actualizando…" : "↻ Actualizar"}
      </button>

      {error && <div className="error-box">{error}</div>}

      <table className="tabla-solicitudes" style={{ marginTop: 20 }}>
        <thead>
          <tr>
            <th>Correo</th>
            <th>Estado</th>
            {puedeGestionar && <th>Acciones</th>}
          </tr>
        </thead>
        <tbody>
          {solicitudes.map((s) => (
            <tr key={s.correo}>
              <td>{s.correo}</td>
              <td>{s.estado}</td>
              {puedeGestionar && (
                <td>
                  <button onClick={() => accionSolicitud(s.correo, "aprobar")}>
                    Aprobar
                  </button>
                  <button
                    onClick={() => accionSolicitud(s.correo, "rechazar")}
                    style={{ marginLeft: 8 }}
                  >
                    Rechazar
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


