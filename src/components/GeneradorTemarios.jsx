// src/components/GeneradorTemarios.jsx
import React, { useState } from "react";
import EditorDeTemario from "./EditorDeTemario";
import "./GeneradorTemarios.css";

const API_BASE = import.meta.env.VITE_TEMARIOS_API || "";

function GeneradorTemarios() {
  const [tecnologia, setTecnologia] = useState("");
  const [temaCurso, setTemaCurso] = useState("");
  const [nivel, setNivel] = useState("Básico");
  const [nombrePreventa, setNombrePreventa] = useState("");
  const [asesorComercial, setAsesorComercial] = useState("");
  const [enfoque, setEnfoque] = useState("");
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [cargando, setCargando] = useState(false);

  // 🔹 Estados nuevos para las versiones guardadas
  const [versionesGuardadas, setVersionesGuardadas] = useState([]);
  const [mostrarModalVersiones, setMostrarModalVersiones] = useState(false);
  const [cargandoVersiones, setCargandoVersiones] = useState(false);

  // --- Generar nuevo temario ---
  const handleGenerarTemario = async () => {
    if (!nombrePreventa || !asesorComercial || !tecnologia || !temaCurso) {
      alert("Por favor completa todos los campos requeridos.");
      return;
    }

    setCargando(true);
    try {
      const response = await fetch(`${API_BASE}/PruebadeTEMAR`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tecnologia,
          tema_curso: temaCurso,
          nivel_dificultad: nivel.toLowerCase(),
          nombre_preventa: nombrePreventa,
          asesor_comercial: asesorComercial,
          enfoque,
        }),
      });

      const data = await response.json();
      if (data.success) {
        setTemarioGenerado(data.temario);
      } else {
        alert("No se pudo generar el temario.");
      }
    } catch (error) {
      console.error("❌ Error:", error);
      alert("Error al generar el temario.");
    } finally {
      setCargando(false);
    }
  };

  // --- Ver versiones guardadas (nuevo botón) ---
  const handleVerVersionesGuardadas = async () => {
    setCargandoVersiones(true);
    try {
      const response = await fetch(`${API_BASE}/obtener-temarios`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) throw new Error("Error al obtener versiones");

      const data = await response.json();
      setVersionesGuardadas(data.items || []);
      setMostrarModalVersiones(true);
    } catch (error) {
      console.error("❌ Error al obtener versiones:", error);
      alert("No se pudieron cargar las versiones guardadas.");
    } finally {
      setCargandoVersiones(false);
    }
  };

  // --- Guardar versión actual ---
  const handleGuardarTemario = async (temario, nota) => {
    try {
      const response = await fetch(`${API_BASE}/GuardarTemario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nombre_curso: temario.nombre_curso,
          tecnologia,
          nota_version: nota,
          temario_json: temario,
        }),
      });
      const data = await response.json();
      return data;
    } catch (error) {
      console.error("❌ Error al guardar:", error);
      return { success: false, message: "Error al guardar" };
    }
  };

  return (
    <div className="generador-container">
      <h2>Generador de Temarios a la Medida</h2>

      {!temarioGenerado && (
        <div className="formulario-temario">
          <div className="campo">
            <label>Nombre Preventa Asociado</label>
            <input
              value={nombrePreventa}
              onChange={(e) => setNombrePreventa(e.target.value)}
              placeholder="Ejemplo: Carolina Aguilar"
            />
          </div>

          <div className="campo">
            <label>Asesor(a) Comercial Asociado</label>
            <input
              value={asesorComercial}
              onChange={(e) => setAsesorComercial(e.target.value)}
              placeholder="Ejemplo: Natalia García"
            />
          </div>

          <div className="campo">
            <label>Tecnología</label>
            <input
              value={tecnologia}
              onChange={(e) => setTecnologia(e.target.value)}
              placeholder="Ejemplo: AWS, Azure, Python"
            />
          </div>

          <div className="campo">
            <label>Tema Principal del Curso</label>
            <input
              value={temaCurso}
              onChange={(e) => setTemaCurso(e.target.value)}
              placeholder="Ejemplo: Amazon CloudWatch"
            />
          </div>

          <div className="campo">
            <label>Nivel de Dificultad</label>
            <select value={nivel} onChange={(e) => setNivel(e.target.value)}>
              <option>Básico</option>
              <option>Intermedio</option>
              <option>Avanzado</option>
            </select>
          </div>

          <div className="campo">
            <label>Enfoque Adicional (Opcional)</label>
            <textarea
              value={enfoque}
              onChange={(e) => setEnfoque(e.target.value)}
              placeholder="Ejemplo: orientado a auditores"
            ></textarea>
          </div>

          <div className="acciones">
            <button
              className="btn-principal"
              onClick={handleGenerarTemario}
              disabled={cargando}
            >
              {cargando ? "Generando..." : "Generar Propuesta de Temario"}
            </button>

            {/* Botón nuevo */}
            <button
              className="btn-secundario"
              onClick={handleVerVersionesGuardadas}
              disabled={cargandoVersiones}
            >
              {cargandoVersiones ? "Cargando..." : "Ver Versiones Guardadas"}
            </button>
          </div>
        </div>
      )}

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onRegenerate={handleGenerarTemario}
          onSave={handleGuardarTemario}
          isLoading={cargando}
        />
      )}

      {/* ✅ Modal de versiones guardadas */}
      {mostrarModalVersiones && (
        <div className="modal-overlay" onClick={() => setMostrarModalVersiones(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📚 Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModalVersiones(false)}>✕</button>
            </div>
            <div className="modal-body">
              {versionesGuardadas.length === 0 ? (
                <p>No hay versiones guardadas todavía.</p>
              ) : (
                <table className="tabla-versiones">
                  <thead>
                    <tr>
                      <th>Curso</th>
                      <th>Tecnología</th>
                      <th>Fecha de Guardado</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {versionesGuardadas.map((v, i) => (
                      <tr key={i}>
                        <td>{v.nombre_curso}</td>
                        <td>{v.tecnologia}</td>
                        <td>{new Date(v.fecha_guardado).toLocaleString()}</td>
                        <td>
                          <button
                            className="btn-guardar"
                            onClick={() => {
                              const parsed = v.temario_json ? JSON.parse(v.temario_json) : v;
                              setTemarioGenerado(parsed);
                              setMostrarModalVersiones(false);
                            }}
                          >
                            Ver Detalles
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GeneradorTemarios;



