import express from "express";
import ExcelJS from "exceljs";
import cors from "cors";

const app = express();
app.use(cors());
app.use(express.json({ limit: "10mb" }));

app.post("/export/excel", async (req, res) => {
  try {
    const temario = req.body;

    const workbook = new ExcelJS.Workbook();

    // =====================================================
    // HOJA 1 – PORTADA
    // =====================================================
    const portada = workbook.addWorksheet("Portada");

    portada.mergeCells("A1:D1");
    portada.getCell("A1").value = temario.nombre_curso;
    portada.getCell("A1").font = { size: 22, bold: true };
    portada.getCell("A1").alignment = { horizontal: "center" };

    portada.addRow([]);
    portada.addRow(["Duración total (horas)", temario.horas_total_curso]);
    portada.addRow([]);
    portada.addRow(["Descripción General"]);
    portada.addRow([temario.descripcion_general]);
    portada.addRow([]);
    portada.addRow(["Audiencia"]);
    portada.addRow([temario.audiencia]);
    portada.addRow([]);
    portada.addRow(["Prerrequisitos"]);
    portada.addRow([temario.prerrequisitos]);
    portada.addRow([]);
    portada.addRow(["Objetivos"]);
    portada.addRow([temario.objetivos]);

    portada.columns = [
      { width: 30 },
      { width: 80 },
      { width: 20 },
      { width: 20 }
    ];

    // =====================================================
    // HOJA 2 – TEMARIO DETALLADO
    // =====================================================
    const hoja = workbook.addWorksheet("Temario");

    hoja.columns = [
      { header: "Capítulo", width: 40 },
      { header: "Objetivos", width: 50 },
      { header: "Duración Capítulo", width: 20 },
      { header: "Tema", width: 40 },
      { header: "Sesión", width: 10 },
      { header: "Duración Tema", width: 20 }
    ];

    hoja.getRow(1).font = { bold: true };

    temario.temario.forEach((cap, i) => {
      const filaCap = hoja.addRow([
        `Capítulo ${i + 1}: ${cap.capitulo}`,
        Array.isArray(cap.objetivos_capitulo)
          ? cap.objetivos_capitulo.join(", ")
          : cap.objetivos_capitulo,
        cap.tiempo_capitulo_min,
        "",
        "",
        ""
      ]);

      filaCap.font = { bold: true };
      filaCap.fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb: "D9EDF7" }
      };

      cap.subcapitulos.forEach((sub, j) => {
        hoja.addRow([
          "",
          "",
          "",
          `${i + 1}.${j + 1} ${sub.nombre}`,
          sub.sesion,
          sub.tiempo_subcapitulo_min
        ]);
      });

      hoja.addRow([]);
    });

    // =====================================================
    // RESPUESTA
    // =====================================================
    res.setHeader(
      "Content-Type",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    );
    res.setHeader(
      "Content-Disposition",
      `attachment; filename=Temario_${temario.nombre_curso}.xlsx`
    );

    await workbook.xlsx.write(res);
    res.end();

  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Error generando Excel" });
  }
});

app.listen(3001, () => {
  console.log("API Excel corriendo en http://localhost:3001");
});