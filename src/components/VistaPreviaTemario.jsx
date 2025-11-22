// src/components/VistaPreviaTemario.jsx (VERSIÓN FINAL, ROBUSTA Y COMPLETA)

import React from 'react';
import './VistaPreviaTemario.css';

const renderWithLineBreaks = (text) => {
  if (typeof text !== 'string') return text;
  return text.split('<br/>').map((line, index, array) => (
    <React.Fragment key={index}>{line}{index < array.length - 1 && <br />}</React.Fragment>
  ));
};

function VistaPreviaTemario({ temario }) {
  if (!temario || Object.keys(temario).length === 0) {
    return <div className="temario-vista-previa"><p>No hay datos de temario para mostrar.</p></div>;
  }

  return (
    <div className="temario-vista-previa">
      <h1 className="curso-titulo">{temario.nombre_curso || "Nombre del Curso no Disponible"}</h1>
      <p className="version-tecnologia">Versión de la Tecnología: {temario.version_tecnologia || 'N/A'}</p>
      
      <ul className="info-lista">
        <li><strong>Horas Totales:</strong> {temario.horas_totales || 'N/A'}</li>
        <li><strong>Sesiones:</strong> {temario.numero_sesiones || 'N/A'}</li>
        <li><strong>Soporte (EOL):</strong> {temario.EOL || 'N/A'}</li>
        <li><strong>Distribución General:</strong> {temario.porcentaje_teoria_practica_general || 'N/A'}</li>
      </ul>

      <div className="descripcion-seccion">
        <h2>Descripción General</h2><p>{temario.descripcion_general || "N/A"}</p>
      </div>
      <div className="descripcion-seccion">
        <h2>Objetivos</h2>
        {Array.isArray(temario.objetivos) ? (
          <ul>
            {temario.objetivos.map((obj, i) => <li key={i}>{obj}</li>)}
          </ul>
        ) : temario.objetivos ? (
          <div style={{whiteSpace: 'pre-wrap'}}>{temario.objetivos}</div>
        ) : (
          <p>N/A</p>
        )}
      </div>
      <div className="descripcion-seccion">
        <h2>Audiencia</h2><p>{temario.audiencia || "N/A"}</p>
      </div>
      <div className="descripcion-seccion">
        <h2>Prerrequisitos</h2><p>{temario.prerrequisitos || "N/A"}</p>
      </div>

      <h2>Temario Detallado</h2>
      {Array.isArray(temario.temario) && temario.temario.map((cap, index) => (
        <div key={index} className="capitulo-container">
          <h3 className="capitulo-titulo">{cap?.capitulo || `Capítulo ${index + 1}`}</h3>
          <ul className="info-lista-capitulo">
            {cap?.tiempo_capitulo_min && <li><strong>Duración Estimada:</strong> {Math.floor(cap.tiempo_capitulo_min / 60)} horas ({cap.tiempo_capitulo_min} min)</li>}
            {cap?.porcentaje_teoria_practica_capitulo && <li><strong>Distribución:</strong> {cap.porcentaje_teoria_practica_capitulo}</li>}
          </ul>

          {cap?.objetivos_capitulo && (
            <div className="objetivos-capitulo-seccion">
              <h4>Objetivos del Capítulo</h4>
              {Array.isArray(cap.objetivos_capitulo) ? (
                <ul>
                  {cap.objetivos_capitulo.map((obj, i) => <li key={i}>{obj}</li>)}
                </ul>
              ) : (
                <div style={{whiteSpace: 'pre-wrap'}}>{cap.objetivos_capitulo}</div>
              )}
            </div>
          )}

          <table className="subcapitulos-tabla">
            <thead><tr><th>Tema</th><th>Sesión</th><th>Duración</th></tr></thead>
            <tbody>
              {Array.isArray(cap?.subcapitulos) && cap.subcapitulos.map((sub, subIndex) => {
                const nombreSub = typeof sub === 'object' ? sub.nombre : sub;
                const esPractico = typeof nombreSub === 'string' && (nombreSub.toLowerCase().includes('laboratorio') || nombreSub.toLowerCase().includes('caso práctico') || nombreSub.toLowerCase().includes('proyecto'));
                return (
                  <tr key={subIndex} className={esPractico ? 'subcapitulo-practico' : ''}>
                    <td>{renderWithLineBreaks(nombreSub || 'Subcapítulo sin nombre')}</td>
                    <td>{sub?.sesion || '-'}</td>
                    <td>{sub?.tiempo_subcapitulo_min ? `${sub.tiempo_subcapitulo_min} min` : '-'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {Array.isArray(cap?.ejercicios_practicos) && cap.ejercicios_practicos.length > 0 && (
            <div className="ejercicios-practicos-seccion">
              <h4>Ejercicios Prácticos Sugeridos</h4>
              <ul>
                {cap.ejercicios_practicos.map((ej, ejIndex) => <li key={ejIndex}>{ej}</li>)}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default VistaPreviaTemario;
