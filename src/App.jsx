// src/App.jsx (CORREGIDO Y FUNCIONAL)
import React, { useEffect, useState, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useLocation } from 'react-router-dom';
import { fetchAuthSession, signOut, signInWithRedirect } from 'aws-amplify/auth';
import { Hub } from 'aws-amplify/utils';
import './App.css';
import './amplify';
import { Toaster } from 'react-hot-toast';

// === EDITORES ===
import EditorDeTemario_seminario from './components/EditorDeTemario_seminario.jsx';
import EditorTemarioPage from "./components/EditorTemarioPage.jsx";
import EditorDeTemario_Practico from './components/EditorDeTemario_Practico.jsx';
import EditorDeTemario_KNTR from "./components/EditorDeTemario_KNTR.jsx";

// === IMÁGENES ===
import logoImg from './assets/Netec.png';
import previewImgSrc from './assets/Preview.png';
import chileFlagImg from './assets/chile.png';
import peruFlagImg from './assets/peru.png';
import colombiaFlagImg from './assets/colombia.png';
import mexicoFlagImg from './assets/mexico.png';
import espanaFlagImg from './assets/espana.png';

// === COMPONENTES PRINCIPALES ===
import Sidebar from './components/Sidebar.jsx';
import ProfileModal from './components/ProfileModal.jsx';
import ChatModal from './components/ChatModal.jsx';
import Home from './components/Home.jsx';
import ActividadesPage from './components/ActividadesPage.jsx';
import ResumenesPage from './components/ResumenesPage.jsx';
import ExamenesPage from './components/ExamenesPage.jsx';
import AdminPage from './components/AdminPage.jsx';
import AdminRoute from './routes/AdminRoute';

// === GENERADOR DE CONTENIDOS ===
import GeneradorContenidosPage from './components/GeneradorContenidosPage.jsx';
import GeneradorContenido from './components/GeneradorContenido.jsx';
import GeneradorTemarios from './components/GeneradorTemarios.jsx';
import GeneradorTemarios_KNTR from './components/GeneradorTemarios_KNTR.jsx';
import GeneradorTemarios_Seminarios from './components/GeneradorTemarios_Seminarios.jsx';
import GeneradorCursos from './components/GeneradorCursos.jsx';
import GeneradorTemariosPracticos from './components/GeneradorTemariosPracticos.jsx';

import BookBuilderPage from './components/BookBuilderPage.jsx';
import BookEditorPage from './components/BookEditorPage.jsx';

import FAQ from "./components/FAQ.jsx";
import PresentacionesPage from './components/PresentacionesPage.jsx';
import InfographicViewer from './components/InfographicViewer.jsx';
import InfographicEditor from './components/InfographicEditor.jsx';



// ==================================================================
// ========================== EDITORES ==============================
// ==================================================================

function EditorSeminarioPage() {
  const { cursoId, versionId } = useParams();

  const onSave = async (contenido, nota) => {
    const token = sessionStorage.getItem("access_token");
    const res = await fetch(
      "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-seminario",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          cursoId,
          contenido,
          nota_version: nota || `Guardado el ${new Date().toISOString()}`,
          nombre_curso: contenido?.nombre_curso || "Sin título",
          tecnologia: contenido?.tecnologia || "",
          asesor_comercial: contenido?.asesor_comercial || "",
          nombre_preventa: contenido?.nombre_preventa || "",
          enfoque: contenido?.enfoque || "General",
          fecha_creacion: new Date().toISOString(),
        }),
      }
    );
    if (!res.ok) throw new Error((await res.json()).error || "Error al guardar versión");
  };

  return <EditorDeTemario_seminario temarioInicial={null} onSave={onSave} isLoading={false} />;
}

// === PRÁCTICO ===
function EditorPracticoPage() {
  const { cursoId, versionId } = useParams();
  const [temarioInicial, setTemarioInicial] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const token = sessionStorage.getItem("access_token");
        const res = await fetch(
          "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-practico/get",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ cursoId, versionId }),
          }
        );

        const json = await res.json();
        const item = json.data || json;
        setTemarioInicial(item.contenido ?? item);
      } catch (e) {
        console.error("Error cargando versión práctica:", e);
      } finally {
        setIsLoading(false);
      }
    };

    fetchVersion();
  }, [cursoId, versionId]);

  const onSave = async (contenido, nota) => {
    const token = sessionStorage.getItem("access_token");
    const res = await fetch(
      "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-practico",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          cursoId,
          contenido,
          nota_version: nota || `Guardado el ${new Date().toISOString()}`,
          nombre_curso: contenido?.nombre_curso,
        }),
      }
    );
    if (!res.ok) throw new Error("Error al guardar versión práctica");
  };

  return (
    <EditorDeTemario_Practico
      temarioInicial={temarioInicial}
      onSave={onSave}
      isLoading={isLoading}
    />
  );
}

