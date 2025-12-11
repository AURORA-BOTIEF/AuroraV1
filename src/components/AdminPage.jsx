// src/components/AdminPage.jsx
import React, { useEffect, useState, useMemo } from "react";
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

// Wrapper de fetch con token actualizado
// Wrapper de fetch con token estricto (solo access_token)
async function apiFetch(url, opts = {}) {
  // 1. Obtener sesión inicial
  let session = await getSessionOrNull(false);
  let token = session?.tokens?.accessToken?.jwtToken;

  // 2. Si falta token, intentar refresh inmediato
  if (!token) {
    session = await getSessionOrNull(true);
    token = session?.tokens?.accessToken?.jwtToken;
  }

  if (!token) {
    throw new Error("No access token available");
  }

  // DEFINICIÓN: Pasamos 'tokenToUse' explícitamente para evitar confusión de scope
  const makeRequest = async (tokenToUse) => {
    const headers = {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
      Authorization: `Bearer ${tokenToUse}`,
    };
    return fetch(url, { ...opts, headers });
  };

  // 3. Primer intento
  let res = await makeRequest(token);

  // 4. Si expira (401), refrescar y reintentar
  if (res.status === 401) {
    session = await getSessionOrNull(true);
    token = session?.tokens?.accessToken?.jwtToken;

    if (!token) {
      throw new Error("Cannot refresh access token");
    }

    // Reintento con el NUEVO token explícito
    res = await makeRequest(token);
  }

  // 5. Manejo de respuesta
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

  // pestaña activa: 'usuarios' | 'solicitudes'
  const [tab, setTab] = useState("solicitudes");

  // listado de usuarios (filtrados por backend)
  const [usuarios, setUsuarios] = useState([]);
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
  const cargarUsuarios = async () => {
    if (!puedeGestionar) return;
    setLoadingUsuarios(true);
    setError("");

    try {
      const qs = filtroUsuarios ? `?filtro=${encodeURIComponent(filtroUsuarios)}` : "";
      const data = await apiFetch(`${API_BASE}/usuarios${qs}`, { method: "GET" });

      // se espera un array de objetos: { correo, rol, tieneSolicitudCreador, dominio }
      setUsuarios(Array.isArray(data?.usuarios) ? data.usuarios : []);
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
  const accionUsuario = async (correo, accion) => {
    // accion: 'solicitar-creador' | 'cancelar-solicitud' | 'dar-admin' | 'quitar-admin' | 'revocar-creador'
    try {
      await apiFetch(`${API_BASE}/usuarios/accion`, {
        method: "POST",
        body: JSON.stringify({ correo, accion }),
      });
      toast.success("Acción aplicada");
      // refrescar listas
      cargarUsuarios();
      cargarSolicitudes();
    } catch (err) {
      const msg = err.body?.message || err.message || "Error en acción de usuario";
      toast.error(msg);
      setError(msg);
    }
  };

  const usuariosFiltrados = useMemo(() => {
    const txt = filtroUsuarios.toLowerCase().trim();
    if (!txt) return usuarios;
    return usuarios.filter((u) =>
      (u.correo || "").toLowerCase().includes(txt) ||
      (u.dominio || "").toLowerCase().includes(txt)
    );
  }, [usuarios, filtroUsuarios]);

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
            cargarUsuarios();
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
              placeholder="Buscar por correo o dominio…"
              value={filtroUsuarios}
              onChange={(e) => setFiltroUsuarios(e.target.value)}
            />
            <button onClick={cargarUsuarios} disabled={loadingUsuarios}>
              {loadingUsuarios ? "Buscando…" : "🔍 Buscar"}
            </button>
          </div>

          <table className="tabla-solicitudes" style={{ marginTop: 20 }}>
            <thead>
              <tr>
                <th>Correo</th>
                <th>Rol</th>
                <th>Solicitud creador</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuariosFiltrados.map((u) => (
                <tr key={u.correo}>
                  <td>{u.correo}</td>
                  <td>{u.rol}</td>
                  <td>{u.tieneSolicitudCreador ? "Sí" : "No"}</td>
                  <td>
                    {/* Aquí decides qué botones mostrar según rol */}
                    {u.rol === "Participante" && (
                      <>
                        {!u.tieneSolicitudCreador && (
                          <button onClick={() => accionUsuario(u.correo, "solicitar-creador")}>
                            Solicitar rol creador
                          </button>
                        )}
                        <button onClick={() => accionUsuario(u.correo, "dar-admin")} style={{ marginLeft: 8 }}>
                          Dar admin
                        </button>
                      </>
                    )}

                    {u.rol === "Creador" && (
                      <>
                        <button onClick={() => accionUsuario(u.correo, "revocar-creador")}>
                          Revocar creador
                        </button>
                        <button onClick={() => accionUsuario(u.correo, "dar-admin")} style={{ marginLeft: 8 }}>
                          Dar admin
                        </button>
                      </>
                    )}

                    {u.rol === "Administrador" && (
                      <button onClick={() => accionUsuario(u.correo, "quitar-admin")}>
                        Quitar admin
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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


