export async function downloadExcelTemario() {
  console.warn(
    "downloadExcelTemario deshabilitado: implementación incompatible con frontend build (Vite)"
  );
}

/*
//import ExcelJS from "exceljs";
//import { saveAs } from "file-saver";

export async function downloadExcelTemario(temario) {
  const workbook = new ExcelJS.Workbook();

  // ============================================================
  // 📌 HOJA 1 — PORTADA
  // ============================================================
  const portada = workbook.addWorksheet("Portada");

  portada.mergeCells("A1:D1");
  portada.getCell("A1").value = temario.nombre_curso || "Nombre del Curso";
  portada.getCell("A1").font = { size: 20, bold: true };
  portada.getCell("A1").alignment = { horizontal: "center" };

  portada.addRow([]);
  portada.addRow(["Duración total (horas):", temario.horas_total_curso || 0]);

  portada.addRow([]);
  portada.addRow(["Descripción General:"]);
  portada.addRow([temario.descripcion_general || ""]);

  portada.addRow([]);
  portada.addRow(["Audiencia:"]);
  portada.addRow([temario.audiencia || ""]);

  portada.addRow([]);
  portada.addRow(["Prerrequisitos:"]);
  portada.addRow([temario.prerrequisitos || ""]);

  portada.addRow([]);
  portada.addRow(["Objetivos del Curso:"]);
  portada.addRow([temario.objetivos || ""]);

  portada.columns = [
    { width: 40 },
    { width: 40 },
    { width: 20 },
    { width: 20 }
  ];

  // ============================================================
  // 📌 HOJA 2 — TEMARIO DETALLADO
  // ============================================================
  const hojaTemario = workbook.addWorksheet("Temario Detallado");

  hojaTemario.columns = [
    { header: "Capítulo", key: "capitulo", width: 40 },
    { header: "Objetivos del Capítulo", key: "objetivos", width: 50 },
    { header: "Duración (min)", key: "duracion", width: 15 },
    { header: "Tema", key: "tema", width: 40 },
    { header: "Sesión", key: "sesion", width: 10 },
    { header: "Duración Tema (min)", key: "dur_tema", width: 20 },
  ];

  // 📌 Estilo del encabezado
  hojaTemario.getRow(1).font = { bold: true };
  hojaTemario.getRow(1).alignment = { horizontal: "center" };

  // ============================================================
  // 📌 Cargar capítulos y subtemas
  // ============================================================
  temario.temario.forEach((cap, i) => {
    const objetivosTexto = Array.isArray(cap.objetivos_capitulo)
      ? cap.objetivos_capitulo.join(", ")
      : cap.objetivos_capitulo || "";

    hojaTemario.addRow({
      capitulo: `Capítulo ${i + 1}: ${cap.capitulo}`,
      objetivos: objetivosTexto,
      duracion: cap.tiempo_capitulo_min,
      tema: "",
      sesion: "",
      dur_tema: ""
    });

    // Estilo capítulo
    const fila = hojaTemario.lastRow;
    fila.font = { bold: true, color: { argb: "005A9C" } };

    cap.subcapitulos.forEach((sub, j) => {
      hojaTemario.addRow({
        capitulo: "",
        objetivos: "",
        duracion: "",
        tema: `${i + 1}.${j + 1} ${sub.nombre}`,
        sesion: sub.sesion,
        dur_tema: sub.tiempo_subcapitulo_min
      });
    });

    hojaTemario.addRow([]);
  });

  // ============================================================
  // 📌 EXPORTAR ARCHIVO
  // ============================================================
  const buffer = await workbook.xlsx.writeBuffer();

  saveAs(
    new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
    `Temario_${temario.nombre_curso || "curso"}.xlsx`
  );
}
*/