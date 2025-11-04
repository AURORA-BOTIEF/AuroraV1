// src/components/EditorTemarioPage.jsx
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import EditorDeTemario from "./EditorDeTemario.jsx";

function EditorTemarioPage() {
  const { versionId } = useParams(); // viene desde navigate(`/editor-temario/${v.versionId}`);
  const [temario, setTemario] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // ✅ Cargar versión desde la API al entrar
  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const token = localStorage.getItem("id_token");
        const res = await fetch(
          `https://eim01evqg7.execute-api.us-east-1.amazonaws.com/versiones/versiones?id=${versionId}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!res.ok) {
          throw new Error("Error al cargar la versión");
        }

        const data = await res.json();
        console.log("✅ Versión cargada:", data);
        setTemario(data.contenido); // Usa el campo 'contenido' que viene de DynamoDB
      } catch (error) {
        console.error("❌ Error cargando versión:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchVersion();
  }, [versionId]);

  // ✅ Guardar versión editada
  const onSave = async (contenido, nota) => {
    try {
      const token = localStorage.getItem("id_token");
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

  // 🧭 Mostrar carga o editor
  if (isLoading) {
    return <div style={{ padding: "2rem" }}>Cargando versión...</div>;
  }

  return (
    <EditorDeTemario
      temarioInicial={temario}
      onSave={onSave}
      isLoading={isLoading}
    />
  );
}

export default EditorTemarioPage;
