// src/components/AdminPage.jsx
import React, { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import './AdminPage.css';

// ==========================
//  API BASE 100% A PRUEBA DE FALLOS
// ==========================
const API_BASE = 
  'https://' +
  'h6ysn7u0tl' +          // ID
  '.execute-api' +        // Región fija
  '.us-east-1' +
  '.amazonaws' +
  '.com' +
  '/dev2';                // Stage

// ==========================
const ADMIN_EMAIL = 'anette.flores@netec.com.mx';

function AdminPage() {
  const { pathname } = useLocation();
  if (!pathname.startsWith('/admin')) return null;

  // ====== ESTADO GENERAL ======
  const [email, setEmail] = useState('');
  const token = localStorage.getItem('id_token');

  const authHeader = useMemo(() => {
    if (!token) return {};
    return { Authorization: token };   // <---- SIN BEARER
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

  const puedeGestionar = email.toLowerCase() === ADMIN_EMAIL;

  // ====== TABS ======
  const [vista, setVista] = useState('solicitudes');

  // ====== SOLICITUDES DE ROL ======
  const [solicitudes, setSolicitudes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState('');

  const [filtroTexto, setFiltroTexto] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('all');
  const [vistaRol, setVistaRol] = useState(
    () => localStorage.getItem('ui_role_preview') || 'Administrador'
  );

  const cargarSolicitudes = async () => {
    setCargando(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/obtener-solicitudes-rol`, {
        method: 'GET',
        headers: { ...authHeader }
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

  const pokeClientsToRefresh = () => {
    try { localStorage.setItem('force_attr_refresh', '1'); } catch {}
  };

  const accionSolicitud = async (correo, accion) => {
    setEnviando(correo);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/aprobar-rol`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader
        },
        body: JSON.stringify({ correo, accion })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || 'Error en la acción');

      pokeClientsToRefresh();

      setSolicitudes(prev =>
        prev.map(s =>
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
          ...authHeader
        },
        body: JSON.stringify({ correo })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || 'Error al eliminar');

      pokeClientsToRefresh();

      setSolicitudes(prev => prev.filter(s => s.correo !== correo));

      alert(`🗑️ Solicitud de ${correo} eliminada.`);

    } catch (e) {
      console.error(e);
      setError('No se pudo eliminar la solicitud.');
    } finally {
      setEnviando('');
    }
  };

  const solicitudesFiltradas = solicitudes.filter(s => {
    const txt = filtroTexto.trim().toLowerCase();
    const estado = (s.estado || 'pendiente').toLowerCase();
    const correo = (s.correo || '').toLowerCase();

    const pasaTexto = !txt || correo.includes(txt);
    const pasaEstado = filtroEstado === 'all' || estado === filtroEstado;

    return pasaTexto && pasaEstado;
  });

  useEffect(() => {
    localStorage.setItem('ui_role_preview', vistaRol);
  }, [vistaRol]);

  // ====== USUARIOS EXTERNOS ======
  const [usuariosExternos, setUsuariosExternos] = useState([]);
  const [cargandoExternos, setCargandoExternos] = useState(false);
  const [errorExternos, setErrorExternos] = useState('');
  const [enviandoExterno, setEnviandoExterno] = useState('');
  const [filtroTextoExt, setFiltroTextoExt] = useState('');
  const [externosCargados, setExternosCargados] = useState(false);

  const cargarExternos = async () => {
    setCargandoExternos(true);
    setErrorExternos('');
    try {
      const res = await fetch(`${API_BASE}/usuarios-externos`, {
        method: 'GET',
        headers: { ...authHeader }
      });

      const data = await res.json().catch(() => ({}));
      setUsuariosExternos(Array.isArray(data?.externos) ? data.externos : []);
      setExternosCargados(true);

    } catch (e) {
      console.error(e);
      setErrorExternos('No se pudieron cargar los usuarios externos.');
    } finally {
      setCargandoExternos(false);
    }
  };

  const actualizarHabilitado = async (correo, habilitado) => {
    if (!puedeGestionar) return;

    setEnviandoExterno(correo);
    setErrorExternos('');

    try {
      const res = await fetch(`${API_BASE}/actualizar-externo`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader
        },
        body: JSON.stringify({ correo, habilitado })
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.error || 'No se pudo actualizar');

      setUsuariosExternos(prev =>
        prev.map(u =>
          u.email === correo ? { ...u, habilitado } : u
        )
      );

    } catch (e) {
      console.error(e);
      setErrorExternos('Error al actualizar el estado del usuario externo.');
    } finally {
      setEnviandoExterno('');
    }
  };

  const usuariosExternosFiltrados = usuariosExternos.filter(u =>
    (u.email || '').toLowerCase().includes(filtroTextoExt.toLowerCase())
  );

  // ====== RENDER ======
  return (
    <div className="pagina-admin">
      <h1>Panel de Administración</h1>
      <p>Desde aquí puedes revisar solicitudes para otorgar el rol "creador".</p>

      {!puedeGestionar && (
        <p className="solo-autorizado">
          🚫 Solo la administradora autorizada puede aprobar/rechazar/revocar/eliminar.
        </p>
      )}

      {/* TABS */}
      <div className="tabs-admin">
        <button
          className={vista === 'solicitudes' ? 'active' : ''}
          onClick={() => setVista('solicitudes')}
        >
          Solicitudes de Rol
        </button>

        <button
          className={vista === 'externos' ? 'active' : ''}
          onClick={() => {
            setVista('externos');
            if (!externosCargados) cargarExternos();
          }}
        >
          Usuarios Externos
        </button>
      </div>

      {/* ================= VISTA SOLICITUDES ================ */}
      {vista === 'solicitudes' && (
        <>
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

            <button
              className="btn-recargar"
              onClick={cargarSolicitudes}
              disabled={cargando}
            >
              {cargando ? 'Actualizando…' : '↻ Actualizar'}
            </button>
          </div>

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
                            {estado.charAt(0).toUpperCase() + estado.slice(1)}
                          </span>
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
        </>
      )}

      {/* ================= VISTA USUARIOS EXTERNOS ================ */}
      {vista === 'externos' && (
        <div className="vista-externos">
          <p>
            Aquí puedes ver los usuarios cuyo correo NO pertenece a dominios Netec y
            habilitar o deshabilitar que vean el botón "Solicitar rol de Creador".
          </p>

          <div className="filtros">
            <input
              type="text"
              className="buscar-correo"
              placeholder="Buscar externo por correo…"
              value={filtroTextoExt}
              onChange={(e) => setFiltroTextoExt(e.target.value)}
            />

            <button
              className="btn-recargar"
              onClick={cargarExternos}
              disabled={cargandoExternos}
            >
              {cargandoExternos ? 'Cargando…' : '↻ Actualizar'}
            </button>
          </div>

          {cargandoExternos ? (
            <div className="spinner">Cargando usuarios externos…</div>
          ) : errorExternos ? (
            <div className="error-box">{errorExternos}</div>
          ) : usuariosExternosFiltrados.length === 0 ? (
            <p>No hay usuarios externos registrados.</p>
          ) : (
            <div className="tabla-solicitudes tabla-externos">
              <table>
                <thead>
                  <tr>
                    <th>Correo</th>
                    <th>Dominio</th>
                    <th>Rol actual</th>
                    <th>Botón Solicitar Rol</th>
                    {puedeGestionar && <th>Acciones</th>}
                  </tr>
                </thead>

                <tbody>
                  {usuariosExternosFiltrados.map((u) => {
                    const correo = u.email;
                    const habilitado = !!u.habilitado;

                    return (
                      <tr key={correo}>
                        <td>{correo}</td>
                        <td>{u.dominio || correo.split('@')[1] || '-'}</td>
                        <td>{u.rol || 'participant'}</td>
                        <td>
                          <span className={`badge-habilitado ${habilitado ? 'on' : 'off'}`}>
                            {habilitado ? 'Habilitado' : 'Deshabilitado'}
                          </span>
                        </td>

                        {puedeGestionar && (
                          <td className="col-acciones">
                            <button
                              className="btn-aprobar"
                              onClick={() => actualizarHabilitado(correo, true)}
                              disabled={enviandoExterno === correo || habilitado}
                            >
                              {enviandoExterno === correo ? 'Aplicando…' : '✅ Habilitar'}
                            </button>

                            <button
                              className="btn-rechazar"
                              onClick={() => actualizarHabilitado(correo, false)}
                              disabled={enviandoExterno === correo || !habilitado}
                              style={{ marginLeft: 8 }}
                            >
                              {enviandoExterno === correo ? 'Aplicando…' : '🚫 Deshabilitar'}
                            </button>
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
      )}
    </div>
  );
}

export default AdminPage;




