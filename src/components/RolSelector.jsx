// src/components/RolSelector.jsx

import React from 'react';
import './RolSelector.css'; // si prefieres separar estilos, aunque ya los tienes en app.css

function RolSelector({ onSelect }) {
  return (
    <div className="rol-selector-container">
      <h2>¿Cómo deseas ingresar?</h2>
      <button className="rol-selector-btn admin" onClick={() => onSelect('admin')}>
        Administrador
      </button>
      <button className="rol-selector-btn participant" onClick={() => onSelect('participant')}>
        Participante
      </button>
    </div>
  );
}

export default RolSelector;
