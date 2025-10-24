import React, { useState, useEffect } from 'react'; // Se añade useEffect
import { fetchAuthSession } from "aws-amplify/auth"; // Se añade import
import EditorDeTemario from './EditorDeTemario'; 
import './GeneradorTemarios.css';

const asesoresComerciales = [
  "Alejandra Galvez",
  "Ana Aragón",
  "Arely Alvarez",
  "Benjamin Araya",
  "Carolina Aguilar",
  "Cristian Centeno",
  "Elizabeth Navia",
  "Eonice Garfías",
  "Guadalupe Agiz",
  "Jazmin Soriano",
  "Lezly Durán",
  "Lusdey Trujillo",
  "Natalia García",
  "Natalia Gomez",
  "Vianey Miranda",
].sort();


function GeneradorTemarios() {
  const [temarioGenerado, setTemarioGenerado] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

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

  // --- INICIA LÓGICA DEL MODAL ---
  const [userEmail, setUserEmail] = useState("");
  const [versiones, setVersiones] = useState([]);
  const [mostrarModal, setMostrarModal] = useState(false);
  const [filtros, setFiltros] = useState({ curso: "", asesor: "", tecnologia: "" });
  const [menuActivo, setMenuActivo] = useState(null);

  useEffect(() => {
    const getUser = async () => {
      try {
        const session = await fetchAuthSession();
        const email = session?.tokens?.idToken?.payload?.email;
        setUserEmail(email || "sin-correo");
      } catch (err) {
        console.error("⚠️ Error obteniendo usuario:", err);
      }
    };
    getUser();
  }, []);
  // --- TERMINA LÓGICA DEL MODAL ---


  const generarApiUrl = "https://h6ysn7u0tl.execute-api.us-east-1.amazonaws.com/dev2/PruebadeTEMAR";
  const guardarApiUrl = "https://wng2h5l0cd.execute-api.us-east-1.amazonaws.com/versiones";


  const handleParamChange = (e) => {
    const { name, value } = e.target;
    let valorFinal = value;
    if (name === 'horas_por_sesion' || name === 'numero_sesiones_por_semana') {
        valorFinal = parseInt(value, 10);
    }
    setParams(prev => ({ ...prev, [name]: valorFinal }));
  };

  const handleGenerar = async (nuevosParams = params) => {
    
    // Validación con campos opcionales
    if (!nuevosParams.tema_curso || !nuevosParams.tecnologia || !nuevosParams.sector) {
      setError("Por favor, completa todos los campos requeridos: Tecnología, Tema del Curso y Sector/Audiencia.");
      return;
    }

    setIsLoading(true);
    setError('');
    setTemarioGenerado(null);

    try {
      const payload = { ...nuevosParams };

      if (payload.objetivo_tipo !== 'certificacion') {
        delete payload.codigo_certificacion;
      }

      const token = localStorage.getItem("id_token");
      const response = await fetch(generarApiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();

      if (!response.ok) {
        const errorMessage = typeof data.error === 'object' ? JSON.stringify(data.error) : data.error;
        throw new Error(errorMessage || "Ocurrió un error en el servidor.");
      }
      
      const temarioCompleto = { ...data, ...nuevosParams };
      setTemarioGenerado(temarioCompleto);
      
    } catch (err) {
      console.error("Error al generar el temario:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Esta es tu función original para GUARDAR
  const handleSave = async (temarioParaGuardar, nota) => {
    const token = localStorage.getItem("id_token");
    try {
      const response = await fetch(guardarApiUrl, { // Usa la URL de guardado
        method: 'POST', // Método POST para guardar
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          // El body que tu API de guardado espera
          contenido: temarioParaGuardar, 
          nota: nota,
          // Añadimos los campos extra para el buscador
          autor: userEmail,
          asesor_comercial: params.asesor_comercial,
          nombre_preventa: params.nombre_preventa,
          nombre_curso: params.tema_curso,
          tecnologia: params.tecnologia,
          fecha_creacion: new Date().toISOString(),
        })
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || 'Error al guardar la versión.');
      }
      
      return { success: true, message: `Versión guardada ✔ (versionId: ${result.versionId})` };

    } catch (err) {
      console.error("Error en handleSave:", err);
      return { success: false, message: err.message };
    }
  };

  const horasTotales = params.horas_por_sesion * params.numero_sesiones_por_semana;


  // --- INICIAN FUNCIONES DEL MODAL ---
  const handleListarVersiones = async () => {
    try {
      const token = localStorage.getItem("id_token");
      // Ajuste: Usamos la 'guardarApiUrl' para el GET, asumiendo que es el mismo endpoint
      const res = await fetch(
        guardarApiUrl,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const data = await res.json();
      const sortedData = data.sort(
        (a, b) => new Date(b.fecha_creacion) - new Date(a.fecha_creacion)
      );
      setVersiones(sortedData);
      setMostrarModal(true); // Abre el modal
    } catch (error) {
      console.error("Error al obtener versiones:", error);
    }
  };

  const handleCargarVersion = (version) => {
    setMostrarModal(false); // Cierra el modal
    // Carga el contenido de la versión en el editor
    setTimeout(() => setTemarioGenerado(version.contenido), 300); 
  };

  const handleFiltroChange = (e) => {
    const { name, value } = e.target;
    setFiltros((prev) => ({ ...prev, [name]: value }));
  };

  const limpiarFiltros = () => {
    setFiltros({ curso: "", asesor: "", tecnologia: "" });
  };

  // Variable para filtrar versiones
  const versionesFiltradas = versiones.filter((v) => {
    // Manejo de 'v.nombre_curso' por si es undefined
    const nombreCurso = v.nombre_curso || '';
    const tecnologia = v.tecnologia || '';
    
    return (
      nombreCurso.toLowerCase().includes(filtros.curso.toLowerCase()) &&
      (filtros.asesor ? v.asesor_comercial === filtros.asesor : true) &&
      tecnologia.toLowerCase().includes(filtros.tecnologia.toLowerCase())
    );
  });
  // --- TERMINAN FUNCIONES DEL MODAL ---


  return (
    <div className="generador-temarios-container">
      <h2>Generador de Temarios a la Medida</h2>
      <p>Introduce los detalles para generar una propuesta de temario con Inteligencia artificial.</p>

      <div className="formulario-inicial">
        <div className="form-grid">
          <div className="form-group">
            <label>Nombre Preventa Asociado (Opcional)</label>
            <input name="nombre_preventa" value={params.nombre_preventa} onChange={handleParamChange} placeholder="Ej: Juan Pérez" />
          </div>
          <div className="form-group">
            <label>Asesor(a) Comercial Asociado (Opcional)</label>
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
          <div className="form-group">
            <label>Nivel de Dificultad</label>
            <select name="nivel_dificultad" value={params.nivel_dificultad} onChange={handleParamChange}>
              <option value="basico">Básico</option>
              <option value="intermedio">Intermedio</option>
              <option value="avanzado">Avanzado</option>
            </select>
          </div>
          <div className="form-group">
            <label>Número de Sesiones (1-7)</label>
            <div className='slider-container'>
              <input name="numero_sesiones_por_semana" type="range" min="1" max="7" value={params.numero_sesiones_por_semana} onChange={handleParamChange} />
              <span>{params.numero_sesiones_por_semana} {params.numero_sesiones_por_semana > 1 ? 'sesiones' : 'sesión'}</span>
            </div>
          </div>
          <div className="form-group">
            <label>Horas por Sesión (4-12)</label>
            <div className='slider-container'>
              <input name="horas_por_sesion" type="range" min="4" max="12" value={params.horas_por_sesion} onChange={handleParamChange} />
              <span>{params.horas_por_sesion} horas</span>
            </div>
          </div>

          <div className="form-group total-horas-display">
            <label>Total del Curso</label>
            <span className="horas-numero">{horasTotales} horas</span>
          </div>

        </div> {/* --- Fin del form-grid --- */}

        <div className="form-group">
          <label>Tipo de Objetivo</label>
          <div className="radio-group">
            <label>
              <input type="radio" name="objetivo_tipo" value="saber_hacer" checked={params.objetivo_tipo === 'saber_hacer'} onChange={handleParamChange} />
              Saber Hacer (Enfocado en habilidades)
            </label>
            <label>
              <input type="radio" name="objetivo_tipo" value="certificacion" checked={params.objetivo_tipo === 'certificacion'} onChange={handleParamChange} />
              Certificación (Enfocado en examen)
            </label>
          </div>
        </div>

        {params.objetivo_tipo === 'certificacion' && (
          <div className="form-group">
            <label>Código de Certificación</label>
            <input name="codigo_certificacion" value={params.codigo_certificacion} onChange={handleParamChange} placeholder="Ej: AWS CLF-C02, AZ-900" />
          </div>
        )}

        <div className="form-group">
          <label>Sector / Audiencia</label>
          <textarea name="sector" value={params.sector} onChange={handleParamChange} placeholder="Ej: Sector financiero, Desarrolladores con 1 año de experiencia..." />
        </div>
        <div className="form-group">
          <label>Enfoque Adicional (Opcional)</label>
          <textarea name="enfoque" value={params.enfoque} onChange={handleParamChange} placeholder="Ej: Orientado a patrones de diseño, con énfasis en casos prácticos" />
        </div>
        
        <div className="contenedor-botones">
          <button className="btn-generar-principal" onClick={() => handleGenerar(params)} disabled={isLoading}>
            {isLoading ? 'Generando...' : 'Generar Propuesta de Temario'} 
          </button>
          {/* Botón conectado a la nueva función */}
          <button type="button" className="btn-ver-versiones" onClick={handleListarVersiones} disabled={isLoading}>
            Ver Versiones Guardadas
          </button>
        </div>

      </div> {/* --- Fin del formulario-inicial --- */}

      {error && <div className="error-mensaje">{error}</div>}

      {temarioGenerado && (
        <EditorDeTemario
          temarioInicial={temarioGenerado}
          onRegenerate={handleGenerar}
          onSave={handleSave} // Se conecta al 'handleSave' original
          isLoading={isLoading}
        />
      )}
      
      {/* --- INICIA JSX DEL MODAL --- */}
      {mostrarModal && (
        <div className="modal-overlay" onClick={() => setMostrarModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📚 Versiones Guardadas</h3>
              <button className="modal-close" onClick={() => setMostrarModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="filtros-versiones">
                <input 
                  type="text" 
                  placeholder="Filtrar por curso" 
                  name="curso" 
                  value={filtros.curso} 
                  onChange={handleFiltroChange}
                />
                <select 
                  name="asesor" 
                  value={filtros.asesor} 
                  onChange={handleFiltroChange}
                >
                  <option value="">Todos los asesores</option>
                  {asesoresComerciales.map((a) => <option key={a}>{a}</option>)}
                </select>
                <input 
                  type="text" 
                  placeholder="Filtrar por tecnología" 
                  name="tecnologia" 
                  value={filtros.tecnologia} 
                  onChange={handleFiltroChange}
                />
                <button className="btn-secundario" onClick={limpiarFiltros}>
                  Limpiar
                </button>
              </div>

              {versionesFiltradas.length === 0 ? (
                <p className="no-versiones">No hay versiones guardadas.</p>
              ) : (
                <table className="tabla-versiones">
                  <thead>
                    <tr>
                      <th>Curso</th>
                      <th>Tecnología</th>
                      <th>Asesor</th>
                      <th>Fecha</th>
                      <th>Autor</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versionesFiltradas.map((v, i) => (
                      <tr key={v.versionId || i}> {/* Usar un ID único si está disponible */}
                        <td>{v.nombre_curso}</td>
                        <td>{v.tecnologia}</td>
                        <td>{v.asesor_comercial}</td>
                        <td>{new Date(v.fecha_creacion).toLocaleString()}</td>
                        <td>{v.autor}</td>
                        <td className="acciones-cell">
                          <button 
                            className="menu-btn" 
                            onClick={() => setMenuActivo(menuActivo === i ? null : i)}
                          >
                            ⋮
                          </button>
                          {menuActivo === i && (
                            <div className="menu-opciones">
                              {/* Llama a handleCargarVersion para cargar en el editor */}
                              <button onClick={() => handleCargarVersion(v)}> 
                                Editar
                              </button>
                              {/* Aquí irían "Exportar PDF", etc. */}
                            </div>
                          )}
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
      {/* --- TERMINA JSX DEL MODAL --- */}

    </div>
  );
}

export default GeneradorTemarios;