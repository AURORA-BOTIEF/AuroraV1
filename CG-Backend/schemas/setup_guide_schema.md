# Schema — Setup Guide (SUG) de Thor

Contrato de datos que produce `setup_guide_builder` y consume la plantilla PDF
(`setup_guide_template.py`). El documento es **determinista**: se construye a partir
del outline, el `lab-master-plan.json` y los laboratorios ya generados. Thor **no
inventa** información: cualquier dato no confirmado se emite como marcador visible
(`[VERSIÓN POR VALIDAR]`, `[ENLACE OFICIAL]`, `[REGIÓN POR DEFINIR]`, etc.).

## Ubicación de salida

```
{project_folder}/setupguide/setup-guide.json
{project_folder}/setupguide/Setup_Guide.pdf
```

## Estructura

```jsonc
{
  "metadata": {
    "project_folder": "string",
    "generated_at": "ISO-8601",
    "course_title": "string",
    "course_key": "string | [CLAVE COMPLETA]",
    "version": "string | [V1.0]",
    "status": "BORRADOR",
    "last_validation": "string | [FECHA DE VALIDACIÓN]",
    "source": { "outline": "key|none", "master_plan": "key|none", "labs": ["key", "..."] },
    "placeholders_count": 0
  },
  "identification": {
    "title": "string",
    "key": "string",
    "version": "string",
    "status": "string",
    "description": "string",
    "links": [
      { "label": "Repositorio GitHub", "url": "string", "status": "Verificado|Por confirmar" }
    ]
  },
  "previous_knowledge": {
    "knowledge": ["string"],
    "accounts": ["string"],
    "licenses": ["string"],
    "permissions": ["string"],
    "network": ["string"],          // dominios, puertos, proxy, VPN
    "timing": ["string"]            // momento en que cada acceso debe estar disponible
  },
  "infrastructure": {
    "hardware": [
      { "component": "string", "minimum": "string", "recommended": "string", "status": "string" }
    ],
    "counters": [
      { "value": "16 GB", "label": "RAM" }
    ],
    "virtual_machines": [
      { "field": "string", "value": "string" }
    ],
    "network": ["string"]
  },
  "software": [
    {
      "name": "string",
      "version": "string",
      "source": "string | [ENLACE OFICIAL]",
      "moment": "string",
      "validation": "string | [COMANDO DE PRUEBA]",
      "license": "string | [LICENCIA POR VALIDAR]",
      "purpose": "string",
      "pending": true
    }
  ],
  "accesses": [
    { "element": "string", "definition": "string" }
  ],
  "preparation": [
    {
      "order": "01",
      "title": "string",
      "description": "string",
      "commands": ["string"],
      "expected_result": "string",
      "evidence": "string",
      "warning": "string"
    }
  ],
  "validation": {
    "checklist": ["string"],
    "full_test": "string",
    "troubleshooting": [
      { "symptom": "string", "probable_cause": "string", "how_to_validate": "string", "corrective_action": "string" }
    ]
  },
  "lab_matrix": [
    {
      "number": "01-01-01",
      "name": "string",
      "objective": "string",
      "duration": "string",
      "dependencies": "string",
      "initial_state": "string",
      "expected_result": "string",
      "evidence": "string",
      "access": { "label": "Capítulo 01", "url": "string" }
    }
  ],
  "references": [
    { "label": "string", "url": "string" }
  ],
  "placeholders": ["string"]        // lista de marcadores detectados, para QA
}
```

## Reglas de generación

1. **No inventar**: si un campo técnico no está en las fuentes, se usa un marcador.
2. **Versión exacta**: versiones vagas (`latest`, `actual`, `1.x`) se marcan
   `[VERSIÓN POR VALIDAR]` y la fila queda `pending`.
3. **Fuente oficial**: si no se conoce la URL oficial se usa `[ENLACE OFICIAL]`.
4. **Matriz por práctica** (no por capítulo): una fila por laboratorio real.
5. **Pie de página**: curso/clave, versión/fecha y número de página. Sin campo de
   responsable.
