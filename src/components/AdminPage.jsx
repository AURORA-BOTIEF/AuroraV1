// src/components/AdminPage.jsx
import React, { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import './AdminPage.css';

const ADMIN_EMAIL = 'anette.flores@netec.com.mx';
const API_BASE = 'https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2';

function AdminPage() {
  const { pathname } = useLocation();
  if (!pathname.startsWith('/admin')) return null;

  const [activeTab, setActiveTab] = useState('solicitudes'); // solicitudes | externos

  const [solicitudes, setSolicitudes] = useState([]);
  const [externos, setExternos] = useState([]);

  const [email, setEmail] = useState('');
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState('');

  const [nuevoExterno, setNuevoExterno] = useState('');

  const [filtroTexto, setFiltroTexto] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('all');
  const [vistaRol, setVistaRol] = useState(
    () => localStorage.getItem('ui_role_preview') || 'Administrador'
  );

  const token = localStorage.getItem('id_token');

  // Auth header
  const authHeader = useMemo(() => {
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }, [token]);

  // Extraer email del token
  useEffect(() => {
    if (!token) return;
    try {
      const payload = JSON.parse(atob((token.split('.')[1] || '').replace(/-/g, "+").replace(/_/g, "/")));
      setEmail(payload?.email || '');
    } catch (err) {}
  }, [token]);

  const puedeGestionar = email.toLowerCase() === ADMIN_EMAIL;

  // Cargar solicitudes de rol
  const cargarSolicitudes = async () => {
    try {
      setCargando(true);
      const res = await fetch(`${API_BASE}/obtener-solicitudes-rol`, { headers: authHeader });
      const data = await res.json();
      const lista = Array.isArray(data?.solicitudes) ? data.solicitudes : [];

      // Filtrar externos por estado === 'externo'
      const externosFiltrados = lista.filter(s => s.estado === 'externo');

      setSolicitudes(lista.filter(s => s.estado !== 'externo'));
      setExternos(externosFiltrados);

    } catch (err) {
      console.error(err);
      setError('No se pudieron cargar los datos.');
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    if (token) cargarSolicitudes();
  }, [token]);

  const pokeClientsToRefresh = () => {
    try {
      localStorage.setItem('force_attr_refresh', '1');
    } catch {}
  };

  // Acciones del panel de solicitudes existentes
  const accionSolicitud = async (correo, accion) => {
    try {
      setEnviando(correo);
      const res = await fetch(`${API_BASE}/aprobar-rol`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ correo, accion }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || 'Error en la acción');

      pokeClientsToRefresh();

      // Actualizar localmente
      setSolicitudes(prev =>
        prev.map(s =>
          s.correo === correo
            ? { ...s, estado: accion === "aprobar" ? "aprobado" : "rechazado" }
            : s
        )
      );

      alert(`Acción ${accion} aplicada para ${correo}`);
    } catch (err) {
      console.error(err);
      setError(`No se pudo ${accion} la solicitud.`);
    } finally {
      setEnviando('');
    }
  };

  const eliminarSolicitud = async (correo) => {
    try {
      setEnviando(correo);
      const res = await fetch(`${API_BASE}/eliminar-solicitud`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ correo }),
      });
      if (!res.ok) throw new Error();

      pokeClientsToRefresh();

      setSolicitudes(prev => prev.filter(s => s.correo !== correo));
      alert(`Solicitud de ${correo} eliminada.`);
    } catch {
      setError("No se pudo eliminar la solicitud.");
    } finally {
      setEnviando('');
    }
  };

  // ============
  // USUARIOS EXTERNOS
  // ============

  const agregarExterno = async () => {
    if (!nuevoExterno) return alert("Ingresa un correo.");

    try {
      setEnviando(nuevoExterno);
      const res = await fetch(`${API_BASE}/estado-boton`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({
          correo: nuevoExterno.toLowerCase(),
          accion: "crear" // nuestra Lambda lo interpretará
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Error al crear usuario externo");

      setNuevoExterno("");
      cargarSolicitudes();
      alert("Usuario externo agregado.");

    } catch (e) {
      alert("Error creando usuario externo.");
    } finally {
      setEnviando('');
    }
  };

  const toggleBotonExterno = async (correo, valor) => {
    try {
      setEnviando(correo);
      const res = await fetch(`${API_BASE}/estado-boton`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({
          correo,
          boton_habilitado: valor,
          accion: "actualizar"
        })
      });

      if (!res.ok) throw new Error();

      setExternos(prev =>
        prev.map(ex => ex.correo === correo ? { ...ex, boton_habilitado: valor } : ex)
      );

    } catch {
      alert("Error actualizando usuario externo.");
    } finally {
      setEnviando('');
    }
  };

  const eliminarExterno = async (correo) => {
    try {
      setEnviando(correo);
      const res = await fetch(`${API_BASE}/estado-boton`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({
          correo,
          accion: "eliminar"
        })
      });

      if (!res.ok) throw new Error();

      setExternos(prev => prev.filter(ex => ex.correo !== correo));
      alert("Usuario externo eliminado.");

    } catch {
      alert("Error eliminando usuario externo.");
    } finally {
      setEnviando('');
    }
  };

  // Filtrado solicitudes
  const solicitudesFiltradas = solicitudes.filter(s => {
    const txt = filtroTexto.trim().toLowerCase();
    const correo = s.correo.toLowerCase();
    const estado = s.estado.toLowerCase();
    return (!txt || correo.includes(txt)) &&
      (filtroEstado === 'all' || estado === filtroEstado);
  });

  return (
    <div className="pagina-admin">
      <h1>Panel de Administración</h1>

      {/* Tabs */}
      <div className="admin-tabs">
        <button
          className={activeTab === 'solicitudes' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('solicitudes')}
        >
          Solicitudes de Rol
        </button>

        <button
          className={activeTab === 'externos' ? 'tab active' : 'tab'}
          onClick={() => setActiveTab('externos')}
        >
          Usuarios Externos
        </button>
      </div>

      {/* ===================== */}
      {/* TAB 1 - SOLICITUDES */}
      {/* ===================== */}

      {activeTab === 'solicitudes' && (
        <>
          {!puedeGestionar && (
            <p className="solo-autorizado">
              🚫 Solo la administradora autorizada puede aprobar / rechazar / revocar / eliminar.
            </p>
          )}

          <div className="filtros">
            <input
              type="text"
              className="buscar-correo"
              placeholder="Buscar por correo…"
              value={filtroTexto}
              onChange={(e) => setFiltroTexto(e.target.value)}
            />

            <select
              className="select-estado"
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value)}
            >
              <option value="all">Todos los estados</option>
              <option value="pendiente">Pendiente</option>
              <option value="aprobado">Aprobado</option>
              <option value="rechazado">Rechazado</option>
            </select>

            <button className="btn-recargar" onClick={cargarSolicitudes} disabled={cargando}>
              {cargando ? "Actualizando…" : "↻ Actualizar"}
            </button>
          </div>

          <div className="tabla-solicitudes">
            <table>
              <thead>
                <tr>
                  <th>Correo</th>
                  <th>Estado</th>
                  {puedeGestionar && <th>Acciones</th>}
                </tr>
              </thead>
              <tbody>
                {solicitudesFiltradas.map((s) => (
                  <tr key={s.correo}>
                    <td>{s.correo}</td>
                    <td>
                      <span className={`badge-estado ${s.estado}`}>
                        {s.estado.charAt(0).toUpperCase() + s.estado.slice(1)}
                      </span>
                    </td>

                    {puedeGestionar && (
                      <td className="col-acciones">
                        <button
                          className="btn-aprobar"
                          disabled={enviando === s.correo}
                          onClick={() => accionSolicitud(s.correo, 'aprobar')}
                        >
                          {enviando === s.correo ? "…" : "Aprobar"}
                        </button>

                        <button
                          className="btn-rechazar"
                          disabled={enviando === s.correo}
                          onClick={() => accionSolicitud(s.correo, 'rechazar')}
                        >
                          Rechazar
                        </button>

                        <button
                          className="btn-rechazar"
                          disabled={enviando === s.correo}
                          onClick={() => accionSolicitud(s.correo, 'revocar')}
                        >
                          Revocar
                        </button>

                        <button
                          className="btn-rechazar"
                          disabled={enviando === s.correo}
                          onClick={() => eliminarSolicitud(s.correo)}
                        >
                          Eliminar
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ===================== */}
      {/* TAB 2 - EXTERNOS */}
      {/* ===================== */}

      {activeTab === 'externos' && (
        <div className="externos">
          <h2>Usuarios Externos</h2>

          <div className="externo-add">
            <input
              type="email"
              placeholder="Correo externo"
              value={nuevoExterno}
              onChange={(e) => setNuevoExterno(e.target.value)}
            />
            <button onClick={agregarExterno} disabled={!puedeGestionar || enviando === nuevoExterno}>
              Agregar
            </button>
          </div>

          <table className="tabla-externos">
            <thead>
              <tr>
                <th>Correo</th>
                <th>Mostrar botón</th>
                <th>Acciones</th>
              </tr>
            </thead>

            <tbody>
              {externos.map(ex => (
                <tr key={ex.correo}>
                  <td>{ex.correo}</td>

                  <td>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={!!ex.boton_habilitado}
                        disabled={enviando === ex.correo}
                        onChange={(e) => toggleBotonExterno(ex.correo, e.target.checked)}
                      />
                      <span className="slider round"></span>
                    </label>
                  </td>

                  <td>
                    <button
                      className="btn-rechazar"
                      disabled={enviando === ex.correo}
                      onClick={() => eliminarExterno(ex.correo)}
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>

          </table>
        </div>
      )}
    </div>
  );
}

export default AdminPage;


