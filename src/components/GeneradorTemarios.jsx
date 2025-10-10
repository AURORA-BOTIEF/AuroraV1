import React, { useState } from 'react';
import EditorDeTemario from './EditorDeTemario';
import './GeneradorTemarios.css';

const asesoresComerciales = [
  "Alejandra Galvez", "Ana Aragón", "Arely Alvarez", "Benjamin Araya",
  "Carolina Aguilar", "Cristian Centeno", "Elizabeth Navia", "Eonice Garfías",
  "Guadalupe Agiz", "Jazmin Soriano", "Lezly Durán", "Lusdey Trujillo",
  "Natalia García", "Natalia Gomez", "Vianey Miranda",
].sort();

function GeneradorTemarios() {
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({
    tecnologia: '',
    asesor_comercial: '',
    nombre_curso: ''
  });

  const [params, setParams] = useState({
    nombre_preventa: '',
    asesor_comercial: '',
    tecnologia: '',
    tema_curso: '',
    nivel_dificultad: 'basico',
    sector: '',
    enfoque: '',
    horas_por_sesion: 7,
    numero_sesiones_por_semana: 1,
    objetivo_tipo: 'saber_hacer',
    codigo_certificacion: ''
  });

  const apiUrl = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones";

  const handleParamChange = (e) => {
    const { name, value } = e.target;
    let valorFinal = value;
    if (name === 'horas_por_sesion' || name === 'numero_sesiones_por_semana') {
      valorFinal = parseInt(value, 10);
    }
    setParams(prev => ({ ...prev, [name]: valorFinal }));
  };

  const handleGenerar = async (nuevosParams = params) => {
    if (!nuevosParams.nombre_preventa || !nuevosParams.asesor_comercial ||
        !nuevosParams.tema_curso || !nuevosParams.tecnologia || !nuevosParams.sector) {
      setError("Por favor completa todos los campos requeridos.");
      return;
    }

    setIsLoading(true);
    setError('');
    setTemarioGenerado(null);

    try {
      const payload = { ...nuevosParams };
      if (payload.objetivo_tipo !== 'certificacion') delete payload.codigo_certificacion;

      const token = localStorage.getItem("id_token");
      const response = await fetch("https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/PruebadeTEMAR", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Error al generar el temario.");

      const temarioCompleto = { ...data, ...nuevosParams };
      setTemarioGenerado(temarioCompleto);

    } catch (err) {
      console.error("Error al generar el temario:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async (temarioParaGuardar) => {
    try {
      const token = localStorage.getItem("id_token");
      const bodyData = {
        cursoId: temarioParaGuardar.tema_curso || params.tema_curso || "SinNombre",
        contenido: temarioParaGuardar,
        autor: token ? "anette.flores@netec.com.mx" : "Anónimo",
        asesor_comercial: params.asesor_comercial || "No asignado",
        nombre_preventa: params.nombre_preventa || "No especificado",
        nombre_curso: params.tema_curso || "Sin nombre",
        tecnologia: params.tecnologia || "No especificada",
        nota_version: `Guardado el ${new Date().toLocaleString()}`,
        fecha_creacion: new Date().toISOString(),
        s3_path: `s3://temarios/${(params.tema_curso || "SinNombre").replace(/\s+/g, "_")}_${new Date().toISOString()}.json`
      };

      const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(bodyData)
      });

      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || "Error al guardar la versión.");

      alert(`✅ Versión guardada correctamente\nVersion ID: ${data.versionId}`);
    } catch (error) {
      console.error("Error al guardar el temario:", error);
      alert("❌ No se pudo guardar el temario.");
    }
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros(prev => ({ ...prev, [name]: value }));
  };

  const handleListarVersiones = async () => {
    try {
      const token = localStorage.getItem("id_token");
      const response = await fetch(apiUrl, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        }
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Error al obtener versiones.");

      setVersiones(data);
      setMostrarModal(true);
    } catch (error) {
      console.error("Error al obtener versiones:", error);
      alert("❌ No se pudieron obtener las versiones.");
    }
  };

  const versionesFiltradas = versiones.filter(v =>
    (!filtros.tecnologia || v.tecnologia?.toLowerCase().includes(filtros.tecnologia.toLowerCase())) &&
    (!filtros.asesor_comercial || v.asesor_comercial === filtros.asesor_comercial) &&
    (!filtros.nombre_curso || v.nombre_curso?.toLowerCase().includes(filtros.nombre_curso.toLowerCase()))
  );

  return (
    <div className="generador-temarios-container">
      <h2>Generador de Temarios a la Medida</h2>
      <p>Introduce los detalles para generar una propuesta de temario con Inteligencia Artificial.</p>

      <div className="formulario-inicial">
        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado</label>
            <input name="nombre_preventa" value={params.nombre_preventa} onChange={handleParamChange} />
          </div>

          <div className="form-group">
            <label>Asesor(a) Comercial Asociado</label>
            <select name="asesor_comercial" value={params.asesor_comercial} onChange={handleParamChange}>
              <option value="">Selecciona un asesor(a)</option>
              {asesoresComerciales.map(nombre => (
                <option key={nombre} value={nombre}>{nombre}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Tecnología</label>
            <input name="tecnologia" value={params.tecnologia} onChange={handleParamChange} placeholder="Ej: AWS, React, Python" />
          </div>

          <div className="form-group">
            <label>Tema Principal del Curso</label>
            <input name="tema_curso" value={params.tema_curso} onChange={handleParamChange} placeholder="Ej: Arquitecturas Serverless" />
          </div>
        </div>

        <div style={{ display: "flex", gap: "1rem" }}>
          <button className="btn-generar-principal" onClick={() => handleGenerar(params)} disabled={isLoading}>
            {isLoading ? 'Generando...' : 'Generar Propuesta de Temario'}
          </button>

          <button className="btn-generar-principal" style={{ backgroundColor: "#45ab9f" }} onClick={handleListarVersiones}>
            Ver Versiones Guardadas
          </button>
        </div>
      </div>

      {error && <div className="error-mensaje">{error}</div>}

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onRegenerate={handleGenerar}
          onSave={handleSave}
          isLoading={isLoading}
        />
      )}

      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📚 Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModal(false)}>✕</button>
            </div>

            <div className="modal-body">
              <div className="filtros-versiones">
                <input type="text" name="tecnologia" placeholder="Filtrar por tecnología..." value={filtros.tecnologia} onChange={handleFiltroChange} />
                <select name="asesor_comercial" value={filtros.asesor_comercial} onChange={handleFiltroChange}>
                  <option value="">Todos los asesores</option>
                  {asesoresComerciales.map(nombre => (
                    <option key={nombre} value={nombre}>{nombre}</option>
                  ))}
                </select>
                <input type="text" name="nombre_curso" placeholder="Buscar curso..." value={filtros.nombre_curso} onChange={handleFiltroChange} />
                <button className="btn-lupa" title="Buscar" onClick={handleListarVersiones}>🔍</button>
              </div>

              {versionesFiltradas.length === 0 ? (
                <p>No hay versiones guardadas todavía.</p>
              ) : (
                <table className="tabla-versiones">
                  <thead>
                    <tr>
                      <th>Curso</th>
                      <th>Tecnología</th>
                      <th>Asesor</th>
                      <th>Fecha</th>
                      <th>Autor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versionesFiltradas.map((v, i) => (
                      <tr key={i}>
                        <td>{v.nombre_curso}</td>
                        <td>{v.tecnologia}</td>
                        <td>{v.asesor_comercial}</td>
                        <td>{v.fecha_creacion ? new Date(v.fecha_creacion).toLocaleString("es-MX") : "Sin fecha"}</td>
                        <td>{v.autor}</td>
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






