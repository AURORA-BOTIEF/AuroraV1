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
          a: "Ambos generadores comparten características, por eso están agrupados en el mismo botón. El Estándar y el Aumentado manejan proporciones similares entre teoría y práctica y son ideales para cursos técnicos o aplicados.",
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
          a: "Está pensado para sesiones cortas, como charlas o conferencias, donde se busca transmitir información rápida y clara sin desarrollar un curso completo.",
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
          a: "Define qué tipo de objetivos y actividades se incluirán, basándose en la Taxonomía de Bloom. Esto afecta la profundidad del aprendizaje y las habilidades que se desarrollarán.",
        },
        {
          q: "¿Qué significa el campo “Sector / Audiencia” y por qué es importante?",
          a: "Indica a quién va dirigido el curso (por ejemplo, desarrolladores, sector financiero). Esto permite adaptar el lenguaje, ejemplos y profundidad del contenido.",
        },
        {
          q: "¿Para qué sirve el campo “Enfoque Adicional”?",
          a: "Puedes dar detalles extra, como 'orientado a patrones de diseño'. Esto ayuda a que el temario sea más alineado a tus objetivos específicos.",
        },
        {
          q: "¿Qué es el “Syllabus Base” y cómo ayuda a la IA?",
          a: "Permite agregar el contenido de un temario oficial o esquema base para que la IA lo use como referencia al generar uno nuevo.",
        },
        {
          q: "¿Cómo se calcula el total de horas del curso?",
          a: "El total se calcula automáticamente según el número de sesiones y las horas por sesión que definas.",
        },
        {
          q: "¿Cuál es la diferencia entre “Saber Hacer” y “Certificación” en el tipo de objetivo?",
          a: "Saber Hacer: habilidades prácticas. Certificación: enfoque en preparación para examen oficial con teoría y práctica.",
        },
        {
          q: "¿Qué pasa si doy clic en “Guardar Versión”?",
          a: "Guarda una copia del temario generado para consultarlo después en 'Ver Versiones Guardadas'.",
        },
        {
          q: "¿Es obligatorio escribir una nota al guardar la versión?",
          a: "No, la nota es opcional. Puedes usarla para identificar la versión más fácilmente, como 'Versión inicial' o 'Ajustada para curso X'.",
        },
        {
          q: "¿Puedo editar el temario después de guardarlo?",
          a: "Sí, puedes editarlo desde la sección 'Ver Versiones Guardadas'.",
        },
      ],
    },
  ];

  return (
    <div className="faq-container">
      <h2 className="faq-title">Centro de FAQs</h2>
      {data.map((section, sIndex) => (
        <div key={sIndex} className="faq-section">
          <h3 className="faq-section-title">{section.section}</h3>
          {section.questions.map((q, index) => (
            <div key={index} className="faq-item">
              <div className="faq-question" onClick={() => toggleFAQ(`${sIndex}-${index}`)}>
                <span>{q.q}</span>
                <button
                  className={`faq-toggle ${activeIndex === `${sIndex}-${index}` ? "open" : ""}`}
                >
                  {activeIndex === `${sIndex}-${index}` ? "−" : "+"}
                </button>
              </div>
              {activeIndex === `${sIndex}-${index}` && (
                <div className="faq-answer">
                  <p>{q.a}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

export default FAQ; 