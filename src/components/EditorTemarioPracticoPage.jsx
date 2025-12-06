// src/components/EditorTemarioPracticoPage.jsx
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import EditorDeTemario_Practico from "./EditorDeTemario_Practico.jsx";

const LIST_URL = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-practico/list";

// 🔸 helper seguro
const safeParse = (v) => {
  if (typeof v !== "string") return v;
  try { return JSON.parse(v); } catch { return null; }
};

// 🔸 normalizador MUY ligero para cubrir alias de campos
const normalizeContenido = (raw) => {
  const c = typeof raw === "string" ? safeParse(raw) : (raw || {});
  if (!c || typeof c !== "object") return {};

  return {
    // alias frecuentes
    nombre_curso: c.nombre_curso ?? c.tema_curso ?? "",
    tecnologia: c.tecnologia ?? "",
    asesor_comercial: c.asesor_comercial ?? "",
    nombre_preventa: c.nombre_preventa ?? "",
    enfoque: c.enfoque ?? "General",
    horas_total_curso: c.horas_total_curso ?? c.horas_totales ?? 0,
    descripcion_general: c.descripcion_general ?? c.descripcion ?? "",
    audiencia: c.audiencia ?? c.dirigido_a ?? "",
    prerrequisitos: c.prerrequisitos ?? c.requisitos ?? "",
    objetivos: c.objetivos ?? "",
    // temario/capitulos
    temario: Array.isArray(c.temario)
      ? c.temario
      : (Array.isArray(c.capitulos) ? c.capitulos : []),
  };
};

function EditorTemarioPracticoPage() {
  const { cursoId, versionId } = useParams();
  const [temarioData, setTemarioData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const onSave = async (contenido, nota) => {
    try {
      const token = sessionStorage.getItem("id_token");
      const res = await fetch(
        "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-practico",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            cursoId, // ✅ el backend genera versionId
            contenido,
            nota_version: nota || `Guardado el ${new Date().toISOString()}`,
            nombre_curso: contenido?.nombre_curso || contenido?.tema_curso || "Sin título",
            tecnologia: contenido?.tecnologia || "",
            asesor_comercial: contenido?.asesor_comercial || "",
            nombre_preventa: contenido?.nombre_preventa || "",
            enfoque: contenido?.enfoque || "General",
            fecha_creacion: new Date().toISOString(),
          }),
        }
      );
      if (!res.ok) throw new Error((await res.json()).error || "Error al guardar versión");
      console.log("✅ Versión guardada correctamente");
    } catch (err) {
      console.error("❌ Error al guardar versión:", err);
    }
  };

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        setIsLoading(true);
        const token = sessionStorage.getItem("id_token");

        // ⚠️ El filtro por id puede ser sensible a may/minus.
        // Si no devuelve nada, quita el query y filtra por versionId en cliente.
        const url = `${LIST_URL}?id=${encodeURIComponent(cursoId)}`;
        const res = await fetch(url, {
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`);

        const items = Array.isArray(data) ? data : [];
        const match = items.find(v => String(v.versionId) === String(versionId));

        if (!match) throw new Error("Versión no encontrada para este curso.");

        // 🔸 AQUI está el fix: parsea si viene string y normaliza alias
        const contenido =
          normalizeContenido(match.contenido ?? match);

        console.log("📦 Versión cargada (normalizada):", contenido);
        setTemarioData(contenido);
      } catch (err) {
        console.error("❌ Error al cargar versión:", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchVersion();
  }, [cursoId, versionId]);

  if (isLoading) return <p>Cargando versión...</p>;
  if (!temarioData) return <p>No se pudo cargar la versión.</p>;

  return (
    <EditorDeTemario_Practico
      temarioInicial={temarioData}
      onSave={onSave}
      isLoading={isLoading}
    />
  );
}

export default EditorTemarioPracticoPage;
