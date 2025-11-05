// src/components/EditorDeTemario_seminario.jsx
import React, { useState, useEffect, useMemo } from "react";
import { useParams } from "react-router-dom"; // ✅ NUEVO
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario_seminario.css";

// === Utilidades de limpieza ===
const cleanTitleNivel = (title = "") =>
  String(title)
    .replace(/\s*\((?:nivel\s+)?(?:b[aá]sico|intermedio|avanzado)\)\s*/gi, " ")
    .replace(/\s{2,}/g, " ")
    .trim();

const stripEtiquetaTema = (text = "") =>
  String(text)
    .replace(/^\s*(te[oó]r[ií]a|pr[aá]ctica)\s*:\s*/i, "")
    .trim();

const normalizeObjetivos = (text = "") => {
  let t = String(text)
    .replace(/[,.]{2,}/g, (m) => (m.includes(".") ? ". " : ", "))
    .replace(/\s*,\s*/g, ", ")
    .replace(/\s*\.\s*/g, ". ")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (t && !/[.!?]$/.test(t)) t += ".";
  return t;
};

// === Utilidad para convertir imágenes a base64 ===
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
    .replace(/^-+|-+$/g, "") || "seminario";

export default function EditorDeTemario_seminario({
  temarioInicial,
  onSave,
  isLoading,
}) {
  const { cursoId, versionId } = useParams(); // ✅ NUEVO

  const [temario, setTemario] = useState(() => ({
    ...temarioInicial,
    temario: Array.isArray(temarioInicial?.temario)
      ? temarioInicial.temario
      : [],
  }));

  const [userEmail, setUserEmail] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: "", texto: "" });
  const [modalExportar, setModalExportar] = useState(false);
  const [exportTipo, setExportTipo] = useState("pdf");

  // ✅ NUEVO: carga desde DynamoDB si hay cursoId/versionId
  useEffect(() => {
    async function cargarDesdeDynamo() {
      if (cursoId && versionId && !temarioInicial) {
        try {
          const res = await fetch(
            `https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-seminario?id=${cursoId}&version=${versionId}`
          );
          const data = await res.json();
          if (data?.contenido) {
            setTemario(data.contenido);
            setMensaje({
              tipo: "ok",
              texto: "✅ Versión cargada desde DynamoDB correctamente",
            });
          }
        } catch (err) {
          console.error("Error al cargar versión:", err);
          setMensaje({
            tipo: "error",
            texto: "❌ No se pudo cargar la versión guardada.",
          });
        }
      }
    }
    cargarDesdeDynamo();
  }, [cursoId, versionId, temarioInicial]);

  // === Obtener usuario autenticado ===
  useEffect(() => {
    const getUser = async () => {
      try {
        const session = await fetchAuthSession();
        const email = session?.tokens?.idToken?.payload?.email;
        setUserEmail(email || "sin-correo");
      } catch (err) {
        console.error("Error obteniendo usuario:", err);
      }
    };
    getUser();
  }, []);

  // === Actualiza el temario cuando cambia el inicial ===
  useEffect(() => {
    if (temarioInicial) {
      setTemario({
        ...temarioInicial,
        temario: Array.isArray(temarioInicial?.temario)
          ? temarioInicial.temario
          : [],
      });
    }
  }, [temarioInicial]);

  // === Temario limpio para exportación ===
  const temarioLimpio = useMemo(() => {
    const copia = JSON.parse(JSON.stringify(temario || {}));
    copia.nombre_curso = cleanTitleNivel(
      copia?.nombre_curso || "Seminario Profesional"
    );
    if (Array.isArray(copia?.temario)) {
      copia.temario.forEach((cap) => {
        cap.objetivos_capitulo = normalizeObjetivos(
          cap.objetivos_capitulo || ""
        );
        if (Array.isArray(cap.subcapitulos)) {
          cap.subcapitulos.forEach((s) => {
            s.nombre = stripEtiquetaTema(s.nombre || "");
          });
        }
      });
    }
    return copia;
  }, [temario]);

  // === Editar campos ===
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!nuevo.temario[capIndex]) return;

    if (subIndex !== null) {
      // === Subcapítulo ===
      nuevo.temario[capIndex].subcapitulos[subIndex][field] =
        field.includes("tiempo") ? parseFloat(value) || 0 : value;
    } else {
      // === Capítulo ===
      nuevo.temario[capIndex][field] = value;
    }

    // Recalcular capítulo
    nuevo.temario[capIndex].tiempo_capitulo_min = nuevo.temario[capIndex].subcapitulos.reduce(
      (sum, s) => sum + (parseFloat(s.tiempo_subcapitulo_min) || 0),
      0
    );

    // Recalcular total seminario
    let totalMin = nuevo.temario.reduce(
      (acc, cap) => acc + (parseFloat(cap.tiempo_capitulo_min) || 0),
      0
    );

    // Límite máximo
    const horasMax = parseFloat(nuevo.horas_totales) || parseFloat(nuevo.horas_por_sesion) || 2;
    const minutosMax = horasMax * 60;
    if (totalMin > minutosMax) {
      const factor = minutosMax / totalMin;
      nuevo.temario.forEach((cap) => {
        cap.tiempo_capitulo_min = Math.floor(cap.tiempo_capitulo_min * factor);
        cap.subcapitulos.forEach((sub) => {
          sub.tiempo_subcapitulo_min = Math.floor(sub.tiempo_subcapitulo_min * factor);
        });
      });
      totalMin = minutosMax;
    }

    nuevo.horas_totales = parseFloat((totalMin / 60).toFixed(1));
    setTemario(nuevo);
  };


  // === Agregar capítulo ===
  const agregarCapitulo = () => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.push({
      capitulo: `Nuevo capítulo ${nuevo.temario.length + 1}`,
      tiempo_capitulo_min: 0,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    });
    setTemario(nuevo);
  };

  // === Agregar tema ===
  const agregarTema = (capIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
      nuevo.temario[capIndex].subcapitulos = [];
    nuevo.temario[capIndex].subcapitulos.push({
      nombre: `Nuevo tema ${
        nuevo.temario[capIndex].subcapitulos.length + 1
      }`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // === Eliminar subtema ===
  const eliminarTema = (capIndex, subIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!nuevo.temario[capIndex]) return;

    nuevo.temario[capIndex].subcapitulos.splice(subIndex, 1);

    // Recalcular tiempo total del capítulo
    nuevo.temario[capIndex].tiempo_capitulo_min = nuevo.temario[capIndex].subcapitulos.reduce(
      (sum, s) => sum + (parseFloat(s.tiempo_subcapitulo_min) || 0),
      0
    );

    // Recalcular total general
    const totalMin = nuevo.temario.reduce(
      (acc, cap) => acc + (parseFloat(cap.tiempo_capitulo_min) || 0),
      0
    );
    nuevo.horas_totales = parseFloat((totalMin / 60).toFixed(1));

    setTemario(nuevo);
  };

  // === Eliminar capítulo ===
  const eliminarCapitulo = (capIndex) => {
    if (!window.confirm("¿Seguro que deseas eliminar este capítulo?")) return;
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.splice(capIndex, 1);

    // Recalcular total general
    const totalMin = nuevo.temario.reduce(
      (acc, cap) => acc + (parseFloat(cap.tiempo_capitulo_min) || 0),
      0
    );
    nuevo.horas_totales = parseFloat((totalMin / 60).toFixed(1));

    setTemario(nuevo);
  };


  // === Ajustar tiempos ===
  const ajustarTiempos = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) return;

    // 🔹 1. Duración total declarada por el usuario
    const horasObjetivo = parseFloat(temario.horas_totales) || parseFloat(temario.horas_por_sesion) || 2;
    const minutosObjetivo = horasObjetivo * 60;

    // 🔹 2. Contar total de subtemas
    const totalSubtemas = temario.temario.reduce(
      (acc, cap) => acc + (cap.subcapitulos?.length || 0),
      0
    );
    if (totalSubtemas === 0) return;

    // 🔹 3. Calcular tiempo por tema base
    const minutosPorTema = Math.floor(minutosObjetivo / totalSubtemas);
    const nuevo = JSON.parse(JSON.stringify(temario));

    // 🔹 4. Ajustar tiempos de subtemas y capítulos
    nuevo.temario.forEach((cap) => {
      cap.subcapitulos.forEach((sub) => {
        sub.tiempo_subcapitulo_min = minutosPorTema;
      });
      cap.tiempo_capitulo_min = cap.subcapitulos.reduce(
        (sum, s) => sum + (s.tiempo_subcapitulo_min || 0),
        0
      );
    });

    // 🔹 5. Recalcular total real y limitarlo si supera el objetivo
    let totalMin = nuevo.temario.reduce(
      (acc, cap) => acc + (parseFloat(cap.tiempo_capitulo_min) || 0),
      0
    );

    // Si excede el objetivo, escalar proporcionalmente
    if (totalMin > minutosObjetivo) {
      const factor = minutosObjetivo / totalMin;
      nuevo.temario.forEach((cap) => {
        cap.tiempo_capitulo_min = Math.floor(cap.tiempo_capitulo_min * factor);
        cap.subcapitulos.forEach((sub) => {
          sub.tiempo_subcapitulo_min = Math.floor(sub.tiempo_subcapitulo_min * factor);
        });
      });
      totalMin = minutosObjetivo; // aseguramos límite
    }

    // 🔹 6. Actualizar horas totales finales
    nuevo.horas_totales = parseFloat((totalMin / 60).toFixed(1));

    setTemario(nuevo);
    setMensaje({
      tipo: "ok",
      texto: `⏱️ Tiempos ajustados: total ${nuevo.horas_totales}h (máx. ${horasObjetivo}h permitidas).`,
    });
  };


  // === Guardar versión ===
  const handleSaveClick = async () => {
    setGuardando(true);
    setMensaje({ tipo: "", texto: "" });
    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):") || "";
    try {
      await onSave?.({ ...temario, autor: userEmail }, nota);
      setMensaje({ tipo: "ok", texto: "✅ Versión guardada correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al guardar la versión" });
    } finally {
      setGuardando(false);
      setTimeout(() => setMensaje({ tipo: "", texto: "" }), 4000);
    }
  };

  // === Exportar PDF profesional ===
  const exportarPDF = async () => {
    try {
      if (
        !Array.isArray(temarioLimpio.temario) ||
        temarioLimpio.temario.length === 0
      ) {
        setMensaje({
          tipo: "error",
          texto: "No hay contenido para exportar.",
        });
        return;
      }

      const doc = new jsPDF({
        orientation: "portrait",
        unit: "pt",
        format: "letter",
      });
      const azul = "#005A9C";
      const negro = "#000";
      const gris = "#555";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();

      const [encabezado, pie] = await Promise.all([
        toDataURL(encabezadoImagen),
        toDataURL(pieDePaginaImagen),
      ]);

      const encProps = doc.getImageProperties(encabezado);
      const encAlto = (encProps.height / encProps.width) * pageWidth;
      const pieProps = doc.getImageProperties(pie);
      const pieAlto = (pieProps.height / pieProps.width) * pageWidth;

      const margin = {
        top: encAlto + 28,
        bottom: pieAlto + 30,
        left: 72,
        right: 72,
      };
      const contentWidth = pageWidth - margin.left - margin.right;
      let y = margin.top;

      const drawHeaderFooter = () => {
        doc.addImage(encabezado, "PNG", 0, 0, pageWidth, encAlto);
        doc.addImage(pie, "PNG", 0, pageHeight - pieAlto, pageWidth, pieAlto);
        doc.setFont("helvetica", "italic");
        doc.setFontSize(9);
        doc.setTextColor("#444");
        doc.text(
          "Documento generado mediante tecnología de IA bajo la supervisión y aprobación de Netec.",
          margin.left,
          pageHeight - 18
        );
        doc.setFont("helvetica", "normal");
        doc.setTextColor(gris);
        doc.text(
          `Página ${doc.internal.getCurrentPageInfo().pageNumber}`,
          pageWidth - margin.right,
          pageHeight - 18,
          { align: "right" }
        );
      };

      const addPageIfNeeded = (extra = 40) => {
        if (y + extra > pageHeight - margin.bottom) {
          doc.addPage();
          drawHeaderFooter();
          y = margin.top;
        }
      };

      drawHeaderFooter();

      // === Encabezado del PDF ===
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azul);
      const titulo = temarioLimpio?.nombre_curso || "Seminario Profesional";
      const tituloLineas = doc.splitTextToSize(titulo, contentWidth);
      tituloLineas.forEach((linea) => {
        doc.text(linea, margin.left, y);
        y += 24;
      });
      y += 14;
      
      // === Subtítulo con duración (alineado a la derecha) ===
      if (temarioLimpio?.horas_totales) {
        doc.setFont("helvetica", "italic");
        doc.setFontSize(12);
        doc.setTextColor(azul);
        doc.text(
          `Duración total del curso: ${temarioLimpio.horas_totales} horas`,
          pageWidth - margin.right,
          y - 10,
          { align: "right" }
        );
        y += 16;
      }

      // === DESCRIPCIÓN GENERAL ===
      if (temarioLimpio?.descripcion_general) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        doc.text("Descripción General", margin.left, y);
        y += 16;

        doc.setFont("helvetica", "normal");
        doc.setFontSize(11);
        doc.setTextColor(negro);
        const desc = doc.splitTextToSize(temarioLimpio.descripcion_general, contentWidth);
        desc.forEach((linea) => {
          addPageIfNeeded(16);
          doc.text(linea, margin.left, y);
          y += 16;
        });
        y += 10;
      }

      // === AUDIENCIA ===
      if (temarioLimpio?.audiencia) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        doc.text("Audiencia", margin.left, y);
        y += 16;

        doc.setFont("helvetica", "normal");
        doc.setFontSize(11);
        doc.setTextColor(negro);
        const aud = doc.splitTextToSize(temarioLimpio.audiencia, contentWidth);
        aud.forEach((linea) => {
          addPageIfNeeded(16);
          doc.text(linea, margin.left, y);
          y += 16;
        });
        y += 10;
      }

      // === PRERREQUISITOS ===
      if (temarioLimpio?.prerrequisitos) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        doc.text("Prerrequisitos", margin.left, y);
        y += 16;

        doc.setFont("helvetica", "normal");
        doc.setFontSize(11);
        doc.setTextColor(negro);
        const pre = doc.splitTextToSize(temarioLimpio.prerrequisitos, contentWidth);
        pre.forEach((linea) => {
          addPageIfNeeded(16);
          doc.text(linea, margin.left, y);
          y += 16;
        });
        y += 10;
      }

      // === OBJETIVOS ===
      if (Array.isArray(temarioLimpio.objetivos_generales)) {
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        doc.text("Objetivos", margin.left, y);
        y += 16;

        doc.setFont("helvetica", "normal");
        doc.setFontSize(11);
        doc.setTextColor(negro);
        temarioLimpio.objetivos_generales.forEach((obj) => {
          addPageIfNeeded(16);
          const textoObj = doc.splitTextToSize(obj, contentWidth);
          textoObj.forEach((linea) => {
            doc.text(linea, margin.left, y);
            y += 16;
          });
        });
        y += 14;
      }

      // === Separador antes del temario ===
      doc.setDrawColor(200);
      doc.setLineWidth(0.5);
      doc.line(margin.left, y, pageWidth - margin.right, y);
      y += 22;

      // === TÍTULO DE TEMARIO ===
      doc.setFont("helvetica", "bold");
      doc.setFontSize(16);
      doc.setTextColor(azul);
      doc.text("Temario", margin.left, y);
      y += 22;

      addPageIfNeeded(50);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(16);
      doc.setTextColor(azul);
      doc.text("Temario Detallado", margin.left, y);
      y += 22;

      temarioLimpio.temario.forEach((cap, i) => {
        addPageIfNeeded(70);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        const capTitle = `Capítulo ${i + 1}: ${cap.capitulo}`;
        const capLines = doc.splitTextToSize(capTitle, contentWidth);
        capLines.forEach((line) => {
          doc.text(line, margin.left, y);
          y += 16;
        });

        doc.setFont("helvetica", "italic");
        doc.setFontSize(9);
        doc.setTextColor(gris);
        doc.text(
          `Duración total: ${cap.tiempo_capitulo_min || 0} min`,
          margin.left + 10,
          y
        );
        y += 12;

        if (cap.objetivos_capitulo) {
          doc.setFont("helvetica", "normal");
          doc.setFontSize(11);
          doc.setTextColor(negro);
          const objLines = doc.splitTextToSize(
            `Objetivos: ${normalizeObjetivos(cap.objetivos_capitulo)}`,
            contentWidth - 15
          );
          objLines.forEach((linea) => {
            addPageIfNeeded(14);
            doc.text(linea, margin.left + 15, y);
            y += 14;
          });
        }
        y += 6;

        (cap.subcapitulos || []).forEach((sub, j) => {
          addPageIfNeeded(16);
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          const tema = `${i + 1}.${j + 1} ${stripEtiquetaTema(
            sub.nombre || ""
          )}`;
          const temaLineas = doc.splitTextToSize(tema, contentWidth - 80);
          temaLineas.forEach((linea, idx) => {
            doc.text(linea, margin.left + 25, y);
            if (idx === 0) {
              doc.text(
                `${sub.tiempo_subcapitulo_min || 0} min`,
                pageWidth - margin.right,
                y,
                { align: "right" }
              );
            }
            y += 12;
          });
        });

        y += 8;
        doc.setDrawColor(200);
        doc.setLineWidth(0.5);
        doc.line(margin.left, y, pageWidth - margin.right, y);
        y += 16;
      });

      doc.save(`Seminario_${slugify(temarioLimpio?.nombre_curso)}.pdf`);
      setMensaje({ tipo: "ok", texto: "✅ PDF exportado correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al generar PDF" });
    }
  };

  // === Exportar Excel ===
  const exportarExcel = () => {
    downloadExcelTemario(temarioLimpio);
    setMensaje({ tipo: "ok", texto: "✅ Excel exportado correctamente" });
  };

  return (
    <div className="editor-container">
      {mensaje.texto && <div className={`msg ${mensaje.tipo}`}>{mensaje.texto}</div>}

      {/* === Botón para volver al generador === */}
      <button
        className="btn-volver"
        onClick={() => window.history.back()}
      >
        ← Volver al menú de contenidos
      </button>

      {/* === INFORMACIÓN GENERAL DEL SEMINARIO === */}
      <h3>Información general del seminario</h3>

      <div className="info-general">
        <label>Duración total del seminario (horas)</label>
        <input
          type="number"
          min ="0.5"
          step="0.5"
          value={temario.horas_totales || ""}
          onChange={(e) => setTemario({ ...temario, horas_totales: parseFloat(e.target.value) || 0, })}
        />

        <label>Descripción general</label>
        <textarea
          value={temario.descripcion_general || ""}
          onChange={(e) => setTemario({ ...temario, descripcion_general: e.target.value })}
          rows="3"
        />

        <label>Audiencia</label>
        <textarea
          value={temario.audiencia || ""}
          onChange={(e) => setTemario({ ...temario, audiencia: e.target.value })}
          rows="3"
        />

        <label>Prerrequisitos</label>
        <textarea
          value={temario.prerrequisitos || ""}
          onChange={(e) => setTemario({ ...temario, prerrequisitos: e.target.value })}
          rows="3"
        />

        <label>Objetivos</label>
        <textarea
          value={temario.objetivos_generales?.join("\n") || ""}
          onChange={(e) =>
            setTemario({
              ...temario,
              objetivos_generales: e.target.value.split("\n"),
            })
          }
          rows="3"
        />
      </div>

      <hr />

      <h3>Temario Detallado</h3>

      {(temario.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>
          <input
            value={cap.capitulo || ""}
            onChange={(e) =>
              handleFieldChange(i, null, "capitulo", e.target.value)
            }
            className="input-capitulo"
          />
          <div className="duracion-total">
            ⏱️ <strong>Duración total: {cap.tiempo_capitulo_min || 0} min</strong>
          </div>
          <label>Objetivos del capítulo</label>
          <textarea
            value={cap.objetivos_capitulo || ""}
            onChange={(e) =>
              handleFieldChange(i, null, "objetivos_capitulo", e.target.value)
            }
          />
          <ul>
            {(cap.subcapitulos || []).map((sub, j) => (
              <li key={j} className="subcapitulo-item">
                <span>
                  {i + 1}.{j + 1}
                </span>
                <input
                  value={sub.nombre || ""}
                  onChange={(e) =>
                    handleFieldChange(i, j, "nombre", e.target.value)
                  }
                />
                <input
                  type="number"
                  value={sub.tiempo_subcapitulo_min || 0}
                  onChange={(e) =>
                    handleFieldChange(
                      i,
                      j,
                      "tiempo_subcapitulo_min",
                      e.target.value
                    )
                  }
                  placeholder="min"
                />
                <button
                  className="btn-eliminar-tema"
                  onClick={() => eliminarTema(i,j)}
                  title="Eliminar subtema"
                >
                  🗑️
                </button>
              </li>
            ))}
          </ul>
          <button className="btn-agregar-tema" onClick={() => agregarTema(i)}>
            ➕ Agregar tema
          </button>
          <button
            className="btn-eliminar-capitulo"
            onClick={() => eliminarCapitulo(i)}
          >
            🗑️ Eliminar Capítulo
          </button>
        </div>
      ))}

      <div className="btn-agregar-capitulo-container">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
          ➕ Agregar capítulo
        </button>
      </div>

      <div className="acciones-footer">
        <button className="btn-primario" onClick={ajustarTiempos}>
          Ajustar tiempos
        </button>
        <button
          className="btn-secundario"
          onClick={handleSaveClick}
          disabled={guardando}
        >
          {guardando ? "Guardando..." : "Guardar versión"}
        </button>
        <button
          className="btn-secundario"
          onClick={() => setModalExportar(true)}
        >
          Exportar
        </button>
      </div>

      {modalExportar && (
        <div className="modal-overlay" onClick={() => setModalExportar(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Exportar</h3>
              <button
                className="modal-close"
                onClick={() => setModalExportar(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "pdf"}
                  onChange={() => setExportTipo("pdf")}
                />{" "}
                PDF
              </label>
              <label>
                <input
                  type="radio"
                  checked={exportTipo === "excel"}
                  onChange={() => setExportTipo("excel")}
                />{" "}
                Excel
              </label>
            </div>
            <div className="modal-footer">
              <button
                onClick={() => {
                  exportTipo === "pdf" ? exportarPDF() : exportarExcel();
                  setModalExportar(false);
                }}
                className="btn-guardar"
              >
                Exportar {exportTipo.toUpperCase()}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
