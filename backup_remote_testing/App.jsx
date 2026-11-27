// src/App.jsx (ACTUALIZADO FINAL)

import { useEffect, useMemo, useState } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import { Auth } from "aws-amplify";

// Componentes
import Sidebar from "./components/Sidebar";
import ChatModal from "./components/ChatModal";
import ProfileModal from "./components/ProfileModal";
import Home from "./components/Home";
import ActividadesPage from "./components/ActividadesPage";
import ResumenesPage from "./components/ResumenesPage";
import ExamenesPage from "./components/ExamenesPage";
import AdminPage from "./components/AdminPage";
import GeneradorContenidosPage from "./components/GeneradorContenidosPage";
import GeneradorTemarios from "./components/GeneradorTemarios";
import GeneradorTemarios_KNTR from "./components/GeneradorTemarios_KNTR";
import GeneradorTemarios_Seminarios from "./components/GeneradorTemarios_Seminarios"; // ✅ NUEVO
import EditorDeTemario_seminario from "./components/EditorDeTemario_seminario";
import GeneradorTemariosPracticos from "../src/components/GeneradorTemariosPracticos";
import EditorDeTemario_Practico from "../src/components/EditorDeTemario_Practico";
import EditorDeTemario_KNTR from "../src/components/EditorDeTemario_KNTR";
 // ✅ YA EXISTENTE

// Estilos y Assets
import "./index.css";
import logo from "./assets/Netec.png";
import previewImg from "./assets/Preview.png";
import chileFlag from "./assets/chile.png";
import peruFlag from "./assets/peru.png";
import colombiaFlag from "./assets/colombia.png";
import mexicoFlag from "./assets/mexico.png";
import espanaFlag from "./assets/espana.png";

const ADMIN_EMAIL = "anette.flores@netec.com.mx";

const normalizarRol = (raw) => {
  if (!raw) return "";
  const parts = String(raw).toLowerCase().split(/[,\s]+/).filter(Boolean);
  if (parts.includes("admin")) return "admin";
  if (parts.includes("creador")) return "creador";
  if (parts.includes("participant")) return "participant";
  return parts[0] || "";
};

