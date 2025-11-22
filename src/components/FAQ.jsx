// src/components/FAQ.jsx
import React, { useState } from "react";
import { Link } from "react-router-dom";
import "./FAQ.css";

const FAQ = () => {
  const [activeIndex, setActiveIndex] = useState(null);

  const toggleFAQ = (index) => {
    setActiveIndex(activeIndex === index ? null : index);
  };

  const data = [
    {
      section: "Sobre el uso de IA",
      questions: [
        {
          q: "¿El temario generado por THOR es definitivo o debo revisarlo?",
          a: "No es definitivo. El contenido generado por THOR es una propuesta base que debes revisar, adaptar y complementar según tus objetivos y el contexto de grupo.",
        },
        {
          q: "¿Por qué debo verificar la información generada por la IA?",
          a: "Porque la IA puede generar datos incorrectos, incompletos o desactualizados. Verificar la información garantiza que el temario sea preciso, relevante y confiable para tus estudiantes.",
        },
        {
          q: "¿La IA garantiza que el contenido esté libre de sesgos?",
          a: "No. Aunque se busca minimizar sesgos, la IA puede reflejar patrones presentes en los datos con los que fue entrenada. Por eso es importante revisar y ajustar el contenido para asegurar que sea inclusivo y respetuoso.",
        },
        {
          q: "¿Qué significa que el contenido es una “propuesta base”?",
          a: "Significa que el temario generado es un punto de partida para tu diseño educativo. No sustituye tu criterio como docente, sino que te ayuda a ahorrar tiempo y organizar ideas.",
        },
        {
          q: "¿Es seguro ingresar datos personales en la plataforma?",
          a: "No. Por seguridad y privacidad, evita ingresar datos personales, sensibles o confidenciales. THOR está diseñado para trabajar con información general, no con datos privados.",
        },
        {
          q: "¿Qué hago si encuentro errores en el temario generado?",
          a: "Simplemente corrige, edita o elimina la información incorrecta. El contenido es 100% editable para que lo adaptes a tus necesidades.",
        },
      ],
    },
    {
      section: "Sobre los tipos de generadores de temarios",
      questions: [
        {
          q: "¿Por qué el Generador de Temario Estándar y el Aumentado están en el mismo botón y cuáles son sus diferencias?",
          a: `Ambos generadores comparten características:
          • Propósito común: crean temarios completos con teoría y práctica.
          • Proporción: 30% teoría y 70% práctica.
          • Duración: diseñados para cursos largos.
          • Elementos incluidos: objetivos, temario, prerrequisitos, público objetivo y guías de laboratorio.`,
        },
        {
          q: "¿Para qué sirve el Generador de Temario Knowledge Transfer?",
          a: "Está diseñado para compartir conocimiento teórico. Genera temarios 100% teóricos, sin prácticas ni laboratorios.",
        },
        {
          q: "¿Qué características tiene el Generador de Temario Taller Práctico?",
          a: "Crea temarios 100% prácticos, enfocados en ejercicios y laboratorios. Perfecto para cursos donde los estudiantes aprenden haciendo.",
        },
        {
          q: "¿Cuándo debo usar el Generador de Temario Seminarios?",
          a: "Está pensado para sesiones cortas, como charlas o conferencias. Su objetivo es transmitir información rápida y clara sin desarrollar un curso completo.",
        },
      ],
    },
    {
      section: "Sobre el llenado del formulario para generar temarios",
      questions: [
        {
          q: "¿Es obligatorio llenar el nombre del Preventa Asociado y el Asesor Comercial?",
          a: "No, estos campos son opcionales. Solo agrégalos si quieres que el temario esté vinculado a un responsable comercial o preventa.",
        },
        {
          q: "¿Cómo influye el nivel de dificultad en el temario generado?",
          a: `El nivel define los objetivos y actividades según la Taxonomía de Bloom:
          • Básico: Recordar y Comprender.
          • Intermedio: Aplicar y Analizar.
          • Avanzado: Evaluar y Crear.`,
        },
        {
          q: "¿Qué significa el campo “Sector / Audiencia” y por qué es importante?",
          a: "Define a quién va dirigido el curso, lo que permite ajustar lenguaje, ejemplos y profundidad.",
        },
        {
          q: "¿Para qué sirve el campo “Enfoque Adicional”?",
          a: "Permite agregar detalles específicos, como 'orientado a patrones de diseño', para personalizar el enfoque del temario.",
        },
        {
          q: "¿Qué es el “Syllabus Base” y cómo ayuda a la IA?",
          a: "Sirve como referencia para generar un temario más alineado con un esquema oficial.",
        },
        {
          q: "¿Cómo se calcula el total de horas del curso?",
          a: "Se calcula automáticamente según el número de sesiones y las horas por sesión.",
        },
        {
          q: "¿Cuál es la diferencia entre “Saber Hacer” y “Certificación” en el tipo de objetivo?",
          a: "Saber Hacer: habilidades prácticas. Certificación: preparación para exámenes oficiales.",
        },
        {
          q: "¿Qué pasa si el temario generado no coincide con mis expectativas?",
          a: "Puedes editarlo libremente. Es solo un punto de partida.",
        },
        {
          q: "¿Qué pasa si doy clic en “Guardar Versión”?",
          a: "Guarda una copia del temario para consultarlo después en 'Ver Versiones Guardadas'.",
        },
        {
          q: "¿Es obligatorio escribir una nota al guardar la versión?",
          a: "No, la nota es opcional. Úsala para agregar comentarios o identificar versiones fácilmente.",
        },
        {
          q: "¿Puedo editar el temario después de guardarlo?",
          a: "Sí. En 'Ver Versiones Guardadas' puedes abrir y modificar cualquier versión guardada.",
        },
      ],
    },
  ];

  return (
    <div className="faq-container">
      <div className="faq-header">
        <Link to="/" className="faq-back">← Volver al menú principal</Link>
      </div>
      <h2 className="faq-title">Centro de FAQs</h2>
      {data.map((section, sIndex) => (
        <div key={sIndex} className="faq-section">
          <h3 className="faq-section-title">{section.section}</h3>
          {section.questions.map((item, index) => {
            const key = `${sIndex}-${index}`;
            const isActive = activeIndex === key;
            return (
              <div key={key} className={`faq-item ${isActive ? "active" : ""}`}>
                <div
                  className="faq-question"
                  onClick={() => toggleFAQ(key)}
                >
                  <span>{item.q}</span>
                  <button className="faq-toggle">
                    {isActive ? "−" : "+"}
                  </button>
                </div>
                {isActive && <p className="faq-answer">{item.a}</p>}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export default FAQ;