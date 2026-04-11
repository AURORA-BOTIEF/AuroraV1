// src/components/EditorTemarioPage.jsx
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import EditorDeTemario from "./EditorDeTemario.jsx";

function EditorTemarioPage() {
  const { versionId } = useParams();
  const [temarioData, setTemarioData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const onSave = async (contenido, nota) => {
    try {
      const token = sessionStorage.getItem("id_token");
      const res = await fetch(
        "https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            versionId,
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

      if (!res.ok) {
        throw new Error((await res.json()).error || "Error al guardar versión");
      }
      console.log("✅ Versión guardada correctamente");
    } catch (err) {
      console.error("❌ Error al guardar versión:", err);
    }
  };

  // 🔹 Nuevo: cargar versión desde Dynamo
  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const token = sessionStorage.getItem("id_token");
        const res = await fetch(
          `https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones?versionId=${versionId}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
          }
        );

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Error al obtener versión");

        console.log("📦 Versión cargada:", data);
        setTemarioData(data.contenido || data);
      } catch (err) {
        console.error("❌ Error al cargar versión:", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchVersion();
  }, [versionId]);

  if (isLoading) return <p>Cargando versión...</p>;

  return (
    <EditorDeTemario
      temarioInicial={temarioData}
      onSave={onSave}
      isLoading={isLoading}
    />
  );
}

export default EditorTemarioPage;
