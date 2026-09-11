# Actividades Agosto — Thor

A continuación se describen las actividades de desarrollo de software realizadas durante el mes de agosto de 2026 para el proyecto Thor (Aurora), correspondientes a las contribuciones en el repositorio GitHub y a los despliegues de infraestructura con AWS SAM y AWS Amplify.

**Resumen del mes.** Se publicaron 23 cambios en GitHub (rama `testing`), 31 actualizaciones exitosas del servidor backend y 23 publicaciones de la aplicación web en el ambiente de pruebas. Hubo 12 días con trabajo registrado. El ambiente de producción (`main`) no se actualizó en agosto: todo el trabajo quedó publicado en pruebas (`testing`).

| # | Fecha | Actividad | Descripción | Horas |
|---|-------|-----------|-------------|-------|
| 1 | 03-ago-2026 | Publicación y despliegue de las mejoras de laboratorios | Se subió a GitHub y se publicó en el ambiente de pruebas el trabajo de calidad de laboratorios (alineación con los manuales oficiales, continuidad entre prácticas correlativas y revisión automática de calidad). Incluye despliegue backend con AWS SAM y publicación de la web | 1,5 |
| 2 | 04-ago-2026 | Ajuste y redespliegue del servidor | Nueva actualización del backend en AWS para aplicar ajustes de configuración posteriores a la publicación del día anterior | 1,0 |
| 3 | 06-ago-2026 | Evitar cortes al iniciar un curso con PDFs de referencia | Cuando el usuario carga manuales en PDF, el sistema ya no se queda esperando hasta fallar. El archivo se procesa en segundo plano, se guarda el texto extraído y la pantalla muestra un aviso de éxito sin bloquearse | 2,0 |
| 4 | 06-ago-2026 | Más tiempo de procesamiento para laboratorios | Se amplió el tiempo máximo de las funciones del servidor (hasta 15 minutos) y se redujo el tamaño de cada lote de generación (de 10 a 5) para que las guías largas no se interrumpan a mitad de camino | 1,5 |
| 5 | 06-ago-2026 | Reparar el armado de libros y poder continuar después de la teoría | Se corrigió el componente que arma el libro del curso y se habilitó retomar un trabajo desde la parte de laboratorios, sin volver a generar toda la teoría ni las imágenes | 2,0 |
| 6 | 10-ago-2026 | Despliegues de ajuste del servidor | Tres actualizaciones del backend para afinar el flujo de generación. Ese día no hubo commit nuevo en GitHub: se publicaron ajustes ya trabajados en el ambiente | 1,5 |
| 7 | 11-ago-2026 | Despliegue de seguimiento del backend | Actualización adicional del servidor para consolidar los ajustes de la semana | 1,0 |
| 8 | 12-ago-2026 | Presentaciones según la duración real del curso | El número de diapositivas dejó de ser un tope fijo. Ahora se calcula según las horas del curso, de modo que un curso largo recibe más contenido visual y uno corto no se infla de más | 2,0 |
| 9 | 12-ago-2026 | Datos del curso en todo el flujo y límites de tamaño | La duración y demás datos del curso viajan por todo el proceso de generación. Se evitó que respuestas demasiado grandes hagan fallar el servidor. Mejoró la detección de qué lecciones son de laboratorio | 2,0 |
| 10 | 12-ago-2026 | Despliegues SAM y corrección de un fallo en el flujo | Un intento de actualización se revirtió solo porque un paso del flujo automático quedó inalcanzable. Se corrigió la definición del flujo y se republicó con éxito el mismo día | 1,5 |
| 11 | 13-ago-2026 | Reanudar presentaciones que se quedaron a medias | Si la generación de diapositivas se interrumpe, ahora se puede continuar desde donde quedó, con tiempos de espera más holgados | 2,0 |
| 12 | 14-ago-2026 | Visor de presentaciones más confiable | Se corrigió que las diapositivas no se vieran en modo presentación, que el visor mostrara una versión vieja guardada en caché, un error de conexión al recargar y que no apareciera el aviso de éxito al terminar | 2,0 |
| 13 | 14-ago-2026 | Modelo de IA más reciente y elección de proveedor para presentaciones | Se actualizó el modelo de OpenAI a gpt-5.6-terra y se agregó un selector para elegir con qué proveedor de IA (Amazon, Google u OpenAI) generar las presentaciones | 2,0 |
| 14 | 14-ago-2026 | Restaurar modelos de Amazon y el validador de contenido | Se reincorporaron definiciones de modelo de Amazon que habían quedado fuera y se alineó el validador de contenido para que el flujo no se detenga por un desajuste de respuesta | 1,5 |
| 15 | 14-ago-2026 | Una sola dirección correcta del servicio | Se unificó la dirección del API para dejar de apuntar a ambientes viejos. También se corrigió la carga de libros cuando el nombre del proyecto tiene caracteres especiales | 1,5 |
| 16 | 14-ago-2026 | Lista de proyectos ordenada por fecha real | Los cursos en el listado se ordenan según la fecha verdadera de los archivos, no por un dato aproximado | 1,0 |
| 17 | 20-ago-2026 | Presentaciones HTML de alta fidelidad y avisos por correo | El generador de infografías pasa a un enfoque HTML primero (mejor fidelidad visual al convertir a PowerPoint) y las notificaciones del flujo incluyen el correo del usuario que lanzó el trabajo | 2,5 |
| 18 | 27-ago-2026 | Avisos cuando falla una presentación | Si algo sale mal al generar presentaciones, el usuario recibe una notificación de error clara en lugar de un silencio | 1,5 |
| 19 | 28-ago-2026 | Demostraciones del instructor en laboratorios | El sistema distingue las prácticas que hace el alumno de las demostraciones que realiza el instructor. Teoría, guía de laboratorio y diapositivas se formatean de manera distinta según el caso | 2,5 |
| 20 | 31-ago-2026 | Turnos para no saturar los servicios de IA | Si varios cursos o presentaciones se lanzan a la vez con el mismo proveedor de IA (Amazon, Google u OpenAI), se encolan en lugar de chocar entre sí y fallar. Cada trabajo espera su turno de forma automática | 2,5 |
| | | | **Total** | **35,0** |

