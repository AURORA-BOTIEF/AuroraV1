// src/components/Sidebar.jsx
import { Link } from 'react-router-dom';
import './Sidebar.css';
import defaultFoto from '../assets/default.jpg';
import { useEffect, useMemo, useState } from 'react';
import { getCurrentUser, fetchAuthSession } from 'aws-amplify/auth';
import AvatarPicker from './AvatarPicker';

const API_BASE = 'https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2';

const DOMINIOS_PERMITIDOS = new Set([
  'netec.com', 'netec.com.mx', 'netec.com.co',
  'netec.com.pe', 'netec.com.cl', 'netec.com.es', 'netec.com.pr'
]);

export default function Sidebar({ email = '', nombre, grupo = '' }) {

  const [avatar, setAvatar] = useState(null);
  const [colapsado, setColapsado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [estado, setEstado] = useState('');
  const [error, setError] = useState('');
  const [pickerAbierto, setPickerAbierto] = useState(false);
  const [authHeader, setAuthHeader] = useState({});
  const [tokenLoaded, setTokenLoaded] = useState(false);
  const [botonHabilitado, setBotonHabilitado] = useState(false);

  useEffect(() => {
    let cancelled = false;
    try {
      const prev = localStorage.getItem(`app_avatar_url:${(email || 'anon')}`);
      if (prev && !cancelled) setAvatar(prev);
    } catch { }
    return () => { cancelled = true; };
  }, [email]);

  async function getAuthHeaders() {
    const session = await fetchAuthSession();
    const idToken = session.tokens?.idToken?.toString();
    if (!idToken) return {};

    return {
      raw: { Authorization: idToken },
      bearer: { Authorization: `Bearer ${idToken}` }
    };
  }

  useEffect(() => {

    let cancelled = false;

    fetchAuthSession()
      .then(session => {
        const idToken = session.tokens?.idToken;

        if (idToken && !cancelled) {
          setAuthHeader({ Authorization: `Bearer ${idToken.toString()}` });
        }

        if (!cancelled) setTokenLoaded(true);
      })
      .catch(() => {
        if (!cancelled) {
          setAuthHeader({});
          setTokenLoaded(true);
        }
      });

    return () => { cancelled = true; };

  }, []);

  useEffect(() => {

    let cancelled = false;

    async function pintarFoto() {

      try {
        await getCurrentUser();
        const session = await fetchAuthSession();
        const pic = session.tokens?.idToken?.payload?.picture || '';

        if (/^https?:\/\//i.test(pic)) {
          if (!cancelled) setAvatar(pic);
          return;
        }

      } catch { }

      try {

        const { raw, bearer } = await getAuthHeaders();

        let r = await fetch(`${API_BASE}/perfil`, { headers: raw });

        if (!r.ok) {
          r = await fetch(`${API_BASE}/perfil`, { headers: bearer });
        }

        if (!r.ok) return;

        const d = await r.json().catch(() => ({}));

        if (!cancelled && d?.photoUrl) {
          setAvatar(d.photoUrl);
        }

      } catch { }

    }

    pintarFoto();

    const onUpd = (e) => {
      const url = e.detail?.photoUrl;
      if (url !== undefined) setAvatar(url || null);
    };

    window.addEventListener('profilePhotoUpdated', onUpd);

    return () => {
      cancelled = true;
      window.removeEventListener('profilePhotoUpdated', onUpd);
    };

  }, []);

  const dominio = useMemo(() => (email.split('@')[1] || '').toLowerCase(), [email]);
  const esNetec = DOMINIOS_PERMITIDOS.has(dominio);

  useEffect(() => {

    if (!API_BASE || !email || !esNetec || !tokenLoaded) return;

    const fetchEstado = async () => {

      setError('');

      try {

        const r = await fetch(`${API_BASE}/obtener-solicitudes-rol`, { headers: authHeader });

        if (!r.ok) return;

        const data = await r.json().catch(() => ({}));

        const lista = Array.isArray(data?.solicitudes) ? data.solicitudes : [];

        const it = lista.find(s => (s.correo || '').toLowerCase() === email.toLowerCase());

        const e = (it?.estado || '').toLowerCase();

        if (e === 'aprobado' || e === 'pendiente' || e === 'rechazado') {
          setEstado(e);
        } else {
          setEstado('');
        }

      } catch (e) {
        console.log('No se pudo obtener estado', e);
      }

    };

    fetchEstado();

  }, [email, esNetec, authHeader, tokenLoaded]);

  useEffect(() => {

    if (!email || esNetec === true || !tokenLoaded) return;

    const cargarEstado = async () => {

      try {

        const r = await fetch(`${API_BASE}/boton?correo=${email}`, {
          headers: authHeader
        });

        const j = await r.json().catch(() => ({}));

        setBotonHabilitado(j.boton_habilitado === true);

      } catch {
        setBotonHabilitado(false);
      }

    };

    cargarEstado();

  }, [email, esNetec, authHeader, tokenLoaded]);

  const toggle = () => setColapsado(v => !v);

  const enviarSolicitud = async () => {

    if (!API_BASE || !email) return;

    setEnviando(true);
    setError('');

    try {

      const res = await fetch(`${API_BASE}/solicitar-rol`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ correo: email })
      });

      const j = await res.json().catch(() => ({}));

      if (!res.ok) throw new Error(j.error || 'Error');

      setEstado('pendiente');

    } catch (e) {

      console.error(e);
      setError('Error de red');

    } finally {

      setEnviando(false);

    }

  };

  const esAdmin = grupo === 'admin';
  const esCreador = grupo === 'creador';

  const correosAdminPrincipales = [
    'anette.flores@netec.com.mx',
    'mitzi.montiel@netec.com',
    'america.vicente@netec.com.mx',
    'juan.londono@netec.com.co'
  ];

  const esAdminPrincipal = correosAdminPrincipales.includes(email.toLowerCase());

  const mostrarBoton =
    (esNetec || botonHabilitado) &&
    !(esCreador || esAdminPrincipal);

  const abrirPicker = () => setPickerAbierto(true);
  const cerrarPicker = () => setPickerAbierto(false);

  const onAvatarSaved = (url) => {
    setAvatar(url || null);
    window.dispatchEvent(new CustomEvent('profilePhotoUpdated', { detail: { photoUrl: url } }));
  };

  const rolTexto =
    grupo === 'admin' ? 'Administrador' :
      grupo === 'creador' ? 'Creador' :
        grupo === 'participant' ? 'Participante' :
          grupo === 'asignador' ? 'Asignador' :
            grupo === 'estudiante' ? 'Estudiante' :
              grupo === 'instructor_externo' ? 'Instructor Externo' :
                'Sin grupo';

  const disabled = estado === 'pendiente' || estado === 'aprobado' || enviando;

  const label =
    estado === 'aprobado' ? '✅ Ya eres Creador'
      : estado === 'pendiente' ? '⏳ Solicitud enviada'
        : '📩 Solicitar rol de Creador';

  return (

    <div id="barraLateral" className={`sidebar ${colapsado ? 'sidebar--colapsado' : ''}`}>

      <button className="collapse-btn" onClick={toggle}>
        {colapsado ? '▸' : '◂'}
      </button>

      <div className="perfilSidebar">

        <div className="avatar-wrap" onClick={abrirPicker}>
          <img
            src={avatar || defaultFoto}
            alt="Avatar"
            className="avatar-img"
          />
        </div>

        {!colapsado && <>
          <div className="nombre">{nombre || 'Usuario conectado'}</div>
          <div className="email">{email}</div>
          <div className="grupo">🎖️ Rol: {rolTexto}</div>

          {mostrarBoton && (
            <div className="solicitar-creador-card">
              <button
                className="solicitar-creador-btn"
                onClick={enviarSolicitud}
                disabled={disabled}
              >
                {label}
              </button>

              {!!error && <div className="solicitar-creador-error">{error}</div>}
            </div>
          )}
        </>}

      </div>

      {/* MENÚ */}

      <div id="caminito" className="caminito">

        {(esCreador || esAdminPrincipal) ? (
          <Link to="/generador-contenidos" className="nav-link">
            <div className="step">
              <div className="circle">✍️</div>
              {!colapsado && <span>Crear</span>}
            </div>
          </Link>
        ) : (
          <Link to="/usuarios" className="nav-link">
            <div className="step">
              <div className="circle">👥</div>
              {!colapsado && <span>Usuarios</span>}
            </div>
          </Link>
        )}

        <a
          href="https://nethoot-v2-online-479795236799.us-west1.run.app"
          target="_blank"
          rel="noopener noreferrer"
          className="nav-link"
        >
          <div className="step">
            <div className="circle">🎮</div>
            {!colapsado && <span>Nethoot</span>}
          </div>
        </a>

        <Link to="/resumenes" className="nav-link">
          <div className="step">
            <div className="circle">🧠</div>
            {!colapsado && <span>Resúmenes</span>}
          </div>
        </Link>

        <Link to="/actividades" className="nav-link">
          <div className="step">
            <div className="circle">📘</div>
            {!colapsado && <span>Actividades</span>}
          </div>
        </Link>

        <Link to="/examenes" className="nav-link">
          <div className="step">
            <div className="circle">🔬</div>
            {!colapsado && <span>Examen</span>}
          </div>
        </Link>

      </div>

      <AvatarPicker
        isOpen={pickerAbierto}
        onClose={cerrarPicker}
        email={email}
        onSaved={onAvatarSaved}
      />

    </div>
  );
}
