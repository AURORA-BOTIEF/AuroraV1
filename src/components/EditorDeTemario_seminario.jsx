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
      let val = field.includes("tiempo") ? parseFloat(value) || 0 : value;
      if (field.includes("tiempo") && val < 1) val = 1; // ✅ mínimo 1 minuto
      nuevo.temario[capIndex].subcapitulos[subIndex][field] = val;
    } else {
      // === Capítulo ===
      let val = field.includes("tiempo") ? parseFloat(value) || 0 : value;
      if (field.includes("tiempo") && val < 1) val = 1; // ✅ mínimo 1 minuto
      nuevo.temario[capIndex][field] = val;
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
      nombre: `Nuevo tema ${nuevo.temario[capIndex].subcapitulos.length + 1
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


  // ===== AJUSTAR TIEMPOS (idéntico al de cursos, con límites 0.5–4h) =====
  const ajustarTiempos = () => {
    if (!Array.isArray(temario.temario) || temario.temario.length === 0) return;

    // Duración total declarada (con límites)
    let horas = temario?.horas_por_sesion || 2;
    if (horas < 0.5) horas = 0.5;
    if (horas > 4) horas = 4;
    const minutosTotales = horas * 60;

    // Contar total de subtemas
    const totalTemas = temario.temario.reduce(
      (acc, cap) => acc + (cap.subcapitulos?.length || 0),
      0
    );
    if (totalTemas === 0) return;

    // Calcular tiempo por subtema
    const minutosPorTema = Math.floor(minutosTotales / totalTemas);

    // Crear copia y ajustar tiempos
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

    // Aplicar cambios
    setTemario(nuevo);
    setMensaje({ tipo: "ok", texto: `⏱️ Tiempos ajustados a ${horas}h` });
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

      // === Dibuja solo encabezado y pie gráfico (sin texto) ===
      const drawHeaderFooter = () => {
        doc.addImage(encabezado, "PNG", 0, 0, pageWidth, encAlto);
        doc.addImage(pie, "PNG", 0, pageHeight - pieAlto, pageWidth, pieAlto);
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

      // === Pie de página centrado con numeración total ===
      const totalPages = doc.internal.getNumberOfPages();

      for (let i = 1; i <= totalPages; i++) {
        doc.setPage(i);

        // Redibujar encabezado y pie gráfico
        doc.addImage(encabezado, "PNG", 0, 0, pageWidth, encAlto);
        doc.addImage(pie, "PNG", 0, pageHeight - pieAlto, pageWidth, pieAlto);

        // Texto centrado
        doc.setFont("helvetica", "italic");
        doc.setFontSize(8);
        doc.setTextColor("#444");

        const footerText =
          "Documento generado mediante tecnología de IA bajo la supervisión y aprobación de Netec.";
        const pageNum = `Página ${i} de ${totalPages}`;

        const footerX = pageWidth / 2;
        doc.text(footerText, footerX, pageHeight - 70, { align: "left" });
        doc.text(pageNum, footerX, pageHeight - 55, { align: "center" });
      }


      doc.save(`Seminario_${slugify(temarioLimpio?.nombre_curso)}.pdf`);
      setMensaje({ tipo: "ok", texto: "✅ PDF exportado correctamente" });
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: "❌ Error al generar PDF" });
    }
  };


  // ===== EXPORTAR YAML =====
  const exportarYAML = () => {
    if (!temario || !Array.isArray(temario.temario)) {
      setMensaje({ tipo: "error", texto: "No hay datos para exportar." });
      return;
    }

    const esPractica = (nombre = "") =>
      nombre.startsWith("Práctica:") || nombre.startsWith("Laboratorio:");

    // Convierte audiencia/prerrequisitos en listas YAML
    const toList = (v) => {
      if (Array.isArray(v)) return v.filter(Boolean);
      if (typeof v === "string") {
        return v
          .split(/\r?\n|;/)
          .map((s) => s.trim())
          .filter(Boolean);
      }
      return [];
    };

    // Mapear nivel a basic/intermediate/advanced
    const normalizarLevel = (raw) => {
      const v = String(raw || "").trim().toLowerCase();
      if (["basic", "intermediate", "advanced"].includes(v)) return v;

      // Soporta entradas comunes en español
      if (["básico", "basico"].includes(v)) return "basic";
      if (["intermedio"].includes(v)) return "intermediate";
      if (["avanzado"].includes(v)) return "advanced";

      // Heurística: si no viene, estimamos por duración
      const horas = Number(temario.horas_total_curso || 0);
      if (horas <= 16) return "basic";
      if (horas <= 32) return "intermediate";
      return "advanced";
    };

    // Bloom: si es práctica/lab => Aplicar. Si no, por duración.
    const calcularBloom = (sub) => {
      if (esPractica(sub.nombre || "")) return "Aplicar";
      const dur = Number(sub.tiempo_subcapitulo_min || 0);
      if (dur <= 20) return "Recordar";
      if (dur <= 40) return "Comprender";
      return "Analizar";
    };

    // Porcentaje teoría/práctica a nivel curso
    // (en tu UI el campo es "Porcentaje de teoría y práctica", normalmente representa teoría)
    const percentTheoryCurso = 60//Number(temario.porcentaje_teoria_practica || 0); //
    const percentPracticeCurso = 40//100 - percentTheoryCurso; //  
    
    // Horas totales del curso
    const hoursTotal = 2 //Number(temario.horas_total_curso || 0);

    // ✅ Corrección: theory usa percentTheory, practice usa percentPractice
    const hoursTheory = +(hoursTotal * percentTheoryCurso / 100).toFixed(2);
    const hoursPractice = +(hoursTotal * percentPracticeCurso / 100).toFixed(2);

    // ✅ Corrección: total_duration_minutes (suma de capítulos; fallback suma de subcapítulos)
    const totalDurationMinutesFromCaps = (temario.temario || []).reduce(
      (acc, cap) => acc + (Number(cap.tiempo_capitulo_min) || 0),
      0
    );

    const totalDurationMinutesFromSubs = (temario.temario || []).reduce((acc, cap) => {
      return (
        acc +
        (cap.subcapitulos || []).reduce(
          (s, sub) => s + (Number(sub.tiempo_subcapitulo_min) || 0),
          0
        )
      );
    }, 0);

    const totalDurationMinutes =
      totalDurationMinutesFromCaps > 0
        ? totalDurationMinutesFromCaps
        : totalDurationMinutesFromSubs;

    // ===============================
    // 📌 OBJETO YAML según plantilla_objetivo.yaml
    // ===============================
    const yamlObject = {
      course: {
        title: temario.nombre_curso || "",
        description: temario.descripcion_general || ".",
        level: normalizarLevel(temario.level || temario.nivel),
        audience: toList(temario.audiencia),
        prerequisites: toList(temario.prerrequisitos),
        total_duration_minutes: totalDurationMinutes, // ✅ ahora sí
      },

      language: "es", // (IDIOMA - si tu plantilla tiene otro valor fijo, cámbialo aquí por ese valor)

      learning_outcomes: temario.objetivos || "",

      hours_total: (totalDurationMinutes / 60).toFixed(2),
      hours_theory: hoursTheory,     // ✅ corregido
      hours_practice: hoursPractice, // ✅ corregido

      modules: (temario.temario || []).map((cap, capIndex) => {
        let theoryMin = 0;
        let practiceMin = 0;

        (cap.subcapitulos || []).forEach((sub) => {
          const dur = Number(sub.tiempo_subcapitulo_min || 0);
          esPractica(sub.nombre || "") ? (practiceMin += dur) : (theoryMin += dur);
        });

        const totalMin = theoryMin + practiceMin || 1;

        const module = {
          title: cap.capitulo || "",
          duration_minutes: Number(cap.tiempo_capitulo_min || totalMin),
          percent_theory: Math.round((theoryMin / totalMin) * 100),
          percent_practice: Math.round((practiceMin / totalMin) * 100),

          lessons: (cap.subcapitulos || []).map((sub, subIndex) => ({
            title: sub.nombre || "",
            duration_minutes: Number(sub.tiempo_subcapitulo_min || 0),
            bloom_level: calcularBloom(sub), // ✅ agregado
            topics: [`${capIndex + 1}.${subIndex + 1} ${sub.nombre || ""}`],
          })),
        };

        // lab_activities (solo si hay Práctica/Laboratorio)
        const labs = (cap.subcapitulos || [])
          .filter((s) => esPractica(s.nombre || ""))
          .map((s) => s.nombre);

        if (labs.length > 0) module.lab_activities = labs;

        return module;
      }),
    };

    // Serializador YAML controlado (igual que antes)
    const toYAML = (obj, indent = 0) => {
      const space = "  ".repeat(indent);

      if (Array.isArray(obj)) {
        return obj
          .map((item) => `${space}- ${toYAML(item, indent + 1).trimStart()}`)
          .join("\n");
      }

      if (obj !== null && typeof obj === "object") {
        return Object.entries(obj)
          .map(([key, value]) => {
            if (typeof value === "object" && value !== null) {
              return `${space}${key}:\n${toYAML(value, indent + 1)}`;
            }
            return `${space}${key}: ${value ?? ""}`;
          })
          .join("\n");
      }

      return `${space}${String(obj)}`;
    };

    const yamlContent = toYAML(yamlObject);

    const blob = new Blob([yamlContent], { type: "text/yaml;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Temario_${slugify(temario.nombre_curso)}.yaml`;
    a.click();
    URL.revokeObjectURL(url);

    setMensaje({ tipo: "ok", texto: "✅ YAML exportado correctamente" });
  };


  // === Exportar Excel ===
  const exportarExcel = () => {
    downloadExcelTemario(temarioLimpio);
    setMensaje({ tipo: "ok", texto: "✅ Excel exportado correctamente" });
  };

  // 🔹 Formatea minutos → "1 hr 8 min"
  const formatearDuracion = (minutos) => {
    const horas = Math.floor(minutos / 60);
    const mins = minutos % 60;
    if (horas > 0) {
      return `${horas} hr${horas > 1 ? "s" : ""}${mins > 0 ? ` ${mins} min` : ""}`;
    }
    return `${mins} min`;
  };


  // 🔹 Ajusta los tiempos de los subtemas distribuyendo de forma homogénea minuto a minuto
  const handleDuracionCapituloChange = (indexCap, nuevaDuracion) => {
    let valor = parseInt(nuevaDuracion, 10) || 0;
    if (valor < 1) valor = 1; //mínimo 1 minuto

    setTemario((prev) => {
      const nuevoTemario = JSON.parse(JSON.stringify(prev));
      const capitulos = nuevoTemario.temario || [];
      const capitulo = capitulos[indexCap];
      if (!capitulo || !Array.isArray(capitulo.subcapitulos)) return prev;

      const subtemas = capitulo.subcapitulos;
      const cantidad = subtemas.length;
      if (cantidad === 0) return prev;

      // 🔹 Cálculo base uniforme
      const minutosBase = Math.floor(valor / cantidad);
      let residuo = valor % cantidad;

      // 🔹 Reparto del residuo uno a uno hasta balancear
      subtemas.forEach((sub, i) => {
        sub.tiempo_subcapitulo_min = minutosBase + (residuo > 0 ? 1 : 0);
        if (residuo > 0) residuo--;
      });

      // 🔹 Actualizar el total del capítulo
      capitulo.tiempo_capitulo_min = valor;
      capitulos[indexCap] = capitulo;
      nuevoTemario.temario = capitulos;
      return nuevoTemario;
    });
  };

  return (
    <div className="seminario-editor-container">
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
          min="0.5"
          step="0.5"
          value={temario.horas_totales || ""}
          onChange={(e) => {
            const val = Math.max(parseFloat(e.target.value) || 0, 0.5); // ✅ mínimo 0.5h
            setTemario({ ...temario, horas_totales: val });
          }}
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
          <div className="duracion-capitulo">
            <label>🕒 Duración total:</label>
            <input
              type="number"
              min="1"
              value={cap.tiempo_capitulo_min || 0}
              onChange={(e) => handleDuracionCapituloChange(i, e.target.value)}
            />
            <span className="duracion-horas">
              {formatearDuracion(cap.tiempo_capitulo_min || 0)}
            </span>
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
                  onClick={() => eliminarTema(i, j)}
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
                  checked={exportTipo === "yaml"}
                  onChange={() => setExportTipo("yaml")}
                />{" "}
                Yaml
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
                  if (exportTipo === "pdf") {
                    exportarPDF(temario);
                  } else if (exportTipo === "excel") {
                    exportarExcel();
                  } else if (exportTipo === "yaml") {
                    exportarYAML();
                  }
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
