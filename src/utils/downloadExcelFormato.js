// src/utils/downloadExcelFormato.js
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadExcelTemarioConPlantilla(temario) {
  const ExcelJSmod = await import("exceljs");
  const ExcelJS = ExcelJSmod.default ?? ExcelJSmod; // compat ESM/CJS

  // 1) Cargar plantilla
  const resp = await fetch("/templates/Ejemplo_formato.xlsx");
  const templateBuffer = await resp.arrayBuffer();

  const wb = new ExcelJS.Workbook();
  await wb.xlsx.load(templateBuffer);
  const ws = wb.getWorksheet("Hoja1") ?? wb.worksheets[0];

  // 2) Inyectar “celdas dinámicas” (según tu mapeo)
  ws.getCell("B2").value = `CURSO: ${temario?.nombre_curso ?? ""}`;
  ws.getCell("B3").value = `Versión de la tecnología: ${temario?.version_tecnologia ?? ""}`;
  ws.getCell("B4").value =
    `Horas: ${temario?.horas_totales ?? ""}    ` +
    `Sesiones: ${temario?.numero_sesiones ?? ""}    ` +
    `EOL: ${temario?.EOL ?? ""}`;

  ws.getCell("B6").value = temario?.descripcion_general ?? "";
  ws.getCell("B7").value = temario?.objetivos ?? "";
  ws.getCell("B8").value = temario?.audiencia ?? "";
  ws.getCell("B9").value = temario?.prerrequisitos ?? "";

  // En tu plantilla, el % está en D10 (B10 es el label)
  ws.getCell("D10").value = temario?.porcentaje_teoria_practica_general ?? "";

  // 3) Temario desde fila 13 (B12 son headers)
  // Tip: Usa la fila 13 como “estilo capítulo” y la 14 como “estilo subcapítulo”
  const startRow = 13;
  let row = startRow;
  let totalMin = 0;

  // Limpia zona base (por si la plantilla trae capítulos de ejemplo)
  for (let r = startRow; r <= 24; r++) {
    ["B", "C", "D", "E"].forEach((col) => (ws.getCell(`${col}${r}`).value = null));
  }

  const caps = temario?.temario ?? [];
  for (let i = 0; i < caps.length; i++) {
    const cap = caps[i];

    // Si te quedas sin espacio, duplica una fila “subcapítulo” para mantener bordes/estilos
    if (row > 24) ws.duplicateRow(14, 1, true);

    // Fila capítulo (estilo fila 13)
    ws.getCell(`B${row}`).value = `${i + 1}. ${cap?.capitulo ?? `Capítulo ${i + 1}`}`;
    // Puedes forzar negrita si quieres, pero idealmente ya viene de la plantilla:
    // ws.getCell(`B${row}`).font = { ...ws.getCell("B13").font };

    row++;

    const subs = Array.isArray(cap?.subcapitulos) ? cap.subcapitulos : [];
    for (const sub of subs) {
      if (row > 24) ws.duplicateRow(14, 1, true);

      const nombre = typeof sub === "object" ? (sub?.nombre ?? "") : (sub ?? "");
      const sesion = typeof sub === "object" ? (sub?.sesion ?? "") : "";
      const minutos = typeof sub === "object" ? Number(sub?.tiempo_subcapitulo_min ?? 0) : 0;

      totalMin += minutos;

      ws.getCell(`B${row}`).value = `   ${nombre}`; // indent simple
      ws.getCell(`C${row}`).value = sesion || "";
      ws.getCell(`D${row}`).value = minutos ? `${minutos} min` : "";
      ws.getCell(`E${row}`).value = ""; // Observaciones vacío

      row++;
    }
  }

  // 4) Tiempo total (en la plantilla el label está en C25, el valor lo pones al lado)
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  ws.getCell("D25").value = `${h} h ${m} min`;

  // 5) Descargar
  const out = await wb.xlsx.writeBuffer();
  const blob = new Blob([out], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });

  const filenameBase = (temario?.nombre_curso || "temario")
    .toString().trim().replace(/\s+/g, "_").replace(/[^\w\-_.]/g, "");
  const date = new Date().toISOString().slice(0, 10);

  downloadBlob(blob, `${filenameBase}_${date}.xlsx`);
}