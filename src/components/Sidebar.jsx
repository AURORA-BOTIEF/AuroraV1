import './Sidebar.css';
import defaultFoto from '../assets/default.jpg';

function Sidebar({ onOpenActividades }) {
  return (
    <div id="barraLateral">
      <div id="perfilSidebar">
        <img id="fotoPerfilSidebar" src={defaultFoto} alt="Foto perfil" />
        <div className="nombre" id="nombreSidebar">Usuario</div>
        <div className="email" id="emailSidebar">usuario@ejemplo.com</div>
      </div>

      <div id="caminito">
        {/* Módulos (sin navegación por ahora) */}
        <div className="step">
          <div className="circle">🧠</div>
          <span>Módulos</span>
        </div>

        {/* ACTIVIDADES: Abre modal */}
        <div className="step" onClick={onOpenActividades} style={{ cursor: 'pointer' }}>
          <div className="circle">📘</div>
          <span>Actividades</span>
        </div>

        {/* Examen (también sin navegación por ahora) */}
        <div className="step">
          <div className="circle">🔬</div>
          <span>Examen</span>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
