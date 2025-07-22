// src/App.jsx (CÓDIGO COMPLETO Y CORREGIDO)

import { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Auth } from 'aws-amplify';
import { jwtDecode } from "jwt-decode";



// Componentes
import Sidebar from './components/Sidebar';
import ChatModal from './components/ChatModal';
import ProfileModal from './components/ProfileModal';
import Home from './components/Home';
import ActividadesPage from './components/ActividadesPage'; // Importa la página de actividades

// Estilos y Assets
import './index.css'; // Tu CSS principal
import logo from './assets/Netec.png';
import previewImg from './assets/Preview.png';
// Importa tus banderas si las usas en este archivo
import chileFlag from './assets/chile.png';
import peruFlag from './assets/peru.png';
import colombiaFlag from './assets/colombia.png';
import mexicoFlag from './assets/mexico.png';
import espanaFlag from './assets/espana.png';


function App() {
  const [token, setToken] = useState(localStorage.getItem("id_token"));
  const [email, setEmail] = useState("");

  console.log("📦 Token desde localStorage:", localStorage.getItem("id_token")); // <--- AÑADE ESTO


  // Lógica de Cognito (sin cambios)
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const domain = import.meta.env.VITE_COGNITO_DOMAIN;
  const redirectUri = import.meta.env.VITE_REDIRECT_URI_TESTING;
  const loginUrl = `${domain}/login?response_type=token&client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}`;

   useEffect(() => {
    const hash = window.location.hash;
    if (hash.includes("id_token")) {
      const newToken = hash.split("id_token=")[1].split("&")[0];
      console.log("🪪 Token recibido:", newToken); // <-- Agrega esto
      localStorage.setItem("id_token", newToken);
      setToken(newToken);
      window.history.pushState("", document.title, window.location.pathname + window.location.search);
    }
  }, []);

  // Obtiene el correo del usuario si ya hay token

  const handleLogout = () => {
    localStorage.removeItem("id_token");
    const logoutUrl = `${domain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(redirectUri)}`;
    window.location.href = logoutUrl;
  };

useEffect(() => {
  if (token) {
    try {
      console.log("🪪 Token recibido:", token); // <-- AÑADIDO
      const decoded = jwtDecode(token); 
      console.log("✅ Token decodificado:", decoded);
      setEmail(decoded.email);
    } catch (err) {
      console.error("❌ Error al decodificar el token:", err);
    }
  }
}, [token]);

console.log("🧪 Email en App.jsx:", email);

  return (
    <>
      {!token ? (
        // --- PÁGINA DE LOGIN (sin cambios significativos en la estructura aquí) ---
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
                <a href="https://www.netec.com/cursos-ti-chile" target="_blank" rel="noopener noreferrer" className="flag-item">
                  <img src={chileFlag} alt="Chile" className="flag-image" />
                  <div className="flag-label">Chile</div>
                </a>
                <a href="https://www.netec.com/cursos-ti-peru" target="_blank" rel="noopener noreferrer" className="flag-item">
                  <img src={peruFlag} alt="Perú" className="flag-image" />
                  <div className="flag-label">Perú</div>
                </a>
                <a href="https://www.netec.com/cursos-ti-colombia" target="_blank" rel="noopener noreferrer" className="flag-item">
                  <img src={colombiaFlag} alt="Colombia" className="flag-image" />
                  <div className="flag-label">Colombia</div>
                </a>
                <a href="https://www.netec.com/cursos-ti-mexico" target="_blank" rel="noopener noreferrer" className="flag-item">
                  <img src={mexicoFlag} alt="México" className="flag-image" />
                  <div className="flag-label">México</div>
                </a>
                <a href="https://www.netec.es/" target="_blank" rel="noopener noreferrer" className="flag-item">
                  <img src={espanaFlag} alt="España" className="flag-image" />
                  <div className="flag-label">España</div>
                </a>
              </div>
            </div>
          </div>
        </div>
      ) : (
        // --- VISTA PRINCIPAL (ESTRUCTURA CORREGIDA) ---
        <Router>
          <div id="contenidoPrincipal"> {/* Este div es ahora el contenedor flex */}
            <Sidebar email={email} /> 
            <div style={{ padding: '1rem', background: '#f3f3f3', fontSize: '0.9rem' }}>
              <strong>📧 Correo: {email}</strong>
            </div>

            <ProfileModal token={token} />
            <ChatModal token={token} />

            {/* El <main> con 'margin-left' que empuja el contenido */}
            <main className="main-content-area">
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/actividades" element={<ActividadesPage token={token} />} />
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
