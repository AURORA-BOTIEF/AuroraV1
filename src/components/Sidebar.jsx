// src/components/Sidebar.jsx (CÓDIGO FINAL Y COMPLETO)
//x
import { Link } from 'react-router-dom';
import './Sidebar.css';
import defaultFoto from '../assets/default.jpg';

function Sidebar({ email }) {
  console.log("📧 Email en Sidebar:", email);
  return (
    // Añadimos la clase 'sidebar' para que los estilos de index.css se apliquen
    <div id="barraLateral" className="sidebar"> 
      <div id="perfilSidebar">
        <img id="fotoPerfilSidebar" src={defaultFoto} alt="Foto perfil" />
        <div className="nombre" id="nombreSidebar">Usuario</div>
        <div className="email" id="emailSidebar">{email}</div>
      </div>

      <div id="caminito">
        {/* Módulos (se mantiene sin cambios) */}
        <div className="step">
          <div className="circle">🧠</div>
          <span>Módulos</span>
        </div>

        {/* ACTIVIDADES: Ahora es un Link de navegación */}
        <Link to="/actividades" className="nav-link">
          <div className="step" style={{ cursor: 'pointer' }}>
            <div className="circle">📘</div>
            <span>Actividades</span>
          </div>
        </Link>

        {/* Examen (se mantiene sin cambios) */}
        <div className="step">
          <div className="circle">🔬</div>
          <span>Examen</span>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
