// src/App.jsx
import { useEffect, useMemo, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';
import { Auth } from 'aws-amplify'; // ⬅️ NUEVO: para refrescar atributos reales

import Sidebar from './components/Sidebar';
import ChatModal from './components/ChatModal';
import ProfileModal from './components/ProfileModal';

import Home from './components/Home';
import ActividadesPage from './components/ActividadesPage';
import ResumenesPage from './components/ResumenesPage';
import ExamenesPage from './components/ExamenesPage';
import AdminPage from './components/AdminPage';

import './index.css';
import logo from './assets/Netec.png';
import previewImg from './assets/Preview.png';
import chileFlag from './assets/chile.png';
import peruFlag from './assets/peru.png';
import colombiaFlag from './assets/colombia.png';
import mexicoFlag from './assets/mexico.png';
import espanaFlag from './assets/espana.png';

const ADMIN_EMAIL = 'anette.flores@netec.com.mx';

function App() {
  const [token, setToken] = useState(localStorage.getItem('id_token') || '');
  const [email, setEmail] = useState('');
  const [rol, setRol] = useState(''); // "admin" | "creador" | "participant" | ""

  // ⚙️ Cognito env vars
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const domain = import.meta.env.VITE_COGNITO_DOMAIN; // Ej: https://us-xxx.auth.us-east-1.amazoncognito.com
  const redirectUri = import.meta.env.VITE_REDIRECT_URI_TESTING;

  const loginUrl = useMemo(() => {
    const u = new URL(`${domain}/login`);
    u.searchParams.append('response_type', 'token');
    u.searchParams.append('client_id', clientId);
    u.searchParams.append('redirect_uri', redirectUri);
    return u.toString();
  }, [clientId, domain, redirectUri]);

  // 1) Captura id_token en el hash al volver de Cognito
  useEffect(() => {
    const { hash } = window.location;
    if (hash.includes('id_token=')) {
      const newToken = new URLSearchParams(hash.slice(1)).get('id_token');
      if (newToken) {
        localStorage.setItem('id_token', newToken);
        setToken(newToken);
      }
      // Limpia el hash de la URL
      window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
    }
  }, []);

  // 2) Decodifica token (rápido) para email y rol inicial
  useEffect(() => {
    if (!token) return;
    try {
      const decoded = jwtDecode(token);
      setEmail(decoded?.email || '');
      setRol(decoded?.['custom:rol'] || '');
    } catch (err) {
      console.error('❌ Error al decodificar token:', err);
      setEmail('');
      setRol('');
    }
  }, [token]);

  // 3) 🔄 REFRESCAR ROL REAL desde Cognito (bypass cache)
  //    Esto corrige el caso en que el id_token quedó con "creador", pero ya fue revocado/rechazado/eliminado.
  useEffect(() => {
    if (!token) return;

    const refreshFromCognito = () => {
      Auth.currentAuthenticatedUser({ bypassCache: true })
        .then(u => {
          const freshRol = u?.attributes?.['custom:rol'] || '';
          const freshEmail = u?.attributes?.email || '';
          if (freshEmail && freshEmail !== email) setEmail(freshEmail);
          if (freshRol && freshRol !== rol) setRol(freshRol);
        })
        .catch(err => {
          // Si el usuario no está autenticado vía Amplify, no pasa nada.
          // (La app seguirá con el rol del token hasta que vuelva a iniciar sesión)
          console.log('No se pudo refrescar atributos de Cognito', err?.message || err);
        });
    };

    // a) Al montar / tener token
    refreshFromCognito();

    // b) Cada vez que la ventana recupera foco
    const onFocus = () => refreshFromCognito();
    window.addEventListener('focus', onFocus);

    // c) (Opcional) refresco periódico suave: cada 60s
    const iv = setInterval(refreshFromCognito, 60_000);

    return () => {
      window.removeEventListener('focus', onFocus);
      clearInterval(iv);
    };
  }, [token, email, rol]);

  // 4) Cerrar sesión
  const handleLogout = () => {
    localStorage.removeItem('id_token');
    const u = new URL(`${domain}/logout`);
    u.searchParams.append('client_id', clientId);
    u.searchParams.append('logout_uri', redirectUri);
    window.location.href = u.toString();
  };

  // 🔒 Solo esta persona puede ver/rutear a /admin
  const adminAllowed = email === ADMIN_EMAIL;

  return (
    <>
      {!token ? (
        // ---------- Pantalla de acceso ----------
        <div id="paginaInicio">
          <div className="header-bar">
            <img className="logo-left" src={logo} alt="Logo Netec" />
          </div>
          <div className="main-content">
            <div className="page-container">
              <div className="illustration-centered">
                <img src={previewImg} alt="Ilustración" className="preview-image" />
              </div>
              <button className="login-button" onClick={() => (window.location.href = loginUrl)}>
                🚀 Comenzar Ahora
              </button>
              <div className="country-flags">
                {[
                  { flag: chileFlag, label: 'Chile', url: 'https://www.netec.com/cursos-ti-chile' },
                  { flag: peruFlag, label: 'Perú', url: 'https://www.netec.com/cursos-ti-peru' },
                  { flag: colombiaFlag, label: 'Colombia', url: 'https://www.netec.com/cursos-ti-colombia' },
                  { flag: mexicoFlag, label: 'México', url: 'https://www.netec.com/cursos-ti-mexico' },
                  { flag: espanaFlag, label: 'España', url: 'https://www.netec.es/' }
                ].map(({ flag, label, url }) => (
                  <a key={label} href={url} target="_blank" rel="noopener noreferrer" className="flag-item">
                    <img src={flag} alt={label} className="flag-image" />
                    <div className="flag-label">{label}</div>
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        // ---------- App privada ----------
        <Router>
          <div id="contenidoPrincipal">
            {/* Pasamos el rol FRESCO a la barra lateral */}
            <Sidebar email={email} grupo={rol} token={token} />

            <ProfileModal token={token} />
            <ChatModal token={token} />

            <main className="main-content-area">
              <Routes>
                <Route path="/" element={<Home />} />
                {/* ✅ Actividades: siempre tu generador */}
                <Route path="/actividades" element={<ActividadesPage token={token} />} />

                <Route path="/resumenes" element={<ResumenesPage />} />
                <Route path="/examenes" element={<ExamenesPage />} />

                {/* 🔒 Admin SOLO para anette */}
                <Route
                  path="/admin"
                  element={adminAllowed ? <AdminPage /> : <Navigate to="/" replace />}
                />

                {/* Fallback */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>

            <button id="logout" onClick={handleLogout}>Cerrar sesión</button>
          </div>
        </Router>
      )}
    </>
  );
}

export default App;
