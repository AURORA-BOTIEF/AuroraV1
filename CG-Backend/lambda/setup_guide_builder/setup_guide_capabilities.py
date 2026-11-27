# -*- coding: utf-8 -*-
"""
THOR Setup Guide — capabilities profile (audit item 4 / backlog #7).

Express requirements as licenses, access, permissions and accounts. Drop OS, IDE,
shell, local paths and mandatory folder trees unless the syllabus names them.
"""

from __future__ import annotations

import re

# Editors, shells and OS families that are infrastructure detail unless named in the syllabus.
_INFRASTRUCTURE_TOKENS = (
    "windows",
    "windows server",
    "linux",
    "ubuntu",
    "debian",
    "centos",
    "rhel",
    "red hat",
    "macos",
    "mac os",
    "visual studio code",
    "vs code",
    "vscode",
    "powershell",
    "pwsh",
    "bash",
    "zsh",
    "cmd.exe",
    "command prompt",
    "terminal",
    "hyper-v",
    "wsl",
    "vmware",
    "virtualbox",
)

_PATH_MARKERS = (
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"(?i)\b/opt/"),
    re.compile(r"(?i)\b/var/"),
    re.compile(r"(?i)\b/home/"),
    re.compile(r"(?i)\b/usr/"),
    re.compile(r"(?i)\b/etc/"),
    re.compile(r"(?i)\bProgram Files\b"),
    re.compile(r"(?i)\bAppData\\"),
    re.compile(r"(?i)\bC:\\"),
)


def _normalize_corpus_piece(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def syllabus_requirement_corpus(course_meta: dict, master_plan: dict, outline_data: dict | None = None) -> str:
    """Text corpus where an explicit tool/OS name is allowed to appear in the SUG."""
    parts: list[str] = []
    outline_data = outline_data or {}
    course = outline_data.get("course", outline_data) if isinstance(outline_data, dict) else {}

    for source in (
        course_meta.get("prerequisites") or [],
        course_meta.get("description") or "",
        course.get("description") or "",
        master_plan.get("additional_requirements") or "",
    ):
        if isinstance(source, list):
            parts.extend(str(item) for item in source)
        elif source:
            parts.append(str(source))

    for item in master_plan.get("special_considerations") or []:
        if item:
            parts.append(str(item))

    return _normalize_corpus_piece(" ".join(parts))


def _named_in_syllabus(label: str, corpus: str) -> bool:
    if not label or not corpus:
        return False
    low = _normalize_corpus_piece(label)
    if low in corpus:
        return True
    for token in re.split(r"[^a-z0-9]+", low):
        if len(token) >= 4 and token in corpus:
            return True
    return False


def _contains_path_markers(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _PATH_MARKERS)


def is_infrastructure_detail(text: str) -> bool:
    """True when the text is mainly OS, editor, shell, or a local path / folder tree."""
    low = _normalize_corpus_piece(text)
    if _contains_path_markers(text or ""):
        return True
    if any(token in low for token in _INFRASTRUCTURE_TOKENS):
        return True
    if re.search(r"(?i)\b(ruta|path|directorio|folder|carpeta)\b", text or ""):
        return True
    return False


def filter_hardware_requirements(requirements: list, corpus: str) -> list:
    kept = []
    for req in requirements or []:
        text = str(req)
        if is_infrastructure_detail(text) and not _named_in_syllabus(text, corpus):
            continue
        kept.append(req)
    return kept


def filter_software_requirements(software_items: list[dict], corpus: str) -> list[dict]:
    """Drop infrastructure-only rows unless the syllabus names them."""
    kept: list[dict] = []
    for item in software_items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        purpose = str(item.get("purpose") or item.get("installation_notes") or "")
        combined = f"{name} {purpose}".strip()
        if is_infrastructure_detail(combined) and not _named_in_syllabus(combined, corpus):
            continue
        kept.append(item)
    return kept


def software_to_capabilities(software_items: list[dict]) -> list[dict]:
    """Map software rows to capability fields (license, access, permission)."""
    capabilities: list[dict] = []
    for item in software_items or []:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        capabilities.append(
            {
                "capability": name,
                "license": item.get("license") or "[LICENCIA POR VALIDAR]",
                "access": item.get("source") or "[ENLACE OFICIAL]",
                "permission": item.get("purpose") or item.get("installation_notes") or "[PERMISO POR VALIDAR]",
                "version": item.get("version") or "[VERSIÓN POR VALIDAR]",
                "pending": bool(item.get("pending")),
            }
        )
    return capabilities