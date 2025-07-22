import { Link } from 'react-router-dom';
import './Sidebar.css';
import defaultFoto from '../assets/default.jpg';

function Sidebar({ email, nombre, grupo }) {
  return (
    <div id="barraLateral" className="sidebar">
      <div id="perfilSidebar">
        <img id="fotoPerfilSidebar" src={defaultFoto} alt="Foto perfil" />
        <div className="nombre" id="nombreSidebar">{nombre || 'Usuario conectado'}</div>
        <div className="email" id="emailSidebar">{email}</div>
        <div className="grupo" id="grupoSidebar">🎖️ Rol: {grupo || 'Sin grupo'}</div>
      </div>

      <div id="caminito">
        {/* Módulos */}
        <div className="step">
          <div className="circle">🧠</div>
          <span>Módulos</span>
        </div>

        {/* Actividades (navegable) */}
        <Link to="/actividades" className="nav-link">
          <div className="step" style={{ cursor: 'pointer' }}>
            <div className="circle">📘</div>
            <span>Actividades</span>
          </div>
        </Link>

        {/* Examen */}
        <div className="step">
          <div className="circle">🔬</div>
          <span>Examen</span>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
