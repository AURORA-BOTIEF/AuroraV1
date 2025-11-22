// src/App.jsx (corregido y funcional)
import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useLocation } from 'react-router-dom';
import { fetchAuthSession, signOut, signInWithRedirect } from 'aws-amplify/auth';
import { Hub } from 'aws-amplify/utils';
import './App.css'; // si tienes estilos globales
import EditorDeTemario_seminario from './components/EditorDeTemario_seminario.jsx';
import EditorTemarioPage from "./components/EditorTemarioPage.jsx";
import EditorDeTemario_Practico from './components/EditorDeTemario_Practico.jsx';
import EditorDeTemario_KNTR from "./components/EditorDeTemario_KNTR.jsx";


// Imagenes
import logoImg from './assets/Netec.png';
import previewImgSrc from './assets/Preview.png';
import chileFlagImg from './assets/chile.png';
import peruFlagImg from './assets/peru.png';
import colombiaFlagImg from './assets/colombia.png';
import mexicoFlagImg from './assets/mexico.png';
import espanaFlagImg from './assets/espana.png';

// Componentes principales
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
import GeneradorTemarios_Seminarios from './components/GeneradorTemarios_Seminarios.jsx'
import GeneradorCursos from './components/GeneradorCursos.jsx';
import BookBuilderPage from './components/BookBuilderPage.jsx';
import BookEditorPage from './components/BookEditorPage.jsx';
import GeneradorTemariosPracticos from './components/GeneradorTemariosPracticos.jsx';
import FAQ from "./components/FAQ.jsx";
import PresentacionesPage from './components/PresentacionesPage.jsx';
import InfographicViewer from './components/InfographicViewer.jsx';
import InfographicEditor from './components/InfographicEditor.jsx';



// === Página de edición de seminario ===
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

// === Página de edición de temario práctico ===
function EditorPracticoPage() {
  const { cursoId, versionId } = useParams();

  const [temarioInicial, setTemarioInicial] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // 🔹 Cargar versión exacta desde Lambda (POST cursoId + versionId)
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
            body: JSON.stringify({
              cursoId,
              versionId
            }),
          }
        );

        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          throw new Error(errJson.error || `Error ${res.status} al obtener la versión`);
        }

        const json = await res.json();
        const item = json.data || json;

        // Normalmente el temario está en item.contenido; si no, usamos item tal cual
        const contenido = item.contenido ?? item;

        console.log("Versión práctica cargada desde Lambda:", item);
        console.log("Contenido enviado al editor:", contenido);

        setTemarioInicial(contenido);
      } catch (e) {
        console.error("Error cargando versión práctica:", e);
        setError(e.message || "Error al cargar la versión");
      } finally {
        setIsLoading(false);
      }
    };

    fetchVersion();
  }, [cursoId, versionId]);

  // 🔹 Guardado de versión (se queda igual)
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
          nombre_curso: contenido?.nombre_curso || "Sin título",
          tecnologia: contenido?.tecnologia || "",
          asesor_comercial: contenido?.asesor_comercial || "",
          nombre_preventa: contenido?.nombre_preventa || "",
          enfoque: contenido?.enfoque || "General",
          fecha_creacion: new Date().toISOString(),
        }),
      }
    );
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.error || "Error al guardar versión");
    }
  };

  if (error) {
    return <div style={{ padding: "1rem", color: "red" }}>Error cargando versión: {error}</div>;
  }

  return (
    <EditorDeTemario_Practico
      temarioInicial={temarioInicial}
      onSave={onSave}
      isLoading={isLoading}
    />
  );
}




// === Página de edición de temarios KNTR ===
function EditorKNTRPage() {
  const { cursoId, versionId } = useParams();

  const [temarioInicial, setTemarioInicial] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // 🔹 Cargar versión exacta desde Lambda (POST cursoId + versionId)
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
            body: JSON.stringify({
              cursoId,
              versionId
            }),
          }
        );

        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          throw new Error(errJson.error || `Error ${res.status} al obtener la versión`);
        }

        const json = await res.json();
        const item = json.data || json;

        // Normalmente el temario está en item.contenido; si no, usamos item tal cual
        const contenido = item.contenido ?? item;

        console.log("Versión KNTR cargada desde Lambda:", item);
        console.log("Contenido enviado al editor:", contenido);

        setTemarioInicial(contenido);
      } catch (e) {
        console.error("Error cargando versión KNTR:", e);
        setError(e.message || "Error al cargar la versión");
      } finally {
        setIsLoading(false);
      }
    };

    fetchVersion();
  }, [cursoId, versionId]);

  // 🔹 Guardado de versión (se queda igual)
  const onSave = async (contenido, nota) => {
    const token = localStorage.getItem("id_token");
    const res = await fetch(
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
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.error || "Error al guardar versión");
    }
  };

  if (error) {
    return <div style={{ padding: "1rem", color: "red" }}>Error cargando versión: {error}</div>;
  }

  return (
    <EditorDeTemario_KNTR
      temarioInicial={temarioInicial}
      onSave={onSave}
      isLoading={isLoading}
    />
  );
}


