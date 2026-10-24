#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plantilla HTML (Jinja2) para la Setup Guide (SUG) de Thor.
Se renderiza con xhtml2pdf, igual que book_to_pdf.py.

Replica la estructura de la plantilla visual de referencia:
portada, ruta de preparación, ficha técnica, especificaciones, software,
instalación/configuración, validación, matriz de prácticas y solución de problemas.
"""

SETUP_GUIDE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    @page {
        size: a4 portrait;
        margin: 1.9cm;
    }

    @page content {
        size: a4 portrait;
        margin: 1.9cm;
        margin-top: 2.4cm;
        margin-bottom: 2.2cm;

        @frame header_frame {
            -pdf-frame-content: headerContent;
            top: 0.7cm;
            left: 1.9cm;
            right: 1.9cm;
            height: 1.4cm;
        }

        @frame footer_frame {
            -pdf-frame-content: footerContent;
            bottom: 0.9cm;
            left: 1.9cm;
            right: 1.9cm;
            height: 1.0cm;
        }
    }

    body {
        font-family: Helvetica, Arial, sans-serif;
        font-size: 10.5px;
        line-height: 1.45;
        color: #2b2b2b;
    }

    /* ---------- Portada ---------- */
    .cover { text-align: center; padding-top: 3.6cm; }
    .cover .logo { max-width: 190px; margin-bottom: 1.6cm; }
    .cover .brand { font-size: 13px; letter-spacing: 3px; color: #1a237e; font-weight: bold; margin-bottom: 0.2cm; }
    .cover .doc-type { font-size: 11px; letter-spacing: 2px; color: #999999; margin-bottom: 1.4cm; }
    .cover .title { font-size: 30px; font-weight: bold; color: #1a237e; margin-bottom: 0.5cm; }
    .cover .subtitle { font-size: 13px; color: #555555; margin-bottom: 2.0cm; }
    .cover-table { width: 100%; border-collapse: collapse; margin-top: 1.2cm; }
    .cover-table td { border: 1px solid #d5d5e0; padding: 9px; text-align: center; }
    .cover-table .k { color: #1a237e; font-weight: bold; font-size: 12px; }
    .cover-table .v { color: #444444; font-size: 10px; }
    .cover-link { margin-top: 1.0cm; }
    .cover-link a { color: #1a237e; font-weight: bold; font-size: 11px; }

    /* ---------- Secciones ---------- */
    .page-break { page-break-before: always; }
    h1.section {
        color: #1a237e;
        font-size: 17px;
        border-bottom: 2px solid #1a237e;
        padding-bottom: 4px;
        margin: 0 0 10px 0;
        -pdf-keep-with-next: true;
    }
    h2.sub { color: #303f9f; font-size: 13px; margin: 14px 0 6px 0; -pdf-keep-with-next: true; }
    h3.mini { color: #303f9f; font-size: 11.5px; margin: 12px 0 4px 0; -pdf-keep-with-next: true; }
    .lead { color: #555555; font-size: 10px; margin-bottom: 10px; }

    /* ---------- Tablas de datos ---------- */
    table.data { width: 100%; border-collapse: collapse; margin: 8px 0 12px 0; }
    table.data th {
        background-color: #1a237e;
        color: #ffffff;
        font-size: 9.5px;
        text-align: left;
        padding: 6px 7px;
        border: 1px solid #1a237e;
    }
    table.data td {
        border: 1px solid #d9d9e3;
        padding: 6px 7px;
        font-size: 9.5px;
        vertical-align: top;
    }
    table.data tr.alt td { background-color: #f4f5fb; }
    .tag { font-size: 8.5px; font-weight: bold; }
    .tag-ok { color: #1b7f3b; }
    .tag-pending { color: #b26a00; }
    .pending { color: #b26a00; font-weight: bold; }

    /* ---------- Ruta de preparación ---------- */
    table.route { width: 100%; border-collapse: separate; margin: 6px 0 14px 0; }
    table.route td {
        width: 33%;
        text-align: center;
        padding: 12px 6px;
        background-color: #f0f1f9;
        border: 1px solid #d9d9e3;
        color: #1a237e;
        font-weight: bold;
        font-size: 11px;
    }

    /* ---------- Tarjetas ---------- */
    table.cards { width: 100%; border-collapse: separate; margin: 6px 0 14px 0; }
    table.cards td {
        width: 25%;
        text-align: center;
        padding: 12px 6px;
        background-color: #1a237e;
        border: 3px solid #ffffff;
        color: #ffffff;
    }
    table.cards .cv { font-size: 15px; font-weight: bold; display: block; }
    table.cards .cl { font-size: 8.5px; display: block; margin-top: 3px; color: #d7d9f0; }

    /* ---------- Callouts ---------- */
    table.callout { width: 100%; border-collapse: collapse; margin: 8px 0 12px 0; }
    table.callout td { padding: 8px 10px; font-size: 9.5px; }
    .callout-info { background-color: #eef2ff; border-left: 4px solid #1a237e; }
    .callout-warn { background-color: #fff7e6; border-left: 4px solid #e09b00; }
    .callout-ok { background-color: #ecf7ef; border-left: 4px solid #1b7f3b; }
    .callout-title { display: block; font-weight: bold; color: #1a237e; margin-bottom: 3px; font-size: 9px; letter-spacing: 0.5px; }
    .callout-warn .callout-title { color: #b26a00; }
    .callout-ok .callout-title { color: #1b7f3b; }

    /* ---------- Pasos ---------- */
    .step { margin-bottom: 12px; }
    .step-title { font-size: 12px; font-weight: bold; color: #1a237e; margin-bottom: 3px; -pdf-keep-with-next: true; }
    .step-desc { font-size: 10px; color: #444444; margin-bottom: 5px; }
    pre.code {
        background-color: #f5f5f7;
        border: 1px solid #e2e2ea;
        padding: 8px;
        font-family: Courier, monospace;
        font-size: 9px;
        white-space: pre-wrap;
        margin: 4px 0 8px 0;
    }

    /* ---------- Checklist ---------- */
    ul.check { margin: 4px 0 10px 0; padding-left: 0; list-style-type: none; }
    ul.check li { margin-bottom: 3px; font-size: 9.8px; }
    .box { font-family: Courier, monospace; color: #1a237e; }

    ul.plain { margin: 4px 0 10px 0; padding-left: 16px; }
    ul.plain li { margin-bottom: 3px; font-size: 9.8px; }

    .footer-note { color: #808080; font-size: 8.5px; margin-top: 6px; }

    /* ---------- Header / Footer ---------- */
    .hdr { text-align: right; }
    .hdr img { height: 30px; }
    .ftr {
        text-align: center;
        color: #8a8a8a;
        font-size: 7.8px;
        border-top: 1px solid #e5e5ec;
        padding-top: 4px;
    }
</style>
</head>
<body>

<!-- ===== Header / Footer frames ===== -->
<div id="headerContent">
    <div class="hdr">
        {% if logo_path %}<img src="{{ logo_path }}" />{% endif %}
    </div>
</div>
<div id="footerContent">
    <div class="ftr">
        {{ course_key }} &middot; {{ course_title }} &middot; Versión {{ version }} &middot; {{ date }}
        <br/>
        Página <pdf:pagenumber> de <pdf:pagecount>
    </div>
</div>

<!-- ===== Portada ===== -->
<div class="cover">
    {% if logo_path %}<img src="{{ logo_path }}" class="logo" />{% endif %}
    <div class="brand">NETEC</div>
    <div class="doc-type">THOR / MODELO DE SALIDA &middot; SETUP GUIDE</div>
    <div class="title">Guía de instalación y preparación del entorno</div>
    <div class="subtitle">Todo lo necesario para preparar, configurar y validar los laboratorios del curso.</div>

    <table class="cover-table">
        <tr>
            <td><span class="k">CURSO</span><br/><span class="v">{{ course_title }}</span></td>
            <td><span class="k">CLAVE</span><br/><span class="v">{{ course_key }}</span></td>
            <td><span class="k">VERSIÓN</span><br/><span class="v">{{ version }}</span></td>
            <td><span class="k">ESTADO</span><br/><span class="v">{{ status }}</span></td>
        </tr>
    </table>

    {% if repo_url %}
    <div class="cover-link">
        &#8599; EXPLORAR LABORATORIO<br/>
        Repositorio GitHub &middot; <a href="{{ repo_url }}">{{ repo_url }}</a>
    </div>
    {% endif %}
</div>

<!-- ===== Contenido ===== -->
<pdf:nexttemplate name="content" />
<pdf:nextpage />

<h1 class="section">Ruta de preparación</h1>
<p class="lead">Una lectura rápida del entorno antes de instalar o configurar cualquier componente.</p>

<table class="route">
    <tr>
        <td>01 &nbsp; PREPARAR</td>
        <td>02 &nbsp; CONFIGURAR</td>
        <td>03 &nbsp; VALIDAR</td>
    </tr>
</table>

<h2 class="sub">Ficha técnica</h2>
<table class="data">
    <tr>
        <th>Curso</th>
        <th>Clave</th>
        <th>Versión</th>
        <th>Última validación</th>
    </tr>
    <tr>
        <td>{{ course_title }}</td>
        <td>{{ course_key }}</td>
        <td>{{ version }}</td>
        <td>{{ last_validation }}</td>
    </tr>
</table>

{% if description %}
<h2 class="sub">Propósito</h2>
<p>{{ description }}</p>
{% endif %}

<h2 class="sub">Accesos principales</h2>
<table class="data">
    <tr><th>Recurso</th><th>Ubicación</th><th>Estado</th></tr>
    {% for link in identification.links %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ link.label }}</td>
        <td>{% if link.url %}<a href="{{ link.url }}">{{ link.url }}</a>{% else %}<span class="pending">[INSERTAR ENLACE]</span>{% endif %}</td>
        <td><span class="tag {% if link.status == 'Verificado' %}tag-ok{% else %}tag-pending{% endif %}">{{ link.status }}</span></td>
    </tr>
    {% endfor %}
</table>

<table class="callout">
    <tr><td class="callout-info">
        <span class="callout-title">CRITERIO OBLIGATORIO</span>
        El repositorio de GitHub debe aparecer desde la primera página y dirigir al curso específico.
    </td></tr>
</table>

<!-- ===== 01 Vista general ===== -->
<div class="page-break"></div>
<h1 class="section">01 &nbsp; Vista general</h1>

<h2 class="sub">Requisitos mínimos y recomendados</h2>
{% if counters %}
<table class="cards">
    <tr>
        {% for c in counters %}
        <td><span class="cv">{{ c.value }}</span><span class="cl">{{ c.label }}</span></td>
        {% endfor %}
    </tr>
</table>
{% endif %}

{% if infrastructure.hardware %}
<table class="data">
    <tr><th>Componente</th><th>Mínimo requerido</th><th>Recomendado</th><th>Estado</th></tr>
    {% for h in infrastructure.hardware %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ h.component }}</td>
        <td>{{ h.minimum }}</td>
        <td>{{ h.recommended }}</td>
        <td>{{ h.status }}</td>
    </tr>
    {% endfor %}
</table>
{% else %}
<p class="pending">[ESPECIFICACIONES DE EQUIPO POR VALIDAR]</p>
{% endif %}

<h2 class="sub">Configuración esperada de la máquina virtual</h2>
{% if infrastructure.virtual_machines %}
<table class="data">
    <tr><th>Elemento</th><th>Definición</th></tr>
    {% for vm in infrastructure.virtual_machines %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ vm.field }}</td>
        <td>{{ vm.value }}</td>
    </tr>
    {% endfor %}
</table>
{% else %}
<ul class="check">
    <li><span class="box">&#9744;</span> Hipervisor compatible y versión documentados.</li>
    <li><span class="box">&#9744;</span> Firmware BIOS o UEFI definido; Secure Boot indicado cuando aplique.</li>
    <li><span class="box">&#9744;</span> Modo de red establecido para cada adaptador.</li>
    <li><span class="box">&#9744;</span> Permisos administrativos disponibles durante la preparación.</li>
    <li><span class="box">&#9744;</span> Formato de entrega y ubicación de descarga confirmados.</li>
</ul>
{% endif %}

<h2 class="sub">Conocimientos y accesos previos</h2>
{% if previous_knowledge.knowledge %}
<h3 class="mini">Conocimientos esperados</h3>
<ul class="plain">{% for k in previous_knowledge.knowledge %}<li>{{ k }}</li>{% endfor %}</ul>
{% endif %}
{% if previous_knowledge.accounts or previous_knowledge.licenses or previous_knowledge.permissions %}
<table class="data">
    <tr><th>Elemento</th><th>Definición</th></tr>
    {% for item in previous_knowledge.accounts %}<tr><td>Cuenta</td><td>{{ item }}</td></tr>{% endfor %}
    {% for item in previous_knowledge.licenses %}<tr><td>Licencia</td><td>{{ item }}</td></tr>{% endfor %}
    {% for item in previous_knowledge.permissions %}<tr><td>Permiso</td><td>{{ item }}</td></tr>{% endfor %}
</table>
{% endif %}
{% if previous_knowledge.network %}
<h3 class="mini">Red, dominios y puertos</h3>
<ul class="plain">{% for n in previous_knowledge.network %}<li>{{ n }}</li>{% endfor %}</ul>
{% endif %}
{% if previous_knowledge.timing %}
<h3 class="mini">Momento de disponibilidad</h3>
<ul class="plain">{% for t in previous_knowledge.timing %}<li>{{ t }}</li>{% endfor %}</ul>
{% endif %}

<table class="callout">
    <tr><td class="callout-info">
        <span class="callout-title">NO INFERIR</span>
        Expresiones vagas deben convertirse en preguntas de validación antes de publicar el valor definitivo.
    </td></tr>
</table>

<!-- ===== 02 Especificaciones del equipo ===== -->
{% if infrastructure.hardware %}
<div class="page-break"></div>
<h1 class="section">02 &nbsp; Especificaciones del equipo</h1>
<table class="data">
    <tr><th>Componente</th><th>Mínimo requerido</th><th>Recomendado</th><th>Estado</th></tr>
    {% for h in infrastructure.hardware %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ h.component }}</td><td>{{ h.minimum }}</td><td>{{ h.recommended }}</td><td>{{ h.status }}</td>
    </tr>
    {% endfor %}
</table>
<table class="callout">
    <tr><td class="callout-ok">
        <span class="callout-title">RESULTADO ESPERADO</span>
        Una persona distinta al desarrollador puede crear la máquina y verificar sus recursos sin información adicional.
    </td></tr>
</table>
{% endif %}

<!-- ===== 03 Software, versiones y fuentes ===== -->
<div class="page-break"></div>
<h1 class="section">03 &nbsp; Software, versiones y fuentes oficiales</h1>
{% if software %}
<table class="data">
    <tr><th>Componente</th><th>Versión exacta</th><th>Fuente oficial</th><th>Momento</th><th>Validación</th></tr>
    {% for s in software %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ s.name }}{% if s.purpose %}<br/><span class="footer-note">{{ s.purpose }}</span>{% endif %}</td>
        <td>{% if s.pending %}<span class="pending">{{ s.version }}</span>{% else %}{{ s.version }}{% endif %}</td>
        <td>{% if s.source %}<a href="{{ s.source }}">{{ s.source }}</a>{% else %}<span class="pending">[ENLACE OFICIAL]</span>{% endif %}</td>
        <td>{{ s.moment }}</td>
        <td>{{ s.validation }}</td>
    </tr>
    {% endfor %}
</table>
{% else %}
<p class="pending">[SOFTWARE Y VERSIONES POR VALIDAR]</p>
{% endif %}
<table class="callout">
    <tr><td class="callout-warn">
        <span class="callout-title">VERSIONAMIENTO</span>
        No usar "última versión" o "versión actual". Registrar edición, arquitectura, URL oficial y fecha de validación.
    </td></tr>
</table>

{% if accesses %}
<h2 class="sub">Cuentas, accesos y seguridad</h2>
<table class="data">
    <tr><th>Elemento</th><th>Definición</th></tr>
    {% for a in accesses %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}><td>{{ a.element }}</td><td>{{ a.definition }}</td></tr>
    {% endfor %}
</table>
<table class="callout">
    <tr><td class="callout-warn">
        <span class="callout-title">CONTROL DE SEGURIDAD</span>
        Nunca incluir tokens, llaves de producción o credenciales reales. Las claves de práctica deben cambiarse cuando corresponda.
    </td></tr>
</table>
{% endif %}

<!-- ===== 04 Instalación y configuración ===== -->
<div class="page-break"></div>
<h1 class="section">04 &nbsp; Instalación y configuración</h1>
{% if preparation %}
    {% for step in preparation %}
    <div class="step">
        <div class="step-title">{{ step.order }} | {{ step.title }}</div>
        {% if step.description %}<div class="step-desc">{{ step.description }}</div>{% endif %}
        {% if step.commands %}
        <pre class="code">{% for cmd in step.commands %}{{ cmd }}
{% endfor %}</pre>
        {% endif %}
        {% if step.expected_result %}
        <table class="callout"><tr><td class="callout-ok">
            <span class="callout-title">RESULTADO ESPERADO</span>{{ step.expected_result }}
        </td></tr></table>
        {% endif %}
        {% if step.evidence %}
        <table class="callout"><tr><td class="callout-info">
            <span class="callout-title">EVIDENCIA REQUERIDA</span>{{ step.evidence }}
        </td></tr></table>
        {% endif %}
        {% if step.warning %}
        <table class="callout"><tr><td class="callout-warn">
            <span class="callout-title">PRECAUCIÓN</span>{{ step.warning }}
        </td></tr></table>
        {% endif %}
    </div>
    {% endfor %}
{% else %}
<p class="pending">[PASOS DE INSTALACIÓN POR VALIDAR]</p>
{% endif %}

<!-- ===== 05 Validación ===== -->
<div class="page-break"></div>
<h1 class="section">05 &nbsp; Validación del entorno</h1>
<h2 class="sub">Checklist previo al curso</h2>
<ul class="check">
    {% for item in validation.checklist %}
    <li><span class="box">&#9744;</span> {{ item }}</li>
    {% endfor %}
</ul>

<h2 class="sub">Prueba integral</h2>
<p>{{ validation.full_test }}</p>

<h2 class="sub">Diagnóstico de fallas frecuentes</h2>
{% if validation.troubleshooting %}
<table class="data">
    <tr><th>Síntoma</th><th>Causa probable</th><th>Cómo validar</th><th>Acción correctiva</th></tr>
    {% for t in validation.troubleshooting %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ t.symptom }}</td><td>{{ t.probable_cause }}</td><td>{{ t.how_to_validate }}</td><td>{{ t.corrective_action }}</td>
    </tr>
    {% endfor %}
</table>
{% else %}
<p class="pending">[DIAGNÓSTICO POR VALIDAR]</p>
{% endif %}

<table class="callout">
    <tr><td class="callout-ok">
        <span class="callout-title">ENTORNO LISTO</span>
        Al completar estas validaciones, el curso puede ejecutarse sin pasos previos implícitos.
    </td></tr>
</table>

<!-- ===== 06 Matriz de prácticas ===== -->
<div class="page-break"></div>
<h1 class="section">06 &nbsp; Ejecución de laboratorios</h1>
<p class="lead">Una fila por práctica real del repositorio: qué se ejecuta, qué necesita y cómo se comprueba.</p>
{% if lab_matrix %}
<table class="data">
    <tr>
        <th>Lab</th><th>Objetivo</th><th>Duración</th><th>Dependencias</th>
        <th>Estado inicial</th><th>Resultado esperado</th><th>Evidencia</th><th>Acceso</th>
    </tr>
    {% for lab in lab_matrix %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td><strong>{{ lab.number }}</strong><br/>{{ lab.name }}</td>
        <td>{{ lab.objective }}</td>
        <td>{{ lab.duration }}</td>
        <td>{{ lab.dependencies }}</td>
        <td>{{ lab.initial_state }}</td>
        <td>{{ lab.expected_result }}</td>
        <td>{{ lab.evidence }}</td>
        <td>{% if lab.access.url %}<a href="{{ lab.access.url }}">{{ lab.access.label }}</a>{% else %}<span class="pending">[ENLACE]</span>{% endif %}</td>
    </tr>
    {% endfor %}
</table>
{% else %}
<p class="pending">[MATRIZ DE PRÁCTICAS POR VALIDAR]</p>
{% endif %}

<!-- ===== 07 Solución de problemas ===== -->
<div class="page-break"></div>
<h1 class="section">07 &nbsp; Solución de problemas</h1>
{% if validation.troubleshooting %}
<table class="data">
    <tr><th>Síntoma</th><th>Causa probable</th><th>Cómo validar</th><th>Acción correctiva</th></tr>
    {% for t in validation.troubleshooting %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ t.symptom }}</td><td>{{ t.probable_cause }}</td><td>{{ t.how_to_validate }}</td><td>{{ t.corrective_action }}</td>
    </tr>
    {% endfor %}
</table>
{% else %}
<p class="pending">[DIAGNÓSTICO POR VALIDAR]</p>
{% endif %}

<h2 class="sub">Cierre de la preparación</h2>
<ul class="check">
    <li><span class="box">&#9744;</span> Todos los accesos están disponibles y son oficiales.</li>
    <li><span class="box">&#9744;</span> Las instalaciones cuentan con evidencia verificable.</li>
    <li><span class="box">&#9744;</span> Las configuraciones críticas tienen respaldo y procedimiento de reversión.</li>
    <li><span class="box">&#9744;</span> Cada laboratorio declara dependencias, versión y resultado esperado.</li>
    <li><span class="box">&#9744;</span> La guía está enlazada desde el README principal.</li>
</ul>

<h2 class="sub">Marcadores de acceso rápido</h2>
<table class="data">
    <tr><th>Destino</th><th>Enlace</th></tr>
    {% for ref in references %}
    <tr{% if loop.index0 % 2 == 1 %} class="alt"{% endif %}>
        <td>{{ ref.label }}</td>
        <td>{% if ref.url %}<a href="{{ ref.url }}">{{ ref.url }}</a>{% else %}<span class="pending">[INSERTAR ENLACE]</span>{% endif %}</td>
    </tr>
    {% endfor %}
</table>

<p class="footer-note">Documento generado por Thor (Aurora). Los campos marcados como pendientes deben confirmarse antes de liberar el material.</p>

</body>
</html>
"""
