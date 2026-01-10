import React, { useState } from "react";
import jsPDF from "jspdf";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";
import "./EditorDeTemario_Practico.css";
import { Plus, Trash2, Save } from "lucide-react";

// ================= CONFIG =================
const API_ENDPOINT =
  "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/customtemarios";

// ================= UTILS =================
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

// ================= BASE =================
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

  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [saveError, setSaveError] = useState("");

  // ================= EDICIÓN =================
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

  const handleNotasCapitulo = (cap, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario[cap].notas_capitulo = value;
    setTemario(nuevo);
  };

  // ================= CAPÍTULOS =================
  const agregarCapitulo = () =>
    setTemario({
      ...temario,
      temario: [
        ...temario.temario,
        {
          capitulo: `Nuevo capítulo ${temario.temario.length + 1}`,
          tiempo_capitulo_min: 0,
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

  // ================= TEMAS =================
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

  // ================= AJUSTAR TIEMPOS =================
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

  // ================= GUARDAR EN BD =================
  const guardarEnBD = async () => {
    setSaveMsg("");
    setSaveError("");

    if (!temario.nombre_curso.trim()) {
      setSaveError("El nombre del curso es obligatorio");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch(API_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...temario,
          source: "plantilla-temario",
        }),
      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.message || "Error al guardar");

      setSaveMsg(`✅ Guardado correctamente (ID: ${data.temarioId})`);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  };

  // ================= EXPORTAR PDF =================
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
      doc.setFontSize(14).setTextColor(azul);
      doc.text(s.titulo, margin.left, y);
      y += 18;
      doc.setFontSize(11).setTextColor(negro);
      doc.splitTextToSize(s.texto, contentW).forEach((line) => {
        addPageIfNeeded(14);
        doc.text(line, margin.left, y);
        y += 14;
      });
      y += 10;
    });

    doc.save(`Temario_${slugify(temario.nombre_curso)}.pdf`);
  };

  // ================= RENDER =================
  return (
    <div className="temario-editor-container">
      <h2>Plantilla de Temario</h2>

      <button className="btn-primario" onClick={guardarEnBD} disabled={saving}>
        <Save size={16} /> {saving ? "Guardando..." : "Guardar en BD"}
      </button>

      {saveMsg && <p style={{ color: "green" }}>{saveMsg}</p>}
      {saveError && <p style={{ color: "red" }}>{saveError}</p>}

      {/* FORMULARIO COMPLETO: reutiliza exactamente el que ya tenías */}
      {/* (inputs, capítulos, temas, exportar, etc.) */}
    </div>
  );
}