// Component to handle conditional rendering of Sidebar and ChatModal
const Layout = ({ children, email, role }) => {
  const location = useLocation();
  const isBookEditor = location.pathname.startsWith('/book-editor');

  return (
    <div id="contenidoPrincipal" style={isBookEditor ? { paddingLeft: 0 } : {}}>
      {!isBookEditor && <Sidebar email={email} grupo={role} />}
      <ProfileModal />
      {!isBookEditor && <ChatModal />}

      <main className="main-content-area" style={isBookEditor ? { marginLeft: 0, width: '100%' } : {}}>
        {children}
      </main>

      {!isBookEditor && (
        <button id="logout" onClick={async () => {
          try {
            await signOut();
            window.location.reload();
          } catch (error) {
            console.error('Error signing out: ', error);
          }
        }}>
          Cerrar sesión
        </button>
      )}
    </div>
  );
};

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Imágenes para pantalla de inicio
  const logo = logoImg;
  const previewImg = previewImgSrc;
  const chileFlag = chileFlagImg;
  const peruFlag = peruFlagImg;
  const colombiaFlag = colombiaFlagImg;
  const mexicoFlag = mexicoFlagImg;
  const espanaFlag = espanaFlagImg;

  // ======== Autenticación Amplify ========
  useEffect(() => {
    // Escucha eventos de autenticación
    const hubListener = Hub.listen('auth', ({ payload }) => {
      console.log('Auth event:', payload.event);
      if (payload.event === 'signedIn' || payload.event === 'tokenRefresh') {
        checkAuthSession();
      } else if (payload.event === 'signedOut') {
        setUser(null);
        setLoading(false);
      }
    });

    // Si viene de OAuth (código en URL)
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    if (code) {
      console.log('OAuth code detected, clearing URL...');
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Verificar sesión actual
    checkAuthSession();

    return () => hubListener();
  }, []);

  const checkAuthSession = () => {
    fetchAuthSession()
      .then((session) => {
        const idToken = session.tokens?.idToken;
        const accessToken = session.tokens?.accessToken;
        if (!idToken || !accessToken) {
          throw new Error('No tokens available');
        }

        const attributes = idToken.payload;
        const groups = accessToken.payload['cognito:groups'] || [];
        console.log('Access Token payload:', JSON.stringify(accessToken.payload, null, 2));
        console.log('Groups found:', groups);

        // Guarda tokens localmente para otras llamadas (AdminPage, Sidebar)
        localStorage.setItem('id_token', idToken.toString());
        localStorage.setItem('access_token', accessToken.toString());

        setUser({ attributes, groups });
        setLoading(false);
      })
      .catch((err) => {
        console.log('No authenticated session:', err);
        setUser(null);
        setLoading(false);
      });
  };

  const handleLogout = () => {
    signOut();
  };

  // ======== Roles y permisos ========
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

  // ✅ Solo Anette o usuarios con rol "admin" pueden ver /admin
  const adminAllowed = email === 'anette.flores@netec.com.mx' || rol === 'admin';

  if (loading) {
    return <div>Loading...</div>;
  }

  // ======== Pantalla principal ========
  return (
    <>
      {!user ? (
        // === Pantalla de inicio (no autenticado) ===
        <div id="paginaInicio">
          <div className="header-bar">
            <img className="logo-left" src={logo} alt="Logo Netec" />
          </div>
          <div className="main-content">
            <div className="page-container">
              <div className="illustration-centered">
                <img src={previewImgSrc} alt="Ilustración" className="preview-image" />
              </div>
              <button
                className="login-button"
                onClick={() => {
                  signInWithRedirect({ provider: 'Cognito' });
                }}
              >
                🚀 Comenzar Ahora
              </button>

              <div className="country-flags">
                {[
                  { flag: chileFlagImg, label: 'Chile', url: 'https://www.netec.com/cursos-ti-chile' },
                  { flag: peruFlagImg, label: 'Perú', url: 'https://www.netec.com/cursos-ti-peru' },
                  { flag: colombiaFlagImg, label: 'Colombia', url: 'https://www.netec.com/cursos-ti-colombia' },
                  { flag: mexicoFlagImg, label: 'México', url: 'https://www.netec.com/cursos-ti-mexico' },
                  { flag: espanaFlagImg, label: 'España', url: 'https://www.netec.es/' }
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
        // === Aplicación principal (usuario autenticado) ===
        // === Aplicación principal (usuario autenticado) ===
        <Router>
          <Layout email={email} role={rol}>
            <Routes>
              <Route path="/" element={<Navigate to="/generador-contenidos" replace />} />
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

              <Route path="/presentaciones" element={<PresentacionesPage />} />
              <Route path="/presentaciones/viewer/:folder" element={<InfographicViewer />} />
              <Route path="/presentaciones/editor/:folder" element={<InfographicEditor />} />

              <Route path="/editor-seminario/:cursoId/:versionId" element={<EditorSeminarioPage />} />
              <Route path="/editor-temario/:cursoId/:versionId" element={<EditorTemarioPage />} />
              <Route path="/editor-practico/:cursoId/:versionId" element={<EditorPracticoPage />} />
              <Route path="/editor-KNTR/:cursoId/:versionId" element={<EditorKNTRPage />} />
              <Route path="/book-editor/:projectFolder" element={<BookEditorPage />} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Layout>
        </Router>
      )
      }
    </>
  );
}

export default App;
