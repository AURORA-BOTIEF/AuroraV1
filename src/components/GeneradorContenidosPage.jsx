// src/components/GeneradorContenidosPage.jsx (VERSIÓN MEJORADA + Botón de Versiones)
import React from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import './GeneradorContenidosPage.css';

// 👇 Importa el botón flotante de versiones
import BotonVersionesTemario from './BotonVersionesTemario';

function GeneradorContenidosPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const mostrarMenu = location.pathname === '/generador-contenidos';

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
              <h3>Generador Temario Estándar o Aumentado </h3>
              <p>Genera aquí tu propuesta de temario</p>
            </div>
          </Link> {/* <-- CORRECCIÓN: La etiqueta <Link> ahora se cierra aquí --> */}

          <Link to="generador-cursos" className="opcion-menu">
            <div className="icono">🎓</div>
            <div className="texto">
              <h3>Generador de Cursos</h3>
              <p>Sube outline y genera lecciones con CrewAI</p>
            </div>
          </Link>

          <Link to="book-builder" className="opcion-menu">
            <div className="icono">📖</div>
            <div className="texto">
              <h3>Editor de Libros</h3>
              <p>Visualiza y edita libros completos con texto e imágenes</p>
            </div>
          </Link>

          <div className="opcion-menu disabled">
            <div className="icono">🛠️</div>
            <div className="texto">
              <h3>Generador Temario Taller Práctico</h3>
              <p>Crea un temario 100% enfocado en "hands-on labs" y ejercicios.</p>
            </div>
          </div>

          <div className="opcion-menu disabled">
            <div className="icono">👥</div>
            <div className="texto">
              <h3>Generador de Temario Sem</h3>
              <p>Diseña un temario para sesiones cortas, charlas,conferencias, divulgación.</p>
            </div>
          </div>

          <div className="opcion-menu disabled">
            <div className="icono">🧪</div>
            <div className="texto">
              <h3>Laboratorios (Próximamente)</h3>
              <p>Realiza aquí tu guía de laboratorios.</p>
            </div>
          </div>

          <div className="opcion-menu disabled">
            <div className="icono">📊</div>
            <div className="texto">
              <h3>Presentación (Próximamente)</h3>
              <p>Realiza aquí la PPT del curso.</p>
            </div>
          </div>

          <div className="opcion-menu disabled">
            <div className="icono">💻</div>
            <div className="texto">
              <h3>Setup Guide (Próximamente)</h3>
              <p>Especificaciones de hardware y software necesarias para el ambiente de los participantes.</p>
            </div>
          </div>

        </div>
      ) : (
        // Si no se muestra el menú, mostramos el botón de regresar
        <button onClick={handleRegresar} className="btn-regresar-menu">
          &larr; Volver al menú de contenidos
        </button>
      )}

      <div className="contenido-generador">
        <Outlet />
      </div>

      <BotonVersionesTemario
        apiBase="https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2"
      />
    </div>
  );
}
export default GeneradorContenidosPage;