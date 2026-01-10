import React, { useEffect, useState } from "react";
import jsPDF from "jspdf";
import { Plus, Trash2, Save, Eye, X } from "lucide-react";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";
import "./EditorDeTemario_Practico.css";

/* ================== Utils ================== */
const formatDuration = (minutos) => {
  if (!minutos || minutos < 0) return "0 min";
  const horas = Math.floor(minutos / 60);
  const mins = minutos % 60;
  if (horas === 0) return `${mins} min`;
  if (mins === 0) return `${horas} hr`;
  return `${horas} hr ${mins} min`;
};

const toDataURL = async (url) => {
  const res = await fetch(url);
  const blob = await res.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
};

const slugify = (str = "") =>
  String(str)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "temario";

/* ================== Base ================== */
const plantillaBase = {
  nombre_curso: "",
  descripcion_general: "",
  audiencia: "",
  prerrequisitos: "",
  objetivos: "",
  notas: "",
  horas_total_curso: 0,
  temario: [],
};

/* ================== Component ================== */
export default function PlantillaTemario() {
  const [temario, setTemario] = useState(plantillaBase);

  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [saveError, setSaveError] = useState("");

  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  const [modalVersiones, setModalVersiones] = useState(false);
  const [versiones, setVersiones] = useState([]);
  const [loadingVersiones, setLoadingVersiones] = useState(false);

  const API_BASE = "https://TU_API_ID.execute-api.us-east-1.amazonaws.com";

  /* ================== Guardar ================== */
  const guardarEnBD = async () => {
    if (!temario.nombre_curso.trim()) {
      setSaveError("El nombre del curso es obligatorio");
      return;
    }

    setSaving(true);
    setSaveMsg("");
    setSaveError("");

    try {
      const res = await fetch(`${API_BASE}/customtemarios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ temario }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data?.message || "Error al guardar");

      const parsed =
        typeof data.body === "string" ? JSON.parse(data.body) : data.body;

      setSaveMsg(`Guardado correctamente (ID: ${parsed?.temarioId || "OK"})`);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  };

  /* ================== Versiones ================== */
  const cargarVersiones = async () => {
    setLoadingVersiones(true);
    try {
      const res = await fetch(`${API_BASE}/versiones`);
      const data = await res.json();
      setVersiones(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Error versiones", e);
    } finally {
      setLoadingVersiones(false);
    }
  };

  /* ================== Editor ================== */
  const handleFieldChange = (cap, sub, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (sub === null) nuevo.temario[cap][field] = value;
    else nuevo.temario[cap].subcapitulos[sub][field] = value;

    nuevo.temario[cap].tiempo_capitulo_min =
      nuevo.temario[cap].subcapitulos.reduce(
        (acc, s) => acc + (parseInt(s.tiempo_subcapitulo_min) || 0),
        0
      );
    setTemario(nuevo);
  };

  const agregarCapitulo = () =>
    setTemario({
      ...temario,
      temario: [
        ...temario.temario,
        {
          capitulo: `Nuevo capítulo ${temario.temario.length + 1}`,
          tiempo_capitulo_min: 0,
          subcapitulos: [
            { nombre: "Nuevo tema", tiempo_subcapitulo_min: 30, sesion: 1 },
          ],
        },
      ],
    });

  const eliminarCapitulo = (i) => {
    if (!window.confirm("¿Eliminar capítulo?")) return;
    const nuevo = [...temario.temario];
    nuevo.splice(i, 1);
    setTemario({ ...temario, temario: nuevo });
  };

  const agregarTema = (i) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario[i].subcapitulos.push({
      nombre: "Nuevo tema",
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  const eliminarTema = (i, j) => {
    if (!window.confirm("¿Eliminar tema?")) return;
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario[i].subcapitulos.splice(j, 1);
    setTemario(nuevo);
  };

  const ajustarTiempos = () => {
    const totalMin = temario.horas_total_curso * 60;
    const totalTemas = temario.temario.reduce(
      (a, c) => a + c.subcapitulos.length,
      0
    );
    if (!totalTemas) return;
    const porTema = Math.floor(totalMin / totalTemas);
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.forEach((c) => {
      c.subcapitulos.forEach((s) => (s.tiempo_subcapitulo_min = porTema));
      c.tiempo_capitulo_min = porTema * c.subcapitulos.length;
    });
    setTemario(nuevo);
  };

  /* ================== Render ================== */
  return (
    <div className="temario-editor-container">
      <h2>Plantilla de Temario</h2>

      <label>Nombre del curso</label>
      <input
        value={temario.nombre_curso}
        onChange={(e) =>
          setTemario({ ...temario, nombre_curso: e.target.value })
        }
      />

      <label>Duración total (horas)</label>
      <input
        type="number"
        value={temario.horas_total_curso}
        onChange={(e) =>
          setTemario({ ...temario, horas_total_curso: e.target.value })
        }
      />

      <h3>Información general del curso</h3>

      <textarea
        placeholder="Descripción general"
        value={temario.descripcion_general}
        onChange={(e) =>
          setTemario({ ...temario, descripcion_general: e.target.value })
        }
      />
      <textarea
        placeholder="Audiencia"
        value={temario.audiencia}
        onChange={(e) => setTemario({ ...temario, audiencia: e.target.value })}
      />
      <textarea
        placeholder="Prerrequisitos"
        value={temario.prerrequisitos}
        onChange={(e) =>
          setTemario({ ...temario, prerrequisitos: e.target.value })
        }
      />
      <textarea
        placeholder="Objetivos"
        value={temario.objetivos}
        onChange={(e) => setTemario({ ...temario, objetivos: e.target.value })}
      />
      <textarea
        placeholder="Notas internas"
        value={temario.notas}
        onChange={(e) => setTemario({ ...temario, notas: e.target.value })}
      />

      {temario.temario.map((cap, i) => (
        <div key={i}>
          <input
            value={cap.capitulo}
            onChange={(e) =>
              handleFieldChange(i, null, "capitulo", e.target.value)
            }
          />
          {cap.subcapitulos.map((sub, j) => (
            <div key={j}>
              <input
                value={sub.nombre}
                onChange={(e) =>
                  handleFieldChange(i, j, "nombre", e.target.value)
                }
              />
              <input
                type="number"
                value={sub.tiempo_subcapitulo_min}
                onChange={(e) =>
                  handleFieldChange(
                    i,
                    j,
                    "tiempo_subcapitulo_min",
                    e.target.value
                  )
                }
              />
              <button onClick={() => eliminarTema(i, j)}>
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          <button onClick={() => agregarTema(i)}>+ Tema</button>
          <button onClick={() => eliminarCapitulo(i)}>Eliminar capítulo</button>
        </div>
      ))}

      <button onClick={agregarCapitulo}>
        <Plus size={16} /> Agregar capítulo
      </button>

      {/* ===== Footer ===== */}
      <div className="acciones-footer" style={{ display: "flex", gap: 10 }}>
        <button onClick={ajustarTiempos}>Ajustar tiempos</button>
        <button onClick={guardarEnBD} disabled={saving}>
          <Save size={16} /> Guardar
        </button>
        <button onClick={() => setModalExportar(true)}>Exportar</button>
        <button
          onClick={() => {
            setModalVersiones(true);
            cargarVersiones();
          }}
        >
          <Eye size={16} /> Ver versiones
        </button>
      </div>

      {saveMsg && <p style={{ color: "green" }}>{saveMsg}</p>}
      {saveError && <p style={{ color: "red" }}>{saveError}</p>}

      {/* ===== Modal Versiones ===== */}
      {modalVersiones && (
        <div className="modal-overlay">
          <div className="modal large">
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <h3>Versiones Guardadas</h3>
              <X onClick={() => setModalVersiones(false)} />
            </div>

            {loadingVersiones ? (
              <p>Cargando...</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Curso</th>
                    <th>Tecnología</th>
                    <th>Asesor</th>
                    <th>Fecha</th>
                    <th>Autor</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {versiones.map((v, i) => (
                    <tr key={i}>
                      <td>{v.curso}</td>
                      <td>{v.tecnologia}</td>
                      <td>{v.asesor}</td>
                      <td>{v.fecha}</td>
                      <td>{v.autor}</td>
                      <td>{v.notas}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