// === KNTR ===
function EditorKNTRPage() {
  const { cursoId, versionId } = useParams();
  const [temarioInicial, setTemarioInicial] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const token = sessionStorage.getItem("access_token");
        const res = await fetch(
          "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-KNTR/get",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({ cursoId, versionId }),
          }
        );

        const json = await res.json();
        const item = json.data || json;
        setTemarioInicial(item.contenido ?? item);
      } catch (e) {
        console.error("Error cargando versión KNTR:", e);
      } finally {
        setIsLoading(false);
      }
    };

    fetchVersion();
  }, [cursoId, versionId]);

  const onSave = async (contenido, nota) => {
    const token = sessionStorage.getItem("access_token");
    await fetch(
      "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-KNTR",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          cursoId,
          contenido,
          nota_version: nota,
        }),
      }
    );
  };

  return (
    <EditorDeTemario_KNTR
      temarioInicial={temarioInicial}
      onSave={onSave}
      isLoading={isLoading}
    />
  );
}

// ==================================================================
// ========================= LAYOUT =================================
// ==================================================================

const Layout = ({ children, email, role }) => {
  const location = useLocation();
  const isBookEditor = location.pathname.startsWith('/book-editor');
  const isPresentationViewer = location.pathname.startsWith('/presentaciones/viewer/');
  const isInfographicEditor = location.pathname.startsWith('/presentaciones/editor/');

  const isFullScreenMode = isBookEditor || isPresentationViewer || isInfographicEditor;

  return (
    <div id="contenidoPrincipal" style={isFullScreenMode ? { paddingLeft: 0 } : {}}>
      {!isFullScreenMode && <Sidebar email={email} grupo={role} />}
      <ProfileModal />
      {!isBookEditor && <ChatModal />}

      <main className="main-content-area" style={isFullScreenMode ? { marginLeft: 0, width: '100%' } : {}}>
        {children}
      </main>

      {!isFullScreenMode && (
        <button
          id="logout"
          onClick={async () => {
            try {
              try { sessionStorage.clear(); } catch (e) {}
              try { bcRef.current?.postMessage('signedOut'); } catch(e) {}
              await signOut({ global: true });
              window.location.href = "/";
            } catch (err) {
              console.error("Logout error:", err);
              window.location.href = "/";
            }
          }}
        >
          Cerrar sesión
        </button>
      )}
    </div>
  );
};


