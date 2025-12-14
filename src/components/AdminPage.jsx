// src/components/AdminPage.jsx
import React, { useEffect, useState } from "react"; // Eliminado useMemo
import "./AdminPage.css";
import { toast } from 'react-hot-toast';
import { fetchAuthSession } from "aws-amplify/auth";

const API_BASE =
  "https://" +
  "bnq58d43dh" +
  ".execute-api" +
  ".us-east-1" +
  ".amazonaws" +
  ".com" +
  "/dev2";

// Wrapper de fetch con extracción de token robusta
async function apiFetch(url, opts = {}) {
  let session = null;

  try {
    session = await fetchAuthSession();
  } catch (e) {
    console.warn("No session available yet. Trying refresh...");
  }

  const extractIdToken = (session) => {
    if (!session?.tokens?.idToken) return null;

    return (
      session.tokens.idToken.jwtToken ||
      session.tokens.idToken.toString?.() ||
      null
    );
  };

  let token = extractIdToken(session);

  if (!token) {
    console.log("Refreshing session...");
    session = await fetchAuthSession({ forceRefresh: true });
    token = extractIdToken(session);
  }

  if (!token) throw new Error("No token available");

  const makeRequest = (t) =>
    fetch(url, {
      ...opts,
      headers: {
        "Content-Type": "application/json",
        ...(opts.headers || {}),
        Authorization: `Bearer ${t}`,

      },
    });

  let res = await makeRequest(token);

  if (res.status === 401) {
    console.warn("401 → refreshing token...");
    session = await fetchAuthSession({ forceRefresh: true });
    token = extractIdToken(session);
    if (!token) throw new Error("No token available after refresh");
    res = await makeRequest(token);
  }

  if (!res.ok) {
    const text = await res.text();
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
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

  // pestaña activa: 'usuarios' | 'solicitudes'
  const [tab, setTab] = useState("solicitudes");

  // listado de usuarios (filtrados por backend)
  const [usuarios, setUsuarios] = useState([]);
  const [cursor, setCursor] = useState(null); // Para paginación
  const PAGE_SIZE = 20;

  const [loadingUsuarios, setLoadingUsuarios] = useState(false);
  const [filtroUsuarios, setFiltroUsuarios] = useState(""); // texto de búsqueda

  // Add state for filtering solicitudes
  const [filtroSolicitudes, setFiltroSolicitudes] = useState("");

  // Cargar sesión una sola vez
  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const auth = await fetchAuthSession();   // ← AHORA SÍ SE OBTIENEN TOKENS REALES

        if (active) {
          setSession(auth);
          setLoadingSession(false);
        }
      } catch (e) {
        console.error("Error obteniendo sesión", e);
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

  const grupos =
  session?.tokens?.idToken?.payload?.["cognito:groups"] ||
  session?.tokens?.accessToken?.payload?.["cognito:groups"] ||
  [];

  const puedeGestionar = Array.isArray(grupos) && grupos.includes("Administrador");


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

  // LOAD usuarios (filtrados por email / dominio desde backend)
  const cargarUsuarios = async (reset = false) => {
    if (!puedeGestionar) return;

    setLoadingUsuarios(true);
    setError("");

    try {
      const params = new URLSearchParams();
      params.set("limit", PAGE_SIZE);

      // Filtro por email
      if (filtroUsuarios.trim()) {
        params.set("email", filtroUsuarios.trim());
      }

      // Si no es reset, enviar el cursor
      if (!reset && cursor) {
        params.set("cursor", cursor);
      }

      const url = `${API_BASE}/listar_usuarios?${params.toString()}`;
      const data = await apiFetch(url, { method: "GET" });

      const nuevos = Array.isArray(data.items) ? data.items : [];

      // Si es reset, reemplaza; si no, acumula
      setUsuarios((prev) => (reset ? nuevos : [...prev, ...nuevos]));

      // Actualizar cursor
      setCursor(data.nextCursor || null);
    } catch (err) {
      console.error("cargarUsuarios", err);
      const msg = err.body?.message || err.message || "Error cargando usuarios";
      toast.error(msg);
      setError(msg);
    } finally {
      setLoadingUsuarios(false);
    }
  };

  useEffect(() => {
    if (session && puedeGestionar) {
      cargarSolicitudes();
      // opcional: no cargar usuarios hasta que se abra la pestaña
    }
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

  // Acciones sobre usuarios (cambiar rol / crear solicitud)
  const accionUsuario = async (emailTarget, accion) => {
    // accion: 'solicitar-creador' | 'cancelar-solicitud' | 'dar-admin' | 'quitar-admin' | 'revocar-creador'
    const esDestructivo = ["revocar-creador", "quitar-admin", "eliminar"];
    if (esDestructivo.includes(accion)) {
      if (!window.confirm(`¿Estás seguro de ejecutar: ${accion} a ${emailTarget}?`)) return;
    }

    try {
      await apiFetch(`${API_BASE}/accion_usuarios`, {
        method: "POST",
        body: JSON.stringify({ email: emailTarget, accion }),
      });
      toast.success("Acción aplicada");
      setCursor(null);
      cargarUsuarios(true);
      cargarSolicitudes();
    } catch (err) {
      const msg = err.body?.message || err.message || "Error en acción de usuario";
      toast.error(msg);
      setError(msg);
    }
  };
  
  // ---- Render ----
  if (loadingSession) return <div>Cargando sesión…</div>;
  if (!puedeGestionar) return <div>🚫 No autorizado</div>;

  // Derived state for filtered solicitudes
  const solicitudesFiltradas = solicitudes.filter((s) =>
    s.correo.toLowerCase().includes(filtroSolicitudes.toLowerCase())
  );

  // Add a mapping for estado labels
  const estadoLabel = {
    pendiente: "Pendiente",
    aprobado: "Aprobado",
    rechazado: "Rechazado",
    revocado: "Revocado",
  };

  const renderUserActions = (user, onAction) => {
    const actions = [];

    if (user.role === "Participante") {
      actions.push({ label: "Solicitar Creador", icon: "⬆️", action: "solicitar-creador", variant: "primary" });
      actions.push({ label: "Dar Admin", icon: "🛡️", action: "dar-admin", variant: "warning" });
    } else if (user.role === "Creador") {
      actions.push({ label: "Revocar Creador", icon: "🔽", action: "revocar-creador", variant: "danger" });
      actions.push({ label: "Dar Admin", icon: "🛡️", action: "dar-admin", variant: "warning" });
    } else if (user.role === "Administrador") {
      actions.push({ label: "Quitar Admin", icon: "❌", action: "quitar-admin", variant: "danger" });
    }

    return actions.map((btn) => (
      <button
        key={btn.action}
        className={`btn-${btn.variant}`}
        onClick={() => onAction(user.email, btn.action)}
        title={btn.label}
      >
        {btn.icon}
      </button>
    ));
  };

  return (
    <div className="pagina-admin">
      <h1>Panel de Administración</h1>
      <p>Bienvenido, {email}</p>

      <div className="admin-tabs">
        <button
          className={tab === "usuarios" ? "tab active" : "tab"}
          onClick={() => {
            setTab("usuarios");
            setCursor(null);
            cargarUsuarios(true);
          }}
        >
          Usuarios registrados
        </button>
        <button
          className={tab === "solicitudes" ? "tab active" : "tab"}
          onClick={() => setTab("solicitudes")}
        >
          Solicitudes de rol
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {tab === "usuarios" ? (
        <>
          <div className="filtros-usuarios">
            <input
              type="text"
              placeholder="Buscar por email ..."
              value={filtroUsuarios}
              onChange={(e) => setFiltroUsuarios(e.target.value)}
            />
          </div>

          {usuarios.length === 0 && !loadingUsuarios ? (
            renderEmptyState("No se encontraron usuarios con ese criterio.", () => setFiltroUsuarios("")) 
          ) : (
            <table className="tabla-solicitudes">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Rol</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => (
                  <tr key={u.id || u.email}>
                    <td>{u.email}</td>
                    <td>
                      <span className={`badge ${u.role.toLowerCase()}`}>{u.role}</span>
                    </td>
                    <td>{u.status}</td>
                    <td>
                      <div className="action-buttons-group">
                        {renderUserActions(u, accionUsuario)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      ) : (
        <>
          <div className="filtros-usuarios">
            <input
              type="text"
              placeholder="Buscar por correo..."
              value={filtroSolicitudes}
              onChange={(e) => setFiltroSolicitudes(e.target.value)}
            />
          </div>

          {solicitudesFiltradas.length === 0 ? (
            renderEmptyState("No se encontraron solicitudes con ese criterio.", () => setFiltroSolicitudes(""))
          ) : (
            <table className="tabla-solicitudes">
              <thead>
                <tr>
                  <th>Correo</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {solicitudesFiltradas.map((s) => (
                  <tr key={s.correo}>
                    <td>{s.correo}</td>
                    <td>
                      <span className={`badge ${s.estado.toLowerCase()}`}>{estadoLabel[s.estado] || s.estado}</span>
                    </td>
                    <td>
                      <button onClick={() => accionSolicitud(s.correo, "aprobar")}>✅</button>
                      <button onClick={() => accionSolicitud(s.correo, "rechazar")}>❌</button>
                      <button onClick={() => accionSolicitud(s.correo, "revocar")}>🔄</button>
                      <button onClick={() => accionSolicitud(s.correo, "eliminar")}>🗑️</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

    </div>
  );
}


