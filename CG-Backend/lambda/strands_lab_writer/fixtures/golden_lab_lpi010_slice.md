# Lab 02-01-01: Inspeccionar permisos y propiedad en Linux

## Metadatos

| Campo | Valor |
|---|---|
| Duración | 25 min |
| Complejidad | Media |
| Nivel Bloom | Apply |
| SO | Ubuntu 22.04 LTS (amd64) |

## Descripción General

Práctica orientada a **Linux Essentials**: el alumno interpreta salidas de `ls -l`, identifica
propietario, grupo y bits de permiso, y aplica cambios controlados con `chmod` y `chown`.
Datos embebidos en el enunciado; no se requieren ficheros externos del curso.

## Objetivos de Aprendizaje

- [ ] Interpretar la columna de permisos de `ls -l` en un directorio de trabajo.
- [ ] Ajustar permisos con notación octal sin abrir ejecución innecesaria.

## Prerrequisitos

- Acceso a una terminal en Linux con usuario no root y capacidad `sudo` para el paso de propiedad.
- Directorio de trabajo del curso: `/home/alumno/lab-permisos/`.

## Entorno de Laboratorio

| Componente | Requisito |
|---|---|
| SO | Ubuntu 22.04 LTS [VERSIÓN POR VALIDAR contra documentación oficial] |
| Herramientas | bash, coreutils (`ls`, `chmod`, `chown`) |

```bash
mkdir -p /home/alumno/lab-permisos/scripts
cd /home/alumno/lab-permisos
```

## Instrucciones Paso a Paso

### Paso 1: Crear el escenario de permisos

**Objetivo:** Disponer de un fichero y un script con permisos iniciales medibles.

**Instrucciones:**
1. Cree `informe.txt` con el contenido `Version 1` y fije permisos `644`.
2. Cree `scripts/backup.sh` con shebang `#!/bin/bash` y el cuerpo `echo "copia ok"`.
3. Ejecute `chmod 750 scripts/backup.sh`.

**Salida esperada:** `ls -l` muestra `-rw-r--r--` en `informe.txt` y `-rwxr-x---` en `scripts/backup.sh`.

**Verificación:** Ejecute `stat -c '%a %n' informe.txt scripts/backup.sh` y confirme `644` y `750`.

### Paso 2: Corregir propiedad del script

**Objetivo:** Asignar grupo `alumnos` al script sin alterar el contenido.

**Instrucciones:**
1. Si el grupo `alumnos` no existe, créelo con `sudo groupadd alumnos`.
2. Ejecute `sudo chown :alumnos scripts/backup.sh`.
3. Vuelva a listar con `ls -l scripts/backup.sh`.

**Salida esperada:** La columna de grupo muestra `alumnos` y los permisos conservan `rwxr-x---`.

**Verificación:** El comando `namei -l /home/alumno/lab-permisos/scripts/backup.sh` no reporta enlaces rotos.

<!-- GOLDEN_SLICE_END: remainder of a full lab (validación, dos troubleshooting, limpieza) omitted to save tokens -->