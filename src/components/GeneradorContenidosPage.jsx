// src/components/GeneradorContenidosPage.jsx (VERSIÓN MEJORADA + Botón de Versiones)
import React from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import './GeneradorContenidosPage.css';

// 👇 Importa el botón flotante de versiones
import BotonVersionesTemario from './BotonVersionesTemario';

function GeneradorContenidosPage() {
  const location = useLocation();
  const navigate = useNavigate();
  // Show menu by default, but hide it for "Generador de Cursos" AND "Editor de Libros" (Book Builder)
  const mostrarMenu = location.pathname.startsWith('/generador-contenidos')
    && !location.pathname.includes('/generador-cursos')
    && !location.pathname.includes('/book-builder');

  const handleRegresar = () => {
    navigate('/generador-contenidos'); // Navega de vuelta al menú principal
  };

  return (
    <div className="page-container-contenidos">
      {/* --- RENDERIZADO CONDICIONAL DEL MENÚ --- */}
      {mostrarMenu ? (
        <div className="menu-contenidos">

          <Link to="curso-estandar" className="opcion-menu">
            <div className="icono">📚</div>
            <div className="texto">
              <h3>Generador Temario Estándar</h3>
              <p>Genera aquí tu propuesta de temario</p>
            </div>
          </Link> {/* <-- CORRECCIÓN: La etiqueta <Link> ahora se cierra aquí --> */}

          <Link to="generador-cursos" className="opcion-menu">
            <div className="icono">🎓</div>
            <div className="texto">
              <h3>Generador de Cursos</h3>
              <p>Genera un curso completo a partir de tu temario</p>
            </div>
          </Link>

          <Link to="book-builder" className="opcion-menu">
            <div className="icono">📖</div>
            <div className="texto">
              <h3>Editor de Libros</h3>
              <p>Visualiza y edita las guías de estudiante</p>
            </div>
          </Link>

          <Link to="curso-KNTR" className="opcion-menu">
            <div className="icono">🦉</div>
            <div className="texto">
              <h3>Generador Temario Knowledge Transfer </h3>
              <p>Diseña un temario 100% teórico.</p>
            </div>
          </Link>

          <Link to="temario-practico" className="opcion-menu">
            <div className="icono">🛠️</div>
            <div className="texto">
              <h3>Generador Temario Taller Práctico</h3>
              <p>Crea un temario 100% enfocado en "hands-on labs" y ejercicios.</p>
            </div>
          </Link>

          <Link to="Temario-seminarios" className="opcion-menu">
            <div className="icono">👥</div>
            <div className="texto">
              <h3>Generador de Temario Seminarios</h3>
              <p>Diseña un temario para sesiones cortas, charlas,conferencias, divulgación.</p>
            </div>
          </Link>

          <Link to="plantilla-temario" className="opcion-menu">
            <div className="icono">📝</div>
            <div className="texto">
              <h3>Plantilla de Temario</h3>
              <p>
                Da formato Netec a un temario existente mediante una plantilla estandarizada, sin generación con IA.
              </p>
            </div>
          </Link>

          <Link to="/presentaciones" className="opcion-menu">
            <div className="icono">📊</div>
            <div className="texto">
              <h3>Presentaciones</h3>
              <p>Visualiza y edita tus presentaciones</p>
            </div>
          </Link>

          <div className="opcion-menu disabled">
            <div className="icono">💻</div>
            <div className="texto">
              <h3>Setup Guide (Próximamente)</h3>
              <p>Especificaciones de hardware y software necesarias para el ambiente de los participantes.</p>
            </div>
          </div>

          <Link to="faq" className="opcion-menu">
            <div className="icono">❓</div>
            <div className="texto">
              <h3>Centro de FAQs</h3>
              <p>Encuentra respuestas rápidas a las preguntas más comunes sobre la plataforma.</p>
            </div>
          </Link>

        </div>
      ) : (
        // Si no se muestra el menú, mostramos los botones de navegación con iconos
        <div className="nav-buttons-container">
          <button onClick={() => navigate('/')} className="nav-icon-btn" title="Inicio">
            🏠
          </button>
          <button onClick={handleRegresar} className="nav-icon-btn" title="Menú de contenidos">
            ←
          </button>
        </div>
      )}

      <div className="contenido-generador">
        <Outlet />
      </div>

      {location.pathname.includes('/curso-estandar') && (
        <BotonVersionesTemario
          apiBase={import.meta.env.VITE_GENERAR_TEMARIO_API_URL}
        />
      )}
    </div>
  );
}
export default GeneradorContenidosPage;