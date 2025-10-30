import React, { useState, useEffect } from "react";
import jsPDF from "jspdf";
import { fetchAuthSession } from "aws-amplify/auth";
import { downloadExcelTemario } from "../utils/downloadExcel";
import encabezadoImagen from "../assets/encabezado.png";
import pieDePaginaImagen from "../assets/pie_de_pagina.png";
import "./EditorDeTemario.css";

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
    .replace(/^-+|-+$/g, "") || "curso";

function EditorDeTemario({ temarioInicial, onSave, isLoading }) {
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

  useEffect(() => {
    setTemario({
      ...temarioInicial,
      temario: Array.isArray(temarioInicial?.temario)
        ? temarioInicial.temario
        : [],
    });
  }, [temarioInicial]);

  // ===== CAMBIO DE CAMPOS =====
  const handleFieldChange = (capIndex, subIndex, field, value) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) nuevo.temario = [];
    if (!nuevo.temario[capIndex]) return;

    if (subIndex === null) {
      nuevo.temario[capIndex][field] = value;
    } else {
      if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
        nuevo.temario[capIndex].subcapitulos = [];
      if (typeof nuevo.temario[capIndex].subcapitulos[subIndex] !== "object") {
        nuevo.temario[capIndex].subcapitulos[subIndex] = {
          nombre: String(
            nuevo.temario[capIndex].subcapitulos[subIndex] || "Tema"
          ),
        };
      }
      nuevo.temario[capIndex].subcapitulos[subIndex][field] =
        field.includes("tiempo") || field === "sesion"
          ? parseInt(value, 10) || 0
          : value;
    }

    nuevo.temario[capIndex].tiempo_capitulo_min = (nuevo.temario[
      capIndex
    ].subcapitulos || []).reduce(
      (sum, s) => sum + (parseInt(s.tiempo_subcapitulo_min) || 0),
      0
    );
    setTemario(nuevo);
  };

  // ===== AGREGAR CAPÍTULO =====
  const agregarCapitulo = () => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) nuevo.temario = [];
    nuevo.temario.push({
      capitulo: `Nuevo capítulo ${nuevo.temario.length + 1}`,
      tiempo_capitulo_min: 0,
      objetivos_capitulo: "",
      subcapitulos: [
        { nombre: "Nuevo tema 1", tiempo_subcapitulo_min: 30, sesion: 1 },
      ],
    });
    setTemario(nuevo);
  };

  // ===== AGREGAR TEMA =====
  const agregarTema = (capIndex) => {
    const nuevo = JSON.parse(JSON.stringify(temario));
    if (!Array.isArray(nuevo.temario)) return;
    if (!Array.isArray(nuevo.temario[capIndex].subcapitulos))
      nuevo.temario[capIndex].subcapitulos = [];
    nuevo.temario[capIndex].subcapitulos.push({
      nombre: `Nuevo tema ${nuevo.temario[capIndex].subcapitulos.length + 1}`,
      tiempo_subcapitulo_min: 30,
      sesion: 1,
    });
    setTemario(nuevo);
  };

  // ===== AJUSTAR TIEMPOS =====
  const ajustarTiempos = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) return;
    const horas = temario?.horas_por_sesion || 2;
    const minutosTotales = horas * 60;
    const totalTemas = temario.temario.reduce(
      (acc, cap) => acc + (cap.subcapitulos?.length || 0),
      0
    );
    if (totalTemas === 0) return;
    const minutosPorTema = Math.floor(minutosTotales / totalTemas);
    const nuevo = JSON.parse(JSON.stringify(temario));
    nuevo.temario.forEach((cap) => {
      if (!Array.isArray(cap.subcapitulos)) cap.subcapitulos = [];
      cap.subcapitulos.forEach((sub) => {
        sub.tiempo_subcapitulo_min = minutosPorTema;
      });
      cap.tiempo_capitulo_min = cap.subcapitulos.reduce(
        (a, s) => a + (s.tiempo_subcapitulo_min || 0),
        0
      );
    });
    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: `⏱️ Tiempos ajustados a ${horas}h` });
  };

  // ===== GUARDAR ===== (corregido para evitar 400)
  const handleSaveClick = async () => {
    setGuardando(true);
    setMensaje({ tipo: "", texto: "" });

    const nota =
      window.prompt("Escribe una nota para esta versión (opcional):") || "";

    try {
      const token = localStorage.getItem("id_token");

      const bodyData = {
        cursoId:
          temario?.nombre_curso?.trim() ||
          temario?.tema_curso?.trim() ||
          `curso_${Date.now()}`,
        contenido: temario,
        autor: userEmail || "sin-correo",
        nombre_curso: temario?.nombre_curso || "",
        tecnologia: temario?.tecnologia || "",
        asesor_comercial: temario?.asesor_comercial || "",
        nombre_preventa: temario?.nombre_preventa || "",
        nota_version: nota,
        fecha_creacion: new Date().toISOString(),
      };

      const response = await fetch(
        "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(bodyData),
        }
      );

      const data = await response.json();

      if (!response.ok || !data.success)
        throw new Error(data.error || "Error al guardar versión");

      setMensaje({ tipo: "ok", texto: "✅ Versión guardada correctamente" });
    } catch (err) {
      console.error("Error al guardar versión:", err);
      setMensaje({
        tipo: "error",
        texto: "❌ Error al guardar versión (ver consola)",
      });
    } finally {
      setGuardando(false);
      setTimeout(() => setMensaje({ tipo: "", texto: "" }), 4000);
    }
  };

  // ===== EXPORTAR PDF =====
  const exportarPDF = async () => {
    try {
      if (!Array.isArray(temario.temario) || temario.temario.length === 0) {
        setMensaje({ tipo: "error", texto: "No hay contenido para exportar." });
        return;
      }

      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
      const azul = "#005A9C";
      const negro = "#000000";
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = { top: 230, bottom: 100, left: 60, right: 60 }; // ✅ más margen
      const contentWidth = pageWidth - margin.left - margin.right;
      const encabezado = await toDataURL(encabezadoImagen);
      const pie = await toDataURL(pieDePaginaImagen);
      let y = margin.top;

      const addPageIfNeeded = (extra = 40) => {
        if (y + extra > pageHeight - margin.bottom) {
          doc.addPage();
          y = margin.top;
        }
      };

      doc.setFont("helvetica", "bold");
      doc.setFontSize(22);
      doc.setTextColor(azul);
      const tituloCurso = temario?.nombre_curso || "Temario del Curso";
      const lineasCurso = doc.splitTextToSize(tituloCurso, contentWidth - 40);
      lineasCurso.forEach((linea) => {
        doc.text(linea, pageWidth / 2, y, { align: "center" });
        y += 18;
      });
      y += 20;

      const secciones = [
        { titulo: "Descripción General", texto: temario?.descripcion_general },
        { titulo: "Audiencia", texto: temario?.audiencia },
        { titulo: "Prerrequisitos", texto: temario?.prerrequisitos },
        { titulo: "Objetivos", texto: temario?.objetivos },
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
        doc.setFontSize(10);
        doc.setTextColor(negro);
        const lineas = doc.splitTextToSize(s.texto, contentWidth);
        lineas.forEach((linea) => {
          addPageIfNeeded(14);
          doc.text(linea, margin.left, y, { align: "justify" });
          y += 14;
        });
        y += 10;
      });

      addPageIfNeeded(50);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(azul);
      doc.text("Temario", margin.left, y);
      y += 25;

      temario.temario.forEach((cap, i) => {
        addPageIfNeeded(60);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        doc.setTextColor(azul);
        const tituloCap = `Capítulo ${i + 1}: ${cap.capitulo}`;
        const lineasCap = doc.splitTextToSize(tituloCap, contentWidth - 40);
        lineasCap.forEach((linea) => {
          doc.text(linea, margin.left, y);
          y += 14;
        });
        y += 6;

        doc.setFont("helvetica", "italic");
        doc.setFontSize(9);
        doc.setTextColor(negro);
        doc.text(`Duración total: ${cap.tiempo_capitulo_min || 0} min`, margin.left + 10, y);
        y += 14;

        if (cap.objetivos_capitulo) {
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          const objetivos = Array.isArray(cap.objetivos_capitulo)
            ? cap.objetivos_capitulo.join(" ")
            : cap.objetivos_capitulo;
          const lines = doc.splitTextToSize(`Objetivos: ${objetivos}`, contentWidth);
          lines.forEach((line) => {
            addPageIfNeeded(12);
            doc.text(line, margin.left + 15, y, { align: "justify" });
            y += 12;
          });
          y += 10;
        }

        cap.subcapitulos.forEach((sub, j) => {
          addPageIfNeeded(18);
          const subObj = typeof sub === "object" ? sub : { nombre: sub };
          const meta = `${subObj.tiempo_subcapitulo_min || 0} min • Sesión ${subObj.sesion || 1}`;
          doc.setFont("helvetica", "normal");
          doc.setFontSize(10);
          const subTitulo = `${i + 1}.${j + 1} ${subObj.nombre}`;
          const subLineas = doc.splitTextToSize(subTitulo, contentWidth - 120);
          subLineas.forEach((linea, idx) => {
            addPageIfNeeded(12);
            doc.text(linea, margin.left + 25, y);
            if (idx === 0) doc.text(meta, pageWidth - margin.right, y, { align: "right" });
            y += 12;
          });
        });
        y += 20;
      });

      const totalPages = doc.internal.getNumberOfPages();
      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);
        const propsEnc = doc.getImageProperties(encabezado);
        const altoEnc = (propsEnc.height / propsEnc.width) * pageWidth;
        doc.addImage(encabezado, "PNG", 0, 0, pageWidth, altoEnc);
        const propsPie = doc.getImageProperties(pie);
        const altoPie = (propsPie.height / propsPie.width) * pageWidth;
        doc.addImage(pie, "PNG", 0, pageHeight - altoPie, pageWidth, altoPie);
        doc.setFontSize(8);
        doc.setTextColor("#666");
        doc.text(
          "Documento generado mediante tecnología de IA bajo la supervisión y aprobación de Netec.",
          margin.left,
          pageHeight - 70
        );
        doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 55, {
          align: "center",
        });
      }

      doc.save(`Temario_${slugify(temario?.nombre_curso)}.pdf`);
      setMensaje({ tipo: "ok", texto: "✅ PDF exportado correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al generar PDF" });
    }
  };

  const exportarExcel = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) {
      setMensaje({ tipo: "error", texto: "No hay datos para exportar." });
      return;
    }
    downloadExcelTemario(temario);
    setMensaje({ tipo: "ok", texto: "✅ Excel exportado correctamente" });
  };

  // === RENDER ===
  return (
    <div className="editor-container">
      {mensaje.texto && <div className={`msg ${mensaje.tipo}`}>{mensaje.texto}</div>}

      <h3>Temario Detallado</h3>

      {(temario.temario || []).map((cap, i) => (
        <div key={i} className="capitulo-editor">
          <h4>Capítulo {i + 1}</h4>
          <input
            value={cap.capitulo || ""}
            onChange={(e) => handleFieldChange(i, null, "capitulo", e.target.value)}
            className="input-capitulo"
          />
          <div className="duracion-total">
            ⏱️ Duración total: <strong>{cap.tiempo_capitulo_min || 0} min</strong>
          </div>

          <label>Objetivos del Capítulo</label>
          <textarea
            value={
              Array.isArray(cap.objetivos_capitulo)
                ? cap.objetivos_capitulo.join("\n")
                : cap.objetivos_capitulo || ""
            }
            onChange={(e) =>
              handleFieldChange(i, null, "objetivos_capitulo", e.target.value.split("\n"))
            }
            className="textarea-objetivos-capitulo"
          />

          <ul>
            {(cap.subcapitulos || []).map((sub, j) => (
              <li key={j} className="subcapitulo-item">
                <span>
                  {i + 1}.{j + 1}
                </span>
                <input
                  value={sub.nombre || ""}
                  onChange={(e) => handleFieldChange(i, j, "nombre", e.target.value)}
                />
                <input
                  type="number"
                  value={sub.tiempo_subcapitulo_min || 0}
                  onChange={(e) =>
                    handleFieldChange(i, j, "tiempo_subcapitulo_min", e.target.value)
                  }
                  placeholder="min"
                />
                <input
                  type="number"
                  value={sub.sesion || 1}
                  onChange={(e) => handleFieldChange(i, j, "sesion", e.target.value)}
                  placeholder="sesión"
                />
              </li>
            ))}
          </ul>

          <button className="btn-agregar-tema" onClick={() => agregarTema(i)}>
             Agregar Tema
          </button>
        </div>
      ))}

      <div className="btn-agregar-capitulo-container">
        <button className="btn-agregar-capitulo" onClick={agregarCapitulo}>
           Agregar Capítulo
        </button>
      </div>

      <div className="acciones-footer">
        <button className="btn-primario" onClick={ajustarTiempos}>
          Ajustar Tiempos
        </button>
        <button className="btn-secundario" onClick={handleSaveClick} disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar Versión"}
        </button>
        <button className="btn-secundario" onClick={() => setModalExportar(true)}>
          Exportar
        </button>
      </div>

      {modalExportar && (
        <div className="modal-overlay" onClick={() => setModalExportar(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Exportar</h3>
              <button className="modal-close" onClick={() => setModalExportar(false)}>
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
                  if (exportTipo === "pdf") exportarPDF();
                  else exportarExcel();
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

export default EditorDeTemario;
