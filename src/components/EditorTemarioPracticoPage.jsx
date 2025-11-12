// src/components/EditorTemarioPracticoPage.jsx
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import EditorDeTemario_Practico from "./EditorDeTemario_Practico.jsx";

// Endpoints
const LIST_URL = "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-practico/list";

function EditorTemarioPracticoPage() {
  const { cursoId, versionId } = useParams();
  const [temarioData, setTemarioData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Guardar versión desde el editor
  const onSave = async (contenido, nota) => {
    try {
      const token = localStorage.getItem("id_token");
      const res = await fetch(
        "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones-practico",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            // ✅ IMPORTANTE: manda cursoId, el backend genera versionId
            cursoId,
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

  // Cargar versión desde DynamoDB
  useEffect(() => {
    const fetchVersion = async () => {
      try {
        setIsLoading(true);
        const token = localStorage.getItem("id_token");

        // ✅ Estrategia robusta: usa el endpoint /list y filtra por versionId
        const res = await fetch(`${LIST_URL}?id=${encodeURIComponent(cursoId)}`, {
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`);

        const items = Array.isArray(data) ? data : [];
        const version = items.find(v => v.versionId === versionId);

        if (!version) throw new Error("Versión no encontrada para este curso.");
        setTemarioData(version.contenido || version);
        console.log("📦 Versión cargada:", version);
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
