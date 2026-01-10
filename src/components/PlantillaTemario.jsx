import React, { useState } from "react";
import jsPDF from "jspdf";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";

import "./PlantillaTemario.css"; // ✅ CSS propio
import { Plus, Trash2, Save, Eye, X } from "lucide-react";

// ================== CONFIG ==================
const API_BASE = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com";
const ENDPOINT_GUARDAR = `${API_BASE}/versiones/customtemarios`;   // POST (guardar)
const ENDPOINT_VERSIONES = `${API_BASE}/versiones/customtemarios`; // GET  (listar) ✅ CORRECTO

// ================== Utils ==================
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

const formatFecha = (iso) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

// ================== Base ==================
const plantillaBase = {
  nombre_curso: "",
  descripcion_general: "",
  audiencia: "",
  prerrequisitos: "",
  objetivos: "",
  horas_total_curso: 0,
  notas_generales: "",
  temario: [],
};

export default function PlantillaTemario() {
  const [temario, setTemario] = useState(plantillaBase);

  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  // Guardar
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [saveError, setSaveError] = useState("");

  // Versiones
  const [modalVersiones, setModalVersiones] = useState(false);
  const [loadingVersiones, setLoadingVersiones] = useState(false);
  const [versiones, setVersiones] = useState([]);
  const [versionesError, setVersionesError] = useState("");

  // ================== EDICIÓN ==================
  const handleFieldChange = (cap, sub, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));

    if (sub === null) {
      nuevo.temario[cap][field] = value;
    } else {
      nuevo.temario[cap].subcapitulos[sub][field] = value;
    }

    nuevo.temario[cap].tiempo_capitulo_min =
      nuevo.temario[cap].subcapitulos.reduce(
        (acc, s) => acc + (parseInt(s.tiempo_subcapitulo_min) || 0),
        0
      );

    setTemario(nuevo);
  };

  // ================== CAPÍTULOS ==================
  const agregarCapitulo = () =>
    setTemario({
      ...temario,
      temario: [
        ...temario.temario,
        {
          capitulo: `Nuevo capítulo ${temario.temario.length + 1}`,
          tiempo_capitulo_min: 0,
          objetivos_capitulo: "",
          notas_capitulo: "",
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

  // ================== TEMAS ==================
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

  // ================== AJUSTAR TIEMPOS ==================
  const ajustarTiempos = () => {
    const totalMin = (parseFloat(temario.horas_total_curso) || 0) * 60;
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

  // ================== GUARDAR EN BD ==================
  const guardarEnBD = async () => {
    setSaveMsg("");
    setSaveError("");

    if (!temario.nombre_curso || !temario.nombre_curso.trim()) {
      setSaveError("El nombre del curso es obligatorio");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(ENDPOINT_GUARDAR, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...temario, source: "plantilla-temario" }),
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.message || `Error HTTP ${res.status}`);

      // soporta proxy response o directo
      let temarioId = data?.temarioId;
      if (!temarioId && data?.body) {
        try {
          const parsed = typeof data.body === "string" ? JSON.parse(data.body) : data.body;
          temarioId = parsed?.temarioId;
        } catch {}
      }

      setSaveMsg(temarioId ? `✅ Guardado correctamente (ID: ${temarioId})` : "✅ Guardado correctamente");
    } catch (e) {
      setSaveError(`❌ ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  // ================== CARGAR VERSIONES (GET) ==================
  const cargarVersiones = async () => {
    setLoadingVersiones(true);
    setVersionesError("");
    try {
      const res = await fetch(ENDPOINT_VERSIONES, { method: "GET" });

      const data = await res.json().catch(() => ({}));

      // soporta: array directo o proxy { body: "[]" }
      const list =
        data?.body && typeof data.body === "string"
          ? JSON.parse(data.body)
          : Array.isArray(data)
          ? data
          : [];

      setVersiones(Array.isArray(list) ? list : []);
    } catch (e) {
      console.error("Error versiones:", e);
      setVersiones([]);
      setVersionesError("No se pudieron cargar las versiones.");
    } finally {
      setLoadingVersiones(false);
    }
  };

  // ================== EXPORTAR PDF ==================
  const exportarPDF = async () => {
    if (!temario.temario.length) return alert("No hay contenido");

    const doc = new jsPDF({ unit: "pt", format: "letter" });
    const azul = "#005A9C";
    const negro = "#000000";
    const pageW = doc.internal.pageSize.getWidth();
    const pageH = doc.internal.pageSize.getHeight();
    const margin = { top: 230, bottom: 100, left: 60, right: 60 };
    const contentW = pageW - margin.left - margin.right;

    const enc = await toDataURL(encabezadoImagen);
    const pie = await toDataURL(pieDePaginaImagen);

    let y = margin.top;
    const addPageIfNeeded = (extra = 40) => {
      if (y + extra > pageH - margin.bottom) {
        doc.addPage();
        y = margin.top;
      }
    };

    doc.setFont("helvetica", "bold");
    doc.setFontSize(22);
    doc.setTextColor(azul);
    doc.text(temario.nombre_curso || "Temario", pageW / 2, y, { align: "center" });
    y += 30;

    const secciones = [
      { titulo: "Descripción General", texto: temario.descripcion_general },
      { titulo: "Audiencia", texto: temario.audiencia },
      { titulo: "Prerrequisitos", texto: temario.prerrequisitos },
      { titulo: "Objetivos", texto: temario.objetivos },
      { titulo: "Notas", texto: temario.notas_generales },
    ];

    secciones.forEach((s) => {
      if (!s.texto) return;
      addPageIfNeeded(60);

      doc.setFont("helvetica", "bold");
      doc.setFontSize(14);
      doc.setTextColor(azul);
      doc.text(s.titulo, margin.left, y);
      y += 18;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(11);
      doc.setTextColor(negro);

      doc.splitTextToSize(s.texto, contentW).forEach((line) => {
        addPageIfNeeded(14);
        doc.text(line, margin.left, y);
        y += 14;
      });

      y += 10;
    });

    addPageIfNeeded(60);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(18);
    doc.setTextColor(azul);
    doc.text("Temario", margin.left, y);
    y += 25;

    temario.temario.forEach((cap, i) => {
      addPageIfNeeded(60);

      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.setTextColor(azul);
      doc.text(`Capítulo ${i + 1}: ${cap.capitulo}`, margin.left, y);
      y += 14;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.setTextColor(negro);
      doc.text(`Duración total: ${formatDuration(cap.tiempo_capitulo_min)}`, margin.left + 10, y);
      y += 14;

      cap.subcapitulos.forEach((sub, j) => {
        addPageIfNeeded(14);
        doc.setFontSize(10);
        doc.text(`${i + 1}.${j + 1} ${sub.nombre}`, margin.left + 25, y);
        doc.text(
          `${formatDuration(sub.tiempo_subcapitulo_min)} • Sesión ${sub.sesion || 1}`,
          pageW - margin.right,
          y,
          { align: "right" }
        );
        y += 12;
      });

      y += 12;
    });

    const totalPages = doc.internal.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.addImage(enc, "PNG", 0, 0, pageW, 200);
      doc.addImage(pie, "PNG", 0, pageH - 80, pageW, 80);
      doc.text(`Página ${i} de ${totalPages}`, pageW / 2, pageH - 55, { align: "center" });
    }

    doc.save(`Temario_${slugify(temario.nombre_curso)}.pdf`);
  };

  // ================== RENDER ==================
  return (
    <div className="pt-container">
      <h2 className="pt-title">Plantilla de Temario</h2>

      <label>Nombre del curso</label>
      <input
        value={temario.nombre_curso}
        onChange={(e) => setTemario({ ...temario, nombre_curso: e.target.value })}
        className="input-capitulo"
      />

      <label>Duración total (horas)</label>
      <input
        type="number"
        value={temario.horas_total_curso}
        onChange={(e) => setTemario({ ...temario, horas_total_curso: e.target.value })}
        className="input-capitulo"
      />

      <hr style={{ margin: "20px 0" }} />
      <h3>Información general del curso</h3>

      <label>Descripción General</label>
      <textarea
        value={temario.descripcion_general}
        onChange={(e) => setTemario({ ...temario, descripcion_general: e.target.value })}
        className="textarea-objetivos-capitulo"
      />

      <label>Audiencia</label>
      <textarea
        value={temario.audiencia}
        onChange={(e) => setTemario({ ...temario, audiencia: e.target.value })}
        className="textarea-objetivos-capitulo"
      />

      <label>Prerrequisitos</label>
      <textarea
        value={temario.prerrequisitos}
        onChange={(e) => setTemario({ ...temario, prerrequisitos: e.target.value })}
        className="textarea-objetivos-capitulo"
      />

      <label>Objetivos</label>
      <textarea
        value={temario.objetivos}
        onChange={(e) => setTemario({ ...temario, objetivos: e.target.value })}
        className="textarea-objetivos-capitulo"
      />

      <label>Notas (generales)</label>
      <textarea
        value={temario.notas_generales}
        onChange={(e) => setTemario({ ...temario, notas_generales: e.target.value })}
        className="textarea-objetivos-capitulo"
        placeholder="Notas internas para preventa / instructores / ajustes..."
      />

      <hr />

      {temario.temario.map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <input
            value={cap.capitulo}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
          />

          <div className="duracion-total">⏱️ {formatDuration(cap.tiempo_capitulo_min)}</div>

          {cap.subcapitulos.map((sub, j) => (
            <div key={j} className="subcapitulo-item">
              <input value={sub.nombre} onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)} />
              <input
                type="number"
                value={sub.tiempo_subcapitulo_min}
                onChange={(e) => handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)}
                placeholder="min"
              />
              <input
                type="number"
                min="1"
                value={sub.sesion || 1}
                onChange={(e) => handleFieldChange(i, j, "sesion", parseInt(e.target.value, 10) || 1)}
                placeholder="sesión"
                className="input-sesion"
              />
              <button className="btn-eliminar-tema" onClick={() => eliminarTema(i, j)}>
                <Trash2 size={16} />
              </button>
            </div>
          ))}

          <div className="acciones-capitulo">
            <button className="btn-agregar-tema" onClick={() => agregarTema(i)}>
              <Plus size={16} /> Agregar tema
            </button>

            <button className="btn-eliminar-capitulo" onClick={() => eliminarCapitulo(i)}>
              <Trash2 size={16} /> Eliminar capítulo
            </button>
          </div>
        </div>
      ))}

      <div className="btn-agregar-capitulo-container">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
          <Plus size={18} /> Agregar capítulo
        </button>
      </div>

      {/* Footer */}
      <div className="pt-footer">
        <button className="btn-primario" onClick={ajustarTiempos}>
          Ajustar tiempos
        </button>

        <button className="btn-primario" onClick={guardarEnBD} disabled={saving}>
          <Save size={16} style={{ marginRight: 6 }} />
          {saving ? "Guardando..." : "Guardar"}
        </button>

        <button className="btn-secundario" onClick={() => setModalExportar(true)}>
          Exportar
        </button>

        <button
          className="btn-secundario"
          onClick={() => {
            setModalVersiones(true);
            cargarVersiones();
          }}
        >
          <Eye size={16} style={{ marginRight: 6 }} />
          Ver versiones
        </button>
      </div>

      {saveMsg && <p className="pt-ok">{saveMsg}</p>}
      {saveError && <p className="pt-err">{saveError}</p>}

      {/* Modal Exportar */}
      {modalExportar && (
        <div className="modal-overlay" onClick={() => setModalExportar(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Exportar</h3>
            <label>
              <input type="radio" checked={exportTipo === "pdf"} onChange={() => setExportTipo("pdf")} /> PDF
            </label>
            <label>
              <input type="radio" checked={exportTipo === "excel"} onChange={() => setExportTipo("excel")} /> Excel
            </label>

            <button
              className="btn-guardar"
              onClick={() => {
                exportTipo === "pdf" ? exportarPDF() : downloadExcelTemario(temario);
                setModalExportar(false);
              }}
            >
              Exportar {exportTipo.toUpperCase()}
            </button>
          </div>
        </div>
      )}

      {/* Modal Versiones */}
      {modalVersiones && (
        <div className="modal-overlay" onClick={() => setModalVersiones(false)}>
          <div className="pt-modal" onClick={(e) => e.stopPropagation()}>
            <div className="pt-modal-header">
              <h3>Versiones Guardadas</h3>
              <button className="pt-modal-close" onClick={() => setModalVersiones(false)}>
                <X />
              </button>
            </div>

            <div className="pt-modal-body">
              {loadingVersiones ? (
                <p>Cargando...</p>
              ) : versionesError ? (
                <p className="pt-err">{versionesError}</p>
              ) : versiones.length === 0 ? (
                <p>No hay versiones guardadas.</p>
              ) : (
                <div className="pt-table-wrap">
                  <table className="pt-table">
                    <thead>
                      <tr>
                        <th>Curso</th>
                        <th>Audiencia</th>
                        <th>Fecha</th>
                        <th>Autor</th>
                        <th>Notas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {versiones.map((v, idx) => (
                        <tr key={v.temarioId || idx}>
                          <td>{v.nombre_curso || ""}</td>
                          <td>{v.audiencia || ""}</td>
                          <td>{formatFecha(v.createdAt)}</td>
                          <td>{v.createdBy || ""}</td>
                          <td className="pt-notas">{v.notas_generales || ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
