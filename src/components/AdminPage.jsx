// src/components/AdminPage.jsx
import React, { useEffect, useState } from "react"; // Eliminado useMemo
import { getSessionOrNull } from "../utils/session";
import "./AdminPage.css";
import { toast } from 'react-hot-toast';

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
  // Función auxiliar para obtener el string del token.
  // IMPORTANTE: Cambiamos la prioridad a idToken para satisfacer a API Gateway
  const getTokenFromSession = (sess) => {
    // 1. Intentamos sacar el ID TOKEN (Contiene email, grupos, identidad)
    let rawToken = sess?.tokens?.idToken;
    
    // Si no hay idToken, probamos con accessToken como fallback
    if (!rawToken) {
        rawToken = sess?.tokens?.accessToken;
    }

    if (!rawToken) return null;
    
    // Extracción de string compatible con todas las versiones de Amplify
    if (typeof rawToken === 'string') return rawToken;
    if (rawToken.jwtToken) return rawToken.jwtToken;
    if (typeof rawToken.toString === 'function') return rawToken.toString();
    
    return null;
  };

  // 1. Obtener sesión
  let session = await getSessionOrNull(false);
  let token = getTokenFromSession(session);

  // 2. Si no hay token, intentar refresh
  if (!token) {
    session = await getSessionOrNull(true);
    token = getTokenFromSession(session);
  }

  if (!token) {
    console.error("SESSION DEBUG:", session); // Para ver qué está fallando si ocurre
    throw new Error("No token available (Login required)");
  }

  const makeRequest = async (tokenToUse) => {
    const headers = {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
      Authorization: `Bearer ${tokenToUse}`,
    };
    return fetch(url, { ...opts, headers });
  };

  let res = await makeRequest(token);

  // 3. Manejo de expiración (401) -> Refresh y reintento
  if (res.status === 401) {
    console.warn("Token expirado o inválido (401). Intentando refresh...");
    session = await getSessionOrNull(true);
    token = getTokenFromSession(session);

    if (!token) throw new Error("Cannot refresh token");

    res = await makeRequest(token);
  }

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    let body;
    try { body = JSON.parse(txt); } catch { body = txt; }
    
    // Creamos un error más detallado
    const err = new Error(body?.message || `Error HTTP ${res.status}`);
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
    try {
      await apiFetch(`${API_BASE}/accion_usuarios`, {
        method: "POST",
        body: JSON.stringify({ email: emailTarget, accion }),
      });
      toast.success("Acción aplicada");
      // refrescar listas
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
          {/* Filtros usuarios */}
          <div className="filtros-usuarios">
            <input
              type="text"
              placeholder="Buscar por email exacto..."
              value={filtroUsuarios}
              onChange={(e) => {
                setFiltroUsuarios(e.target.value);
                if (e.target.value === "") setCursor(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  setCursor(null);
                  cargarUsuarios(true);
                }
              }}
            />
            <button onClick={() => {
              setCursor(null);
              cargarUsuarios(true);
            }} disabled={loadingUsuarios}>
              {loadingUsuarios ? "Buscando…" : "🔍 Buscar"}
            </button>
          </div>

          <table className="tabla-solicitudes" style={{ marginTop: 20 }}>
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
                  <td>{u.role}</td>
                  <td>{u.status}</td>
                  <td>
                    {/* BOTONES RESTAURADOS (Usando u.role y u.email) */}
                    {u.role === "Participante" && (
                      <>
                        <button onClick={() => accionUsuario(u.email, "solicitar-creador")}>
                          Solicitar Creador
                        </button>
                        <button onClick={() => accionUsuario(u.email, "dar-admin")} style={{ marginLeft: 8 }}>
                          Dar admin
                        </button>
                      </>
                    )}

                    {u.role === "Creador" && (
                      <>
                        <button onClick={() => accionUsuario(u.email, "revocar-creador")}>
                          Revocar creador
                        </button>
                        <button onClick={() => accionUsuario(u.email, "dar-admin")} style={{ marginLeft: 8 }}>
                          Dar admin
                        </button>
                      </>
                    )}

                    {u.role === "Administrador" && (
                      <button onClick={() => accionUsuario(u.email, "quitar-admin")}>
                        Quitar admin
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {cursor && (
            <div style={{ textAlign: "center", marginTop: 20 }}>
              <button
                disabled={loadingUsuarios}
                onClick={() => cargarUsuarios(false)}
              >
                {loadingUsuarios ? "Cargando..." : "⬇ Cargar más"}
              </button>
            </div>
          )}
        </>
      ) : (
        <>
          {/* pestaña Solicitudes (tu lógica actual, apenas ajustada) */}
          <button onClick={cargarSolicitudes} disabled={loading}>
            {loading ? "Actualizando…" : "↻ Actualizar"}
          </button>

          <table className="tabla-solicitudes" style={{ marginTop: 20 }}>
            <thead>
              <tr>
                <th>Correo</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {solicitudes.map((s) => (
                <tr key={s.correo}>
                  <td>{s.correo}</td>
                  <td>{s.estado}</td>
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
                    <button
                      onClick={() => accionSolicitud(s.correo, "revocar")}
                      style={{ marginLeft: 8 }}
                    >
                      Revocar
                    </button>
                    <button
                      onClick={() => accionSolicitud(s.correo, "eliminar")}
                      style={{ marginLeft: 8 }}
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

    </div>
  );
}


