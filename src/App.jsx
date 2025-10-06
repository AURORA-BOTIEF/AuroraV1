// src/App.jsx (Corrected to use AWS Amplify Auth for proper session management and IAM credentials)
import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Auth } from 'aws-amplify';
import { hostedUiAuthorizeUrl } from './amplify.js';
// Image assets
import logoImg from './assets/Netec.png';
import previewImgSrc from './assets/Preview.png';
import chileFlagImg from './assets/chile.png';
import peruFlagImg from './assets/peru.png';
import colombiaFlagImg from './assets/colombia.png';
import mexicoFlagImg from './assets/mexico.png';
import espanaFlagImg from './assets/espana.png';

// Actual component imports
import Sidebar from './components/Sidebar.jsx';
import ProfileModal from './components/ProfileModal.jsx';
import ChatModal from './components/ChatModal.jsx';
import Home from './components/Home.jsx';
import ActividadesPage from './components/ActividadesPage.jsx';
import ResumenesPage from './components/ResumenesPage.jsx';
import ExamenesPage from './components/ExamenesPage.jsx';
import AdminPage from './components/AdminPage.jsx';
import GeneradorContenidosPage from './components/GeneradorContenidosPage.jsx';
import GeneradorContenido from './components/GeneradorContenido.jsx';
import GeneradorTemarios from './components/GeneradorTemarios.jsx';
import GeneradorTemarios_KNTR from './components/GeneradorTemarios_KNTR.jsx';
import GeneradorCursos from './components/GeneradorCursos.jsx';
import BookBuilderPage from './components/BookBuilderPage.jsx';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Image variables
  const logo = logoImg;
  const previewImg = previewImgSrc;
  const chileFlag = chileFlagImg;
  const peruFlag = peruFlagImg;
  const colombiaFlag = colombiaFlagImg;
  const mexicoFlag = mexicoFlagImg;
  const espanaFlag = espanaFlagImg;

  useEffect(() => {
    Auth.currentSession()
      .then((session) => {
        const idToken = session.getIdToken();
        const accessToken = session.getAccessToken();
        const attributes = idToken.payload;
        const groups = accessToken.payload['cognito:groups'] || [];
        console.log('Access Token payload:', JSON.stringify(accessToken.payload, null, 2));
        console.log('Groups found:', groups);
        setUser({ attributes, groups });
        setLoading(false);
      })
      .catch(() => {
        setUser(null);
        setLoading(false);
      });
  }, []);

  const handleLogout = () => {
    Auth.signOut();
  };

  const email = user?.attributes?.email || '';
  const groups = user?.groups || [];
  let rol = '';
  if (groups.includes('Administrador')) {
    rol = 'admin';
  } else if (groups.includes('Creador')) {
    rol = 'creador';
  } else if (groups.includes('Participante')) {
    rol = 'participant';
  }
  const adminAllowed = email === 'anette@netec.com' || rol === 'admin';

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <>
      {!user ? (
        // Authentication screen
        <div id="paginaInicio">
          <div className="header-bar">
            <img className="logo-left" src={logo} alt="Logo Netec" />
          </div>
          <div className="main-content">
            <div className="page-container">
              <div className="illustration-centered">
                <img src={previewImg} alt="Ilustración" className="preview-image" />
              </div>
              <button className="login-button" onClick={() => {
                const url = hostedUiAuthorizeUrl();
                if (url) {
                  window.location.href = url;
                } else {
                  console.error('No login URL available');
                }
              }}>
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
        // Main app
        <Router>
          <div id="contenidoPrincipal">
            <Sidebar email={email} grupo={rol} />
            <ProfileModal />
            <ChatModal />

            <main className="main-content-area">
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/actividades" element={<ActividadesPage />} />
                <Route path="/resumenes" element={<ResumenesPage />} />
                <Route path="/examenes" element={<ExamenesPage />} />
                <Route path="/admin" element={adminAllowed ? <AdminPage /> : <Navigate to="/" replace />} />
                <Route path="/generador-contenidos" element={<GeneradorContenidosPage />}>
                  <Route path="curso-estandar" element={<GeneradorTemarios />} />
                  <Route path="curso-KNTR" element={<GeneradorTemarios_KNTR />} />
                  <Route path="generador-cursos" element={<GeneradorCursos />} />
                  <Route path="book-builder" element={<BookBuilderPage />} />
                  <Route path="generador-contenido" element={<GeneradorContenido />} />
                </Route>
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