## Publicaciones del mes

### GitHub (`AURORA-BOTIEF/AuroraV1`)

- 23 commits en la rama `testing`, todos de Juan.
- 0 pull requests abiertos o fusionados en agosto. El trabajo se publicó directo a `testing`.
- La rama `main` (producción web) no recibió commits en agosto.
- Archivos distintos tocados: 42.

### AWS SAM (servidor backend)

- Stack: `crewai-course-generator-stack` (región `us-east-1`).
- 31 actualizaciones exitosas y 1 reversión automática (12-ago, corregida el mismo día).
- Días con despliegue: 3, 4, 6, 10, 11, 12, 14, 20, 27, 28 y 31 de agosto.
- El 12-ago un paso del flujo automático (`CheckContentTypeForSlides`) quedó inalcanzable; el sistema revirtió solo y se republicó corregido minutos después.

### AWS Amplify (aplicación web)

- Aplicación `Aurora`, rama `testing`: 23 publicaciones, todas exitosas.
- La rama `main` (marcada como producción) no se publicó en agosto; su última publicación fue el 25-may-2026.

## Cómo leer este reporte

- **GitHub** es el registro de los cambios de código (el “qué se hizo”).
- **SAM** es la publicación de esos cambios en el servidor que genera cursos, laboratorios y presentaciones.
- **Amplify** es la publicación de la pantalla que ven instructores y operadores.
- En agosto el trabajo se entregó al **ambiente de pruebas** (`testing`). Llevarlo a producción implica fusionar `testing` hacia `main` y publicar esa rama.
