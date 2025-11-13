// src/components/AdminPage.jsx
import React, { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import './AdminPage.css';

const ADMIN_EMAIL = 'anette.flores@netec.com.mx';
const API_BASE = 'https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2';

function AdminPage() {
  const { pathname } = useLocation();
  if (!pathname.startsWith('/admin')) return null;

  const [solicitudes, setSolicitudes] = useState([]);
  const [email, setEmail] = useState('');
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState('');

  const [filtroTexto, setFiltroTexto] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('all');
  const [vistaRol, setVistaRol] = useState(
    () => localStorage.getItem('ui_role_preview') || 'Administrador'
  );

  const token = localStorage.getItem('id_token');

  // Header Auth
  const authHeader = useMemo(() => {
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }, [token]);

  // Extraer email del token
  useEffect(() => {
    if (!token) return;
    try {
      const payload = JSON.parse(
        atob((token.split('.')[1] || '').replace(/-/g, '+').replace(/_/g, '/'))
      );
      setEmail(payload?.email || '');
    } catch (e) {
      console.error('Error al decodificar token', e);
    }
  }, [token]);

  const cargarSolicitudes = async () => {
    setCargando(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/obtener-solicitudes-rol`, {
        method: 'GET',
        headers: { ...authHeader },
      });
      if (!res.ok) throw new Error(`Error HTTP ${res.status}`);
      const data = await res.json().catch(() => ({}));
      setSolicitudes(Array.isArray(data?.solicitudes) ? data.solicitudes : []);
    } catch (e) {
      console.error(e);
      setError('No se pudieron cargar las solicitudes.');
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    if (token) cargarSolicitudes();
  }, [token]);

  const puedeGestionar = email.toLowerCase() === ADMIN_EMAIL;

  const pokeClientsToRefresh = () => {
    try {
      localStorage.setItem('force_attr_refresh', '1');
    } catch {}
  };

  const accionSolicitud = async (correo, accion) => {
    setEnviando(correo);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/aprobar-rol`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
        body: JSON.stringify({ correo, accion }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || 'Error en la acción');

      pokeClientsToRefresh();

      setSolicitudes((prev) =>
        prev.map((s) =>
          s.correo === correo
            ? { ...s, estado: accion === 'aprobar' ? 'aprobado' : 'rechazado' }
            : s
        )
      );
      alert(`✅ Acción ${accion} aplicada para ${correo}.`);
    } catch (e) {
      console.error(e);
      setError(`No se pudo ${accion} la solicitud.`);
    } finally {
      setEnviando('');
    }
  };

  const eliminarSolicitud = async (correo) => {
    setEnviando(correo);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/eliminar-solicitud`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
        body: JSON.stringify({ correo }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || 'Error al eliminar');

      pokeClientsToRefresh();

      setSolicitudes((prev) => prev.filter((s) => s.correo !== correo));
      alert(`🗑️ Solicitud de ${correo} eliminada.`);
    } catch (e) {
      console.error(e);
      setError('No se pudo eliminar la solicitud.');
    } finally {
      setEnviando('');
    }
  };

  // Filtros
  const solicitudesFiltradas = useMemo(() => {
    const txt = filtroTexto.trim().toLowerCase();
    return solicitudes.filter((s) => {
      const estado = (s.estado || 'pendiente').toLowerCase();
      const correo = (s.correo || '').toLowerCase();
      const pasaTexto = !txt || correo.includes(txt);
      const pasaEstado = filtroEstado === 'all' || estado === filtroEstado;
      return pasaTexto && pasaEstado;
    });
  }, [solicitudes, filtroTexto, filtroEstado]);

  useEffect(() => {
    localStorage.setItem('ui_role_preview', vistaRol);
  }, [vistaRol]);

  return (
    <div className="pagina-admin">
      <h1>Panel de Administración</h1>
      <p>Desde aquí puedes revisar solicitudes para otorgar el rol "creador" y habilitar el botón para usuarios externos.</p>

      {!puedeGestionar && (
        <p className="solo-autorizado">
          🚫 Solo la administradora autorizada puede aprobar/rechazar/revocar/eliminar.
        </p>
      )}

      {/* Filtros */}
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
          {cargando ? 'Actualizando…' : '↻ Actualizar'}
        </button>
      </div>

      {/* Vista de rol */}
      <div className="rol-preview">
        <label>Tu rol activo:&nbsp;</label>
        <select
          className="select-rol"
          value={vistaRol}
          onChange={(e) => setVistaRol(e.target.value)}
        >
          <option>Administrador</option>
          <option>Creador</option>
          <option>Participante</option>
        </select>
        <span className="hint">(tras cambiar, vuelve a iniciar sesión)</span>
      </div>

      {cargando ? (
        <div className="spinner">Cargando solicitudes…</div>
      ) : error ? (
        <div className="error-box">{error}</div>
      ) : solicitudesFiltradas.length === 0 ? (
        <p>No hay solicitudes.</p>
      ) : (
        <div className="tabla-solicitudes">
          <table>
            <thead>
              <tr>
                <th>Correo</th>
                <th>Estado</th>
                <th>Botón Visible</th> {/* ⭐ NUEVO */}
                {puedeGestionar && <th>Acciones</th>}
              </tr>
            </thead>
            <tbody>
              {solicitudesFiltradas.map((s) => {
                const estado = (s.estado || 'pendiente').toLowerCase();
                const correo = s.correo;
                const protegido = correo === ADMIN_EMAIL;

                return (
                  <tr key={correo}>
                    <td>{correo}</td>

                    <td>
                      <span className={`badge-estado ${estado}`}>
                        {estado.replace(/^./, (c) => c.toUpperCase())}
                      </span>
                    </td>

                    {/* ⭐ NUEVO SWITCH */}
                    <td>
                      {protegido ? (
                        <span>🔒</span>
                      ) : (
                        <label className="switch">
                          <input
                            type="checkbox"
                            checked={s.boton_habilitado === true}
                            onChange={async () => {
                              try {
                                await fetch(`${API_BASE}/boton`, {
                                  method: "POST",
                                  headers: {
                                    "Content-Type": "application/json",
                                    ...authHeader,
                                  },
                                  body: JSON.stringify({
                                    correo,
                                    boton_habilitado: !(s.boton_habilitado === true)
                                  }),
                                });

                                setSolicitudes(prev =>
                                  prev.map(x =>
                                    x.correo === correo
                                      ? { ...x, boton_habilitado: !(s.boton_habilitado === true) }
                                      : x
                                  )
                                );
                              } catch (e) {
                                alert("No se pudo actualizar la visibilidad del botón.");
                              }
                            }}
                          />
                          <span className="slider round"></span>
                        </label>
                      )}
                    </td>

                    {puedeGestionar && (
                      <td className="col-acciones">
                        {protegido ? (
                          <span className="chip-protegido">🔒 Protegido</span>
                        ) : (
                          <>
                            <button
                              className="btn-aprobar"
                              onClick={() => accionSolicitud(correo, 'aprobar')}
                              disabled={enviando === correo}
                            >
                              {enviando === correo ? 'Aplicando…' : '✅ Aprobar'}
                            </button>
                            <button
                              className="btn-rechazar"
                              onClick={() => accionSolicitud(correo, 'rechazar')}
                              disabled={enviando === correo}
                            >
                              {enviando === correo ? 'Aplicando…' : '❌ Rechazar'}
                            </button>
                            <button
                              className="btn-rechazar"
                              onClick={() => accionSolicitud(correo, 'revocar')}
                              disabled={enviando === correo}
                              style={{ marginLeft: 8 }}
                            >
                              {enviando === correo ? 'Aplicando…' : '🗑️ Revocar'}
                            </button>
                            <button
                              className="btn-rechazar"
                              onClick={() => eliminarSolicitud(correo)}
                              disabled={enviando === correo}
                              style={{ marginLeft: 8 }}
                            >
                              {enviando === correo ? 'Eliminando…' : '🗑️ Eliminar'}
                            </button>
                          </>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default AdminPage;


