import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure lambda directories are in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda', 'strands_lab_planner'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda', 'strands_lab_writer'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda', 'strands_content_gen'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda', 'ppt_merger'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda', 'strands_infographic_generator'))

import strands_lab_planner
import strands_lab_writer
import strands_content_gen
import lab_guide_builder
import starter_api


def test_planner_is_demo_activity():
    assert strands_lab_planner.is_demo_activity("Demo: Configuración de Docker", "") is True
    assert strands_lab_planner.is_demo_activity("Demostración: Cluster Kubernetes", "") is True
    assert strands_lab_planner.is_demo_activity("Demostracion de Redes", "") is True
    assert strands_lab_planner.is_demo_activity("[Demo] Creación de Pods", "") is True
    assert strands_lab_planner.is_demo_activity("Configurar Redes", "demo") is True
    assert strands_lab_planner.is_demo_activity("Configurar Redes", "demostración") is True
    assert strands_lab_planner.is_demo_activity("Laboratorio 1: Crear Pod", "lab") is False


def test_planner_ensure_demo_title():
    assert strands_lab_planner.ensure_demo_title("Demo: Configuración") == "Demo: Configuración"
    assert strands_lab_planner.ensure_demo_title("Demostración: Configuración") == "Demo: Configuración"
    assert strands_lab_planner.ensure_demo_title("Demostracion: Configuración") == "Demo: Configuración"
    assert strands_lab_planner.ensure_demo_title("Configuración Inicial") == "Demo: Configuración Inicial"


def test_planner_extract_all_labs_with_demos():
    modules = [
        {
            'title': 'Módulo 1: Introducción',
            'lessons': [
                {
                    'title': 'Teoría de Contenedores',
                    'type': 'theory',
                    'duration_minutes': 20
                },
                {
                    'title': 'Demostración: Instalación de Docker',
                    'type': 'demo',
                    'duration_minutes': 25,
                    'objectives': ['Mostrar la instalación de Docker Engine']
                },
                {
                    'title': 'Laboratorio 1: Mi Primer Contenedor',
                    'type': 'lab',
                    'duration_minutes': 30,
                    'objectives': ['Crear un contenedor nginx']
                }
            ]
        },
        {
            'title': 'Módulo 2: Kubernetes',
            'lessons': [
                {
                    'title': 'Arquitectura de K8s',
                    'lab_activities': [
                        {
                            'title': 'Demo: Despliegue de un Deployment',
                            'type': 'demo',
                            'duration_minutes': 20
                        },
                        {
                            'title': 'Lab: Exposición de Servicio',
                            'type': 'lab',
                            'duration_minutes': 30
                        }
                    ]
                }
            ]
        }
    ]

    labs = strands_lab_planner.extract_all_labs(modules)
    assert len(labs) == 4

    # Demo 1
    assert labs[0]['is_demo'] is True
    assert "Demo:" in labs[0]['lab_title']
    assert labs[0]['lab_id'] == "01-02-01"

    # Lab 1
    assert labs[1]['is_demo'] is False
    assert labs[1]['lab_id'] == "01-03-01"

    # Demo 2
    assert labs[2]['is_demo'] is True
    assert "Demo:" in labs[2]['lab_title']
    assert labs[2]['lab_id'] == "02-01-01"

    # Lab 2
    assert labs[3]['is_demo'] is False
    assert labs[3]['lab_id'] == "02-01-02"


def test_writer_is_demo_plan():
    assert strands_lab_writer.is_demo_plan({'is_demo': True, 'lab_title': 'Instalación'}) is True
    assert strands_lab_writer.is_demo_plan({'is_demo': False, 'lab_title': 'Demo: Instalación'}) is True
    assert strands_lab_writer.is_demo_plan({'is_demo': False, 'lab_title': 'Demostración de Redes'}) is True
    assert strands_lab_writer.is_demo_plan({'is_demo': False, 'lab_title': 'Laboratorio de Redes'}) is False


def test_writer_ensure_demo_formatting_spanish():
    sample_markdown = """# Lab 01-02-01: Instalación de Docker

## Metadatos

| Property | Value |
|---|---|
| Duration | 25 min |

## Descripción General

En esta sesión se abordará la instalación de Docker.

## Instrucciones Paso a Paso
### Paso 1: Descarga
Ejecutar curl...
"""

    formatted = strands_lab_writer._ensure_demo_formatting(sample_markdown, is_demo=True, is_spanish=True)
    assert "# Lab 01-02-01: Demo: Instalación de Docker" in formatted
    assert "Demostración realizada por el instructor" in formatted
    assert "en lugar de realizarla individualmente" in formatted


def test_writer_ensure_demo_formatting_english():
    sample_markdown = """# Lab 01-02-01: Docker Setup

## Metadata

| Property | Value |
|---|---|
| Duration | 25 min |

## Overview

In this session we will setup Docker.

## Step-by-Step Instructions
### Step 1: Download
Run curl...
"""

    formatted = strands_lab_writer._ensure_demo_formatting(sample_markdown, is_demo=True, is_spanish=False)
    assert "# Lab 01-02-01: Demo: Docker Setup" in formatted
    assert "Instructor-Led Demonstration" in formatted


def test_content_gen_demo_detection_and_spec():
    lesson_demo = {
        'title': 'Demostración: Cluster Setup',
        'type': 'demo',
        'duration_minutes': 20
    }
    assert strands_content_gen.is_lab_lesson(lesson_demo) is True
    assert strands_content_gen.is_demo_lesson(lesson_demo) is True


def test_lab_guide_builder_normalize_lab_title():
    assert lab_guide_builder.normalize_lab_title("Lab 01-02-01: Demo: Instalación", 1) == "Demo: Instalación"
    assert lab_guide_builder.normalize_lab_title("Lab 01-02-01: Demostración: Configuración", 1) == "Demo: Configuración"
    assert lab_guide_builder.normalize_lab_title("Lab 1: Mi Práctica", 1) == "Mi Práctica"