function App() {
  const [token, setToken] = useState(localStorage.getItem("id_token") || "");
  const [email, setEmail] = useState("");
  const [rol, setRol] = useState("");

  // === AUTENTICACIÓN COGNITO ===
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID;
  const domain = import.meta.env.VITE_COGNITO_DOMAIN;
  const redirectUri = import.meta.env.VITE_REDIRECT_URI_TESTING;

  const loginUrl = useMemo(() => {
    if (!domain || !clientId || !redirectUri) return "";
    const u = new URL(`${domain}/login`);
    u.searchParams.append("response_type", "token");
    u.searchParams.append("client_id", clientId);
    u.searchParams.append("redirect_uri", redirectUri);
    return u.toString();
  }, [clientId, domain, redirectUri]);

  const handleLogout = () => {
    localStorage.removeItem("id_token");
    const u = new URL(`${domain}/logout`);
    u.searchParams.append("client_id", clientId);
    u.searchParams.append("logout_uri", redirectUri);
    window.location.href = u.toString();
  };

  // === Capturar token desde URL (login exitoso) ===
  useEffect(() => {
    const { hash } = window.location;
    if (hash.includes("id_token=")) {
      const newToken = new URLSearchParams(hash.slice(1)).get("id_token");
      if (newToken) {
        localStorage.setItem("id_token", newToken);
        setToken(newToken);
      }
      window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
    }
  }, []);

  // === Decodificar token ===
  useEffect(() => {
    if (!token) {
      setEmail("");
      setRol("");
      return;
    }
    try {
      const decoded = jwtDecode(token);
      const decodedEmail = decoded?.email || "";
      setEmail(decodedEmail);
      if (decodedEmail === ADMIN_EMAIL) setRol("admin");
      else setRol(normalizarRol(decoded?.["custom:rol"]));
    } catch (err) {
      console.error("❌ Error al decodificar token:", err);
      localStorage.removeItem("id_token");
      setToken("");
      setEmail("");
      setRol("");
    }
  }, [token]);

  // === Refrescar atributos de usuario cada 60s ===
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const refreshFromCognito = () => {
      Auth.currentAuthenticatedUser({ bypassCache: true })
        .then((u) => {
          if (cancelled) return;
          const freshRol = normalizarRol(u?.attributes?.["custom:rol"] || "");
          const freshEmail = u?.attributes?.email || "";
          if (freshEmail && freshEmail !== email) setEmail(freshEmail);
          if (freshEmail === ADMIN_EMAIL) setRol("admin");
          else if (freshRol && freshRol !== rol) setRol(freshRol);
        })
        .catch(() => {});
    };
    refreshFromCognito();
    const iv = setInterval(refreshFromCognito, 60_000);
    return () => {
      cancelled = true;
      clearInterval(iv);
    };
  }, [token, email, rol]);

  const adminAllowed = email === ADMIN_EMAIL;

  // === INTERFAZ PRINCIPAL ===
  return (
    <>
      {!token ? (
        // --- Pantalla de login ---
        <div id="paginaInicio">
          <div className="header-bar">
            <img className="logo-left" src={logo} alt="Logo Netec" />
          </div>
          <div className="main-content">
            <div className="page-container">
              <div className="illustration-centered">
                <img src={previewImg} alt="Ilustración" className="preview-image" />
              </div>
              <button className="login-button" onClick={() => loginUrl && (window.location.href = loginUrl)}>
                🚀 Comenzar Ahora
              </button>
              <div className="country-flags">
                {[
                  { flag: chileFlag, label: "Chile", url: "https://www.netec.com/cursos-ti-chile" },
                  { flag: peruFlag, label: "Perú", url: "https://www.netec.com/cursos-ti-peru" },
                  { flag: colombiaFlag, label: "Colombia", url: "https://www.netec.com/cursos-ti-colombia" },
                  { flag: mexicoFlag, label: "México", url: "https://www.netec.com/cursos-ti-mexico" },
                  { flag: espanaFlag, label: "España", url: "https://www.netec.es/" },
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
        // --- App privada ---
        <Router>
          <div id="contenidoPrincipal">
            <Sidebar email={email} grupo={rol} token={token} />
            <ProfileModal token={token} />
            <ChatModal token={token} />

            <main className="main-content-area">
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/actividades" element={<ActividadesPage token={token} />} />
                <Route path="/resumenes" element={<ResumenesPage />} />
                <Route path="/examenes" element={<ExamenesPage token={token} />} />
                <Route
                  path="/admin"
                  element={adminAllowed ? <AdminPage /> : <Navigate to="/" replace />}
                />

                {/* --- RUTAS DE GENERADORES --- */}
                <Route path="/generador-contenidos" element={<GeneradorContenidosPage />}>
                  <Route path="curso-estandar" element={<GeneradorTemarios />} />
                  <Route path="curso-KNTR" element={<GeneradorTemarios_KNTR />} />
                  <Route path="seminario" element={<GeneradorTemarios_Seminarios />} /> {/* ✅ NUEVA */}
                  <Route path="temario-practico" element={<GeneradorTemariosPracticos />} />
                </Route>

                {/* --- Editor desde DynamoDB --- */}
                <Route
                  path="/editor-seminario/:cursoId/:versionId"
                  element={<EditorDeTemario_seminario />}
                />
                <Route
                  path="/editor-practico/:cursoId/:versionId"
                  element={<EditorDeTemario_Practico />}
                />
                <Route
                  path="/editor-KNTR/:cursoId/:versionId"
                  element={<EditorDeTemario_KNTR />}
                />

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
            <button id="logout" onClick={handleLogout}>
              Cerrar sesión
            </button>
          </div>
        </Router>
      )}
    </>
  );
}

export default App;
