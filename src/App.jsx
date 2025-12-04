
// src/App.jsx (CORREGIDO Y FUNCIONAL)
import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useLocation } from 'react-router-dom';
import { fetchAuthSession, signOut, signInWithRedirect } from 'aws-amplify/auth';
import { Hub } from 'aws-amplify/utils';
import './App.css';

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
    const token = localStorage.getItem("id_token");
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
        const token = localStorage.getItem("id_token");
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
    const token = localStorage.getItem("id_token");
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
        const token = localStorage.getItem("id_token");
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
    const token = localStorage.getItem("id_token");
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
        <button id="logout" onClick={async () => {
          try {
            await signOut({ global: true });
          } catch (err) {
            console.error('Logout error:', err);
            localStorage.clear();
            window.location.href = '/';
          }
        }}>
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

// ======== Autenticación Amplify ========
useEffect(() => {

  const hubListener = Hub.listen('auth', ({ payload }) => {
    console.log("Auth Event:", payload.event);

    if (payload.event === 'signedIn') {
      // OAuth COMPLETÓ correctamente → ahora SÍ se puede limpiar el code
      window.history.replaceState({}, document.title, window.location.pathname);
      checkAuthSession();
    }

    if (payload.event === 'tokenRefresh') {
      checkAuthSession();
    }

    if (payload.event === 'signedOut') {
      setUser(null);
      setLoading(false);
    }
  });

  // NO limpiar aquí el code (esto causaba inestabilidad)
  checkAuthSession();

  return () => hubListener();
}, []);


  const checkAuthSession = () => {
    fetchAuthSession()
      .then((session) => {
        const idToken = session.tokens?.idToken;
        const accessToken = session.tokens?.accessToken;

        if (!idToken || !accessToken) throw new Error('No tokens available');

        const attributes = idToken.payload;
        const groups = accessToken.payload['cognito:groups'] || [];

        localStorage.setItem('id_token', idToken.toString());
        localStorage.setItem('access_token', accessToken.toString());

        setUser({ attributes, groups });
        setLoading(false);
      })
      .catch(() => {
        setUser(null);
        setLoading(false);
      });
  };

  const email = user?.attributes?.email || '';
  const groups = user?.groups || [];
  let rol = '';

  if (groups.includes('Administrador')) rol = 'admin';
  else if (groups.includes('Creador')) rol = 'creador';
  else if (groups.includes('Participante')) rol = 'participant';

  if (loading) return <div>Loading...</div>;

  // ==================================================================
  // ========================= RUTAS CORREGIDAS ========================
  // ==================================================================

  return (
    <>
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
                onClick={() => signInWithRedirect({ provider: 'Cognito' })}
              >
                🚀 Comenzar Ahora
              </button>

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

              {/* === RUTAS DEL SIDEBAR → YA NO SE PASMAN === */}
              <Route path="/" element={<Home />} />
              <Route path="/resumenes" element={<ResumenesPage />} />
              <Route path="/actividades" element={<ActividadesPage />} />
              <Route path="/examenes" element={<ExamenesPage />} />

              {/* === ADMIN === */}
              <Route path="/admin" element={<AdminPage />} />

              {/* === GENERADOR DE CONTENIDOS === */}
              <Route path="/generador-contenidos" element={<GeneradorContenidosPage />}>
                <Route path="curso-estandar" element={<GeneradorTemarios />} />
                <Route path="curso-KNTR" element={<GeneradorTemarios_KNTR />} />
                <Route path="Temario-seminarios" element={<GeneradorTemarios_Seminarios />} />
                <Route path="generador-cursos" element={<GeneradorCursos />} />
                <Route path="book-builder" element={<BookBuilderPage />} />
                <Route path="generador-contenido" element={<GeneradorContenido />} />
                <Route path="temario-practico" element={<GeneradorTemariosPracticos />} />
                <Route path="faq" element={<FAQ />} />
              </Route>

              {/* === PRESENTACIONES === */}
              <Route path="/presentaciones" element={<PresentacionesPage />} />
              <Route path="/presentaciones/viewer/:folder" element={<InfographicViewer />} />
              <Route path="/presentaciones/editor/:folder" element={<InfographicEditor />} />

              {/* === EDITORES EXTERNOS === */}
              <Route path="/editor-seminario/:cursoId/:versionId" element={<EditorSeminarioPage />} />
              <Route path="/editor-temario/:cursoId/:versionId" element={<EditorTemarioPage />} />
              <Route path="/editor-practico/:cursoId/:versionId" element={<EditorPracticoPage />} />
              <Route path="/editor-KNTR/:cursoId/:versionId" element={<EditorKNTRPage />} />
              <Route path="/book-editor/:projectFolder" element={<BookEditorPage />} />

              {/* === FALLBACK === */}
              <Route path="*" element={<Navigate to="/" replace />} />

            </Routes>
          </Layout>
        </Router>
      )}
    </>
  );
}

export default App;