// ==================================================================
// ============================== APP ================================
// ==================================================================

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [signingIn, setSigningIn] = useState(false);
  const [loginError, setLoginError] = useState(null);
  const bcRef = useRef(null);

  // ======== Autenticación Amplify ========
  useEffect(() => {
    bcRef.current = new BroadcastChannel('auth');
    const onMessage = (ev) => {
      if (ev.data === 'signedOut') {
        setUser(null);
        setLoading(false);
      }
      if (ev.data === 'signedIn') {
        checkAuthSession();
      }
    };
    bcRef.current.onmessage = onMessage;

    const hubListener = Hub.listen('auth', ({ payload, source }) => {
      if (source !== 'auth') return;
      if (payload.event === 'signedOut') {
        bcRef.current?.postMessage('signedOut');
        setUser(null);
        setLoading(false);
      }
      if (payload.event === 'signedIn' || payload.event === 'tokenRefresh') {
        checkAuthSession();
      }
    });

    // primer chequeo
    checkAuthSession();

    return () => {
      try { hubListener(); } catch(e) {}
      try { bcRef.current?.close(); } catch(e) {}
    };
  }, []);


  const checkAuthSession = () => {
    fetchAuthSession()
      .then((session) => {
        const idToken = session.tokens?.idToken;
        const accessToken = session.tokens?.accessToken;

        if (!idToken || !accessToken) throw new Error("No tokens available");

        const attributes = idToken.payload;
        // Para la lógica/gestión de usuarios preferimos los grupos del idToken
        const groups =
          (idToken.payload && idToken.payload["cognito:groups"]) ||
          (accessToken.payload && accessToken.payload["cognito:groups"]) ||
          [];

        // Guardar tokens correctos en sessionStorage
        sessionStorage.setItem("id_token", idToken.jwtToken);
        sessionStorage.setItem("access_token", accessToken.jwtToken);

        // DEBUG: revisar en consola los claims para validar dónde están los grupos
        console.debug("checkAuthSession -> tokens payloads:", {
          idTokenPayload: idToken.payload,
          accessTokenPayload: accessToken.payload,
          resolvedGroups: groups,
        });

        // DEBUG: solo mostrar grupos en desarrollo
        if (import.meta.env.DEV) {
          try {
            const groupsForDebug =
              (accessToken?.payload && accessToken.payload["cognito:groups"]) ||
              (idToken?.payload && idToken.payload["cognito:groups"]) ||
              [];
            console.debug("Grupos Cognito (DEV):", groupsForDebug);
          } catch (e) {
            // no bloquear producción si algo falla
          }
        }

        setUser({ attributes, groups });
        setLoading(false);
      })
      .catch((err) => {
        // Caso típico: usuario aún no ha iniciado sesión
        if (err?.message === 'No tokens available') {
          console.log('No hay sesión activa todavía, mostrando pantalla de login.');
        } else {
          console.warn('checkAuthSession error:', err);
          try { sessionStorage.clear(); } catch (e) {}
        }

        if (err?.message?.includes('UserNotConfirmedException')) {
          window.location.href = `https://${import.meta.env.VITE_COGNITO_DOMAIN}/signup`;
          return;
        }

        setUser(null);
        setLoading(false);
      });

  };

  const email = user?.attributes?.email || '';
  // raw groups from Cognito (may be undefined)
  const rawGroups = user?.groups || [];

  // normalizar nombres de grupo para comparaciones robustas
  const groups = Array.isArray(rawGroups) ? rawGroups.map(g => String(g || '').toLowerCase().trim()) : [];

  // rol derivado (prioridad: admin > creador > participante)
  const rol =
    groups.includes('administrador') || groups.includes('admin') ? 'admin' :
    groups.includes('creador') ? 'creador' :
    groups.includes('participante') ? 'participant' :
    'usuario';

  const groupNameForRole = {
    admin: "Administrador",
    creador: "Creador",
    participant: "Participante",
  };

  const ProtectedRoute = ({ children, allowedRoles = [] }) => {
    if (!user) return <Navigate to="/" replace />;

    if (allowedRoles.length === 0) return children;

    // permiso por rol derivado
    if (allowedRoles.includes(rol)) return children;

    // comprobar grupos Cognito normalizados
    const userGroupsNormalized = (user?.groups || []).map(g => String(g || '').toLowerCase().trim());

    const allowedGroupNamesNormalized = allowedRoles
      .map(r => (groupNameForRole[r] || r))
      .filter(Boolean)
      .map(g => String(g).toLowerCase().trim());

    const hasGroup = allowedGroupNamesNormalized.some(g => userGroupsNormalized.includes(g));
    if (hasGroup) return children;

    return <Navigate to="/" replace />;
  };

  // apiFetch: wrapper simple para añadir Authorization y detectar 401
  const apiFetch = async (url, opts = {}) => {
    const token = sessionStorage.getItem('access_token');
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;

    const res = await fetch(url, { ...opts, headers });
    if (res.status === 401) {
      try { sessionStorage.clear(); } catch(e) {}
      setUser(null);
      window.location.href = '/';
      throw new Error('Unauthorized');
    }
    return res;
  };

  if (loading) return <div>Cargando...</div>;

  // ==================================================================
  // ========================= RUTAS CORREGIDAS ========================
  // ==================================================================

  return (
    <>
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
      {!user ? (
        // ========== PANTALLA INICIAL (NO AUTENTICADO) ==========
        <div id="paginaInicio">
          <div className="header-bar">
            <img className="logo-left" src={logoImg} alt="Logo Netec" />
          </div>

          <div className="main-content">
            <div className="page-container">
              <div className="illustration-centered">
                <img src={previewImgSrc} alt="Ilustración" className="preview-image" />
              </div>

              <button
                className="login-button"
                onClick={async () => {
                  try {
                    setSigningIn(true);
                    setLoginError(null);
                    await signInWithRedirect(); // Hosted UI + PKCE correcto
                  } catch (err) {
                    console.error("Error al iniciar sesión:", err);
                    setSigningIn(false);
                    setLoginError("No se pudo iniciar sesión. Intenta nuevamente.");
                  }
                }}
                disabled={signingIn}
              >
                {signingIn ? "Iniciando…" : "🚀 Comenzar Ahora"}
              </button>

              {loginError && <div className="login-error-banner">{loginError}</div>}

              <div className="country-flags">
                <a href="https://www.netec.com/cursos-ti-chile" target="_blank">
                  <img src={chileFlagImg} alt="Chile" />
                </a>
                <a href="https://www.netec.com/cursos-ti-peru" target="_blank">
                  <img src={peruFlagImg} alt="Perú" />
                </a>
                <a href="https://www.netec.com/cursos-ti-colombia" target="_blank">
                  <img src={colombiaFlagImg} alt="Colombia" />
                </a>
                <a href="https://www.netec.com/cursos-ti-mexico" target="_blank">
                  <img src={mexicoFlagImg} alt="México" />
                </a>
                <a href="https://www.netec.es/" target="_blank">
                  <img src={espanaFlagImg} alt="España" />
                </a>
              </div>
            </div>
          </div>
        </div>
      ) : (
        // ========== APLICACIÓN PRINCIPAL (AUTENTICADO) ==========
        <Router>
          <Layout email={email} role={rol}>
            <Routes>
              {/* rutas públicas para usuarios autenticados */}
              <Route path="/" element={<Home />} />
              <Route path="/resumenes" element={<ResumenesPage />} />
              <Route path="/actividades" element={<ActividadesPage />} />
              <Route path="/examenes" element={<ExamenesPage />} />

              {/* ADMIN */}
              <Route
                path="/admin"
                element={
                  <AdminRoute>
                    <AdminPage />
                  </AdminRoute>
                }
              />

              {/* GENERADOR DE CONTENIDOS -> admin/creador */}
              <Route
                path="/generador-contenidos"
                element={
                  <ProtectedRoute allowedRoles={['admin', 'creador']}>
                    <GeneradorContenidosPage />
                  </ProtectedRoute>
                }
              >
                <Route path="curso-estandar" element={<GeneradorTemarios />} />
                <Route path="curso-KNTR" element={<GeneradorTemarios_KNTR />} />
                <Route path="Temario-seminarios" element={<GeneradorTemarios_Seminarios />} />
                <Route path="generador-cursos" element={<GeneradorCursos />} />
                <Route path="book-builder" element={<BookBuilderPage />} />
                <Route path="generador-contenido" element={<GeneradorContenido />} />
                <Route path="temario-practico" element={<GeneradorTemariosPracticos />} />
                <Route path="faq" element={<FAQ />} />
              </Route>

              {/* PRESENTACIONES -> accesible a todos autenticados */}
              <Route path="/presentaciones" element={<ProtectedRoute><PresentacionesPage /></ProtectedRoute>} />
              <Route path="/presentaciones/viewer/:folder" element={<ProtectedRoute><InfographicViewer /></ProtectedRoute>} />
              <Route path="/presentaciones/editor/:folder" element={<ProtectedRoute allowedRoles={['admin','creador']}><InfographicEditor /></ProtectedRoute>} />

              {/* EDITORES EXTERNOS -> admin/creador */}
              <Route path="/editor-seminario/:cursoId/:versionId" element={<ProtectedRoute allowedRoles={['admin','creador']}><EditorSeminarioPage /></ProtectedRoute>} />
              <Route path="/editor-temario/:cursoId/:versionId" element={<ProtectedRoute allowedRoles={['admin','creador']}><EditorTemarioPage /></ProtectedRoute>} />
              <Route path="/editor-practico/:cursoId/:versionId" element={<ProtectedRoute allowedRoles={['admin','creador']}><EditorPracticoPage /></ProtectedRoute>} />
              <Route path="/editor-KNTR/:cursoId/:versionId" element={<ProtectedRoute allowedRoles={['admin','creador']}><EditorKNTRPage /></ProtectedRoute>} />

              {/* BOOK EDITOR -> creador/admin */}
              <Route path="/book-editor/:projectFolder" element={<ProtectedRoute allowedRoles={['admin','creador']}><BookEditorPage /></ProtectedRoute>} />

              {/* FALLBACK */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </Router>
      )}
    </>
  );
}

export default App;
