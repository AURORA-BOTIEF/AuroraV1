"""
Content Validator Lambda
========================
Validates generated lesson and lab content against the standard Aurora schemas.
Ensures proper heading hierarchy, required sections, and formatting rules.

Integration:
- Called by Step Functions after content generation
- Can trigger retry if validation fails
- Logs validation results for quality tracking
"""

import os
import re
import json
import boto3
import yaml
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# AWS Clients
s3_client = boto3.client('s3')

# Load validation rules from schema
SCHEMA_BUCKET = os.environ.get('SCHEMA_BUCKET', 'crewai-course-artifacts')
SCHEMA_PREFIX = os.environ.get('SCHEMA_PREFIX', 'schemas')


class ValidationSeverity(Enum):
    ERROR = "error"      # Must fix - reject content
    WARNING = "warning"  # Should fix - flag but accept
    INFO = "info"        # Informational - log only


@dataclass
class ValidationResult:
    """Single validation result."""
    rule: str
    severity: ValidationSeverity
    message: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ContentValidationReport:
    """Complete validation report for a piece of content."""
    content_type: str  # "lesson" or "lab"
    content_key: str
    is_valid: bool
    errors: List[ValidationResult]
    warnings: List[ValidationResult]
    info: List[ValidationResult]
    
    def to_dict(self) -> dict:
        return {
            "content_type": self.content_type,
            "content_key": self.content_key,
            "is_valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.info),
            "errors": [{"rule": e.rule, "message": e.message, "line": e.line_number} for e in self.errors],
            "warnings": [{"rule": w.rule, "message": w.message, "line": w.line_number} for w in self.warnings],
            "info": [{"rule": i.rule, "message": i.message} for i in self.info]
        }


class ContentValidator:
    """Validates markdown content against Aurora schemas."""
    
    # Heading patterns
    H1_PATTERN = re.compile(r'^# (.+)$', re.MULTILINE)
    H2_PATTERN = re.compile(r'^## (.+)$', re.MULTILINE)
    H3_PATTERN = re.compile(r'^### (.+)$', re.MULTILINE)
    H4_PATTERN = re.compile(r'^#### (.+)$', re.MULTILINE)
    ALL_HEADINGS_PATTERN = re.compile(r'^(#{1,6}) (.+)$', re.MULTILINE)
    
    # Lesson patterns - supports English and Spanish
    LESSON_TITLE_PATTERN = re.compile(r'^# (Lesson|Lección) (\d+)\.(\d+): (.+)$', re.MULTILINE)
    
    # Lab patterns
    LAB_TITLE_PATTERN = re.compile(r'^# Lab (\d{2})-(\d{2})-(\d{2}): (.+)$', re.MULTILINE)
    LAB_STEP_PATTERN = re.compile(r'^### Step (\d+): (.+)$', re.MULTILINE)
    
    # Visual tag pattern
    VISUAL_TAG_PATTERN = re.compile(r'\[VISUAL: (\d{2})-(\d{2})-(\d{4}) - ([^\]]{10,100})\]')
    INVALID_VISUAL_PATTERNS = [
        (re.compile(r'\[visual:', re.IGNORECASE), "Lowercase 'visual' - must be uppercase VISUAL"),
        (re.compile(r'\[VISUAL:[^\s]'), "No space after colon in VISUAL tag"),
        (re.compile(r'\[VISUAL: \d+-\d+-\d+\]'), "Missing description in VISUAL tag"),
        (re.compile(r'\[VISUAL: [^\d]'), "VISUAL tag must start with ID (MM-LL-XXXX)"),
    ]
    
    # Code block pattern
    CODE_BLOCK_PATTERN = re.compile(r'```(\w*)\n', re.MULTILINE)
    CODE_BLOCK_NO_LANG = re.compile(r'```\s*\n[^`]+\n```', re.MULTILINE)
    
    # Table pattern
    TABLE_PATTERN = re.compile(r'\|.+\|.*\n\|[-:]+\|', re.MULTILINE)
    
    # Required lesson sections (English and Spanish variants)
    LESSON_REQUIRED_SECTIONS_EN = [
        "Learning Objectives",
        "Introduction",
        "Summary"
    ]
    
    LESSON_REQUIRED_SECTIONS_ES = [
        "Objetivos de Aprendizaje",
        "Introducción",
        "Resumen"
    ]
    
    # Combined for validation (will match either language)
    LESSON_REQUIRED_SECTIONS = [
        ("Learning Objectives", "Objetivos de Aprendizaje"),
        ("Introduction", "Introducción"),
        ("Summary", "Resumen")
    ]
    
    # Required lab sections (English and Spanish variants)
    LAB_REQUIRED_SECTIONS = [
        ("Metadata", "Metadatos"),
        ("Overview", "Descripción General"),
        ("Learning Objectives", "Objetivos de Aprendizaje"),
        ("Prerequisites", "Prerrequisitos"),
        ("Lab Environment", "Entorno de Laboratorio"),
        ("Step-by-Step Instructions", "Instrucciones Paso a Paso"),
        ("Validation & Testing", "Validación y Pruebas"),
        ("Troubleshooting", "Solución de Problemas"),
        ("Cleanup", "Limpieza"),
        ("Summary", "Resumen")
    ]
    
    # Bloom verbs for validation (English and Spanish)
    BLOOM_VERBS = {
        'remember': ['define', 'list', 'identify', 'name', 'recall', 'recognize', 'state', 'describe',
                     'definir', 'listar', 'identificar', 'nombrar', 'recordar', 'reconocer', 'describir'],
        'understand': ['describe', 'explain', 'summarize', 'interpret', 'classify', 'discuss', 'paraphrase',
                       'describir', 'explicar', 'resumir', 'interpretar', 'clasificar', 'discutir'],
        'apply': ['implement', 'execute', 'use', 'demonstrate', 'solve', 'apply', 'practice', 'operate',
                  'implementar', 'ejecutar', 'usar', 'demostrar', 'resolver', 'aplicar', 'practicar', 'operar'],
        'analyze': ['compare', 'differentiate', 'examine', 'investigate', 'distinguish', 'analyze', 'organize',
                    'comparar', 'diferenciar', 'examinar', 'investigar', 'distinguir', 'analizar', 'organizar'],
        'evaluate': ['assess', 'critique', 'judge', 'justify', 'recommend', 'evaluate', 'defend', 'argue',
                     'evaluar', 'criticar', 'juzgar', 'justificar', 'recomendar', 'defender', 'argumentar'],
        'create': ['design', 'develop', 'construct', 'produce', 'compose', 'create', 'build', 'generate',
                   'diseñar', 'desarrollar', 'construir', 'producir', 'componer', 'crear', 'generar']
    }
    
    def __init__(self):
        self.results: List[ValidationResult] = []
    
    def _add_result(self, rule: str, severity: ValidationSeverity, message: str, 
                   line_number: int = None, suggestion: str = None):
        """Add a validation result."""
        self.results.append(ValidationResult(
            rule=rule,
            severity=severity,
            message=message,
            line_number=line_number,
            suggestion=suggestion
        ))
    
    def _find_line_number(self, content: str, pattern: str) -> Optional[int]:
        """Find the line number of a pattern in content."""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if pattern in line:
                return i
        return None
    
    def _get_all_headings(self, content: str) -> List[Tuple[int, int, str]]:
        """Get all headings with their level and line number."""
        headings = []
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            match = self.ALL_HEADINGS_PATTERN.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2)
                headings.append((i, level, title))
        return headings
    
    def validate_heading_hierarchy(self, content: str) -> None:
        """Validate that heading levels don't skip."""
        headings = self._get_all_headings(content)
        
        if not headings:
            self._add_result(
                "heading_hierarchy",
                ValidationSeverity.ERROR,
                "No headings found in content"
            )
            return
        
        prev_level = 0
        for line_num, level, title in headings:
            if level > prev_level + 1 and prev_level > 0:
                self._add_result(
                    "heading_hierarchy",
                    ValidationSeverity.ERROR,
                    f"Heading level skipped: H{prev_level} → H{level} ('{title}')",
                    line_number=line_num,
                    suggestion=f"Add intermediate H{prev_level + 1} heading before this"
                )
            prev_level = level
    
    def validate_single_h1(self, content: str, expected_pattern: re.Pattern) -> None:
        """Validate exactly one H1 heading exists."""
        h1_matches = self.H1_PATTERN.findall(content)
        
        if len(h1_matches) == 0:
            self._add_result(
                "single_h1",
                ValidationSeverity.ERROR,
                "No H1 heading found"
            )
        elif len(h1_matches) > 1:
            self._add_result(
                "single_h1",
                ValidationSeverity.ERROR,
                f"Multiple H1 headings found ({len(h1_matches)}). Only one is allowed."
            )
        else:
            # Check format
            if not expected_pattern.search(content):
                self._add_result(
                    "h1_format",
                    ValidationSeverity.WARNING,
                    f"H1 heading format doesn't match expected pattern"
                )
    
    def validate_required_sections(self, content: str, required_sections) -> None:
        """Validate all required H2 sections exist.
        
        Args:
            content: The markdown content to validate
            required_sections: Can be a list of strings or list of tuples (en, es)
        """
        h2_sections = [title.strip() for _, level, title in self._get_all_headings(content) if level == 2]
        h2_sections_lower = [h2.lower() for h2 in h2_sections]
        
        for section in required_sections:
            # Handle both tuple format (en, es) and string format
            if isinstance(section, tuple):
                section_variants = section  # (English, Spanish)
            else:
                section_variants = (section,)  # Single language
            
            # Check if any variant is found
            found = False
            for variant in section_variants:
                for h2 in h2_sections:
                    if variant.lower() in h2.lower() or h2.lower() in variant.lower():
                        found = True
                        break
                if found:
                    break
            
            if not found:
                section_name = section_variants[0] if isinstance(section, tuple) else section
                alt_name = f" / {section_variants[1]}" if isinstance(section, tuple) and len(section_variants) > 1 else ""
                self._add_result(
                    "required_section",
                    ValidationSeverity.ERROR,
                    f"Required section missing: '{section_name}'{alt_name}",
                    suggestion=f"Add '## {section_name}' section (or equivalent in course language)"
                )
    
    def validate_visual_tags(self, content: str) -> None:
        """Validate VISUAL tag format."""
        # Check for valid visual tags
        valid_tags = self.VISUAL_TAG_PATTERN.findall(content)
        
        # Check for invalid patterns
        for pattern, message in self.INVALID_VISUAL_PATTERNS:
            matches = pattern.findall(content)
            for match in matches:
                line_num = self._find_line_number(content, match if isinstance(match, str) else match[0])
                self._add_result(
                    "visual_tag_format",
                    ValidationSeverity.WARNING,
                    message,
                    line_number=line_num,
                    suggestion="Use format: [VISUAL: MM-LL-XXXX - description]"
                )
        
        if valid_tags:
            self._add_result(
                "visual_tags",
                ValidationSeverity.INFO,
                f"Found {len(valid_tags)} valid VISUAL tags"
            )
    
    def validate_code_blocks(self, content: str) -> None:
        """Validate code blocks have language specification."""
        # Find code blocks without language
        no_lang_matches = self.CODE_BLOCK_NO_LANG.findall(content)
        
        # Get all code block openings
        all_blocks = self.CODE_BLOCK_PATTERN.findall(content)
        blocks_without_lang = [b for b in all_blocks if not b.strip()]
        
        if blocks_without_lang:
            self._add_result(
                "code_block_language",
                ValidationSeverity.WARNING,
                f"Found {len(blocks_without_lang)} code block(s) without language specification",
                suggestion="Add language after ``` (e.g., ```python, ```bash)"
            )
    
    def validate_tables(self, content: str) -> None:
        """Validate tables use native Markdown."""
        tables = self.TABLE_PATTERN.findall(content)
        if tables:
            self._add_result(
                "tables",
                ValidationSeverity.INFO,
                f"Found {len(tables)} properly formatted Markdown table(s)"
            )
    
    def validate_learning_objectives(self, content: str) -> None:
        """Validate learning objectives use Bloom verbs."""
        # Find Learning Objectives section
        obj_match = re.search(r'## Learning Objectives\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        
        if not obj_match:
            return
        
        obj_content = obj_match.group(1)
        objectives = re.findall(r'^[-*\[\] ]+(.+)$', obj_content, re.MULTILINE)
        
        all_verbs = []
        for verbs in self.BLOOM_VERBS.values():
            all_verbs.extend(verbs)
        
        objectives_with_bloom_verbs = 0
        for obj in objectives:
            first_word = obj.split()[0].lower().rstrip(',.:')
            if first_word in all_verbs:
                objectives_with_bloom_verbs += 1
        
        if objectives and objectives_with_bloom_verbs < len(objectives) / 2:
            self._add_result(
                "bloom_verbs",
                ValidationSeverity.WARNING,
                f"Only {objectives_with_bloom_verbs}/{len(objectives)} objectives start with Bloom taxonomy verbs",
                suggestion="Start objectives with verbs like: Define, Explain, Implement, Compare, Evaluate, Design"
            )
    
    def validate_word_count(self, content: str, min_words: int = 500, max_words: int = 6000) -> None:
        """Validate word count is within range."""
        words = len(content.split())
        
        if words < min_words:
            self._add_result(
                "word_count",
                ValidationSeverity.WARNING,
                f"Content has {words} words, which is below minimum ({min_words})"
            )
        elif words > max_words:
            self._add_result(
                "word_count",
                ValidationSeverity.WARNING,
                f"Content has {words} words, which exceeds maximum ({max_words})"
            )
        else:
            self._add_result(
                "word_count",
                ValidationSeverity.INFO,
                f"Word count: {words} (within acceptable range)"
            )
    
    def validate_lab_steps(self, content: str) -> None:
        """Validate lab step structure."""
        steps = self.LAB_STEP_PATTERN.findall(content)
        
        if not steps:
            self._add_result(
                "lab_steps",
                ValidationSeverity.ERROR,
                "No steps found in Step-by-Step Instructions section",
                suggestion="Add steps using: ### Step N: [Title]"
            )
            return
        
        self._add_result(
            "lab_steps",
            ValidationSeverity.INFO,
            f"Found {len(steps)} step(s)"
        )
        
        # Check each step for required elements
        step_sections = re.split(r'### Step \d+:', content)
        
        required_in_step = ['**Objective:**', '**Instructions:**', '**Verification:**']
        
        for i, section in enumerate(step_sections[1:], 1):  # Skip content before first step
            for req in required_in_step:
                if req.lower() not in section.lower():
                    self._add_result(
                        "step_structure",
                        ValidationSeverity.WARNING,
                        f"Step {i} missing '{req.strip('*:')}' section"
                    )
    
    def validate_troubleshooting(self, content: str, min_issues: int = 2) -> None:
        """Validate troubleshooting section has enough issues."""
        # Find troubleshooting section
        trouble_match = re.search(r'## Troubleshooting\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        
        if not trouble_match:
            return
        
        trouble_content = trouble_match.group(1)
        issues = re.findall(r'### Issue \d+:|### Issue:', trouble_content)
        
        if len(issues) < min_issues:
            self._add_result(
                "troubleshooting",
                ValidationSeverity.WARNING,
                f"Found {len(issues)} troubleshooting issue(s), minimum is {min_issues}",
                suggestion="Add more common issues and their solutions"
            )
    
    def validate_lesson(self, content: str) -> ContentValidationReport:
        """Validate lesson content against schema."""
        self.results = []
        
        # Validate heading hierarchy
        self.validate_heading_hierarchy(content)
        
        # Validate single H1 with correct format
        self.validate_single_h1(content, self.LESSON_TITLE_PATTERN)
        
        # Validate required sections
        self.validate_required_sections(content, self.LESSON_REQUIRED_SECTIONS)
        
        # Validate visual tags
        self.validate_visual_tags(content)
        
        # Validate code blocks
        self.validate_code_blocks(content)
        
        # Validate tables
        self.validate_tables(content)
        
        # Validate learning objectives
        self.validate_learning_objectives(content)
        
        # Validate word count
        self.validate_word_count(content, min_words=800, max_words=6000)
        
        # Build report
        errors = [r for r in self.results if r.severity == ValidationSeverity.ERROR]
        warnings = [r for r in self.results if r.severity == ValidationSeverity.WARNING]
        info = [r for r in self.results if r.severity == ValidationSeverity.INFO]
        
        return ContentValidationReport(
            content_type="lesson",
            content_key="",
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=info
        )
    
    def validate_lab(self, content: str) -> ContentValidationReport:
        """Validate lab guide content against schema."""
        self.results = []
        
        # Validate heading hierarchy
        self.validate_heading_hierarchy(content)
        
        # Validate single H1 with correct format
        self.validate_single_h1(content, self.LAB_TITLE_PATTERN)
        
        # Validate required sections
        self.validate_required_sections(content, self.LAB_REQUIRED_SECTIONS)
        
        # Validate code blocks
        self.validate_code_blocks(content)
        
        # Validate tables
        self.validate_tables(content)
        
        # Validate learning objectives
        self.validate_learning_objectives(content)
        
        # Validate lab steps
        self.validate_lab_steps(content)
        
        # Validate troubleshooting
        self.validate_troubleshooting(content, min_issues=2)
        
        # Validate word count (labs tend to be longer)
        self.validate_word_count(content, min_words=1000, max_words=10000)
        
        # Build report
        errors = [r for r in self.results if r.severity == ValidationSeverity.ERROR]
        warnings = [r for r in self.results if r.severity == ValidationSeverity.WARNING]
        info = [r for r in self.results if r.severity == ValidationSeverity.INFO]
        
        return ContentValidationReport(
            content_type="lab",
            content_key="",
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=info
        )


def load_content_from_s3(bucket: str, key: str) -> str:
    """Load markdown content from S3."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response['Body'].read().decode('utf-8')


def save_validation_report(bucket: str, project_folder: str, report: ContentValidationReport, content_key: str) -> str:
    """Save validation report to S3."""
    report_dict = report.to_dict()
    report_dict['content_key'] = content_key
    
    # Generate report key
    content_filename = content_key.split('/')[-1].replace('.md', '')
    report_key = f"{project_folder}/validation/{content_filename}-validation.json"
    
    s3_client.put_object(
        Bucket=bucket,
        Key=report_key,
        Body=json.dumps(report_dict, indent=2),
        ContentType='application/json'
    )
    
    return report_key


def lambda_handler(event, context):
    """
    AWS Lambda handler for content validation.
    
    Input event:
    {
        "course_bucket": "bucket-name",
        "project_folder": "project-name",
        "content_keys": ["path/to/lesson.md", "path/to/lab.md"],
        "content_type": "lesson" | "lab" | "auto",  // auto-detect if not specified
        "fail_on_error": true  // Whether to return error status if validation fails
    }
    
    Output:
    {
        "statusCode": 200 | 400,
        "validation_results": [...],
        "all_valid": true | false,
        "total_errors": N,
        "total_warnings": N
    }
    """
    
    print("=" * 70)
    print("📋 CONTENT VALIDATOR")
    print("=" * 70)
    print(f"Event: {json.dumps(event, indent=2)}")
    
    try:
        # Extract parameters
        course_bucket = event.get('course_bucket', 'crewai-course-artifacts')
        project_folder = event.get('project_folder')
        content_keys = event.get('content_keys', [])
        content_type = event.get('content_type', 'auto')
        fail_on_error = event.get('fail_on_error', True)
        
        if not content_keys:
            # Auto-discover content if no keys provided
            print("No content_keys provided, checking for lesson_keys or lab_keys...")
            content_keys = event.get('lesson_keys', []) or event.get('lab_keys', [])
            
            # Handle structured lesson_keys (list of dicts with s3_key)
            if content_keys and isinstance(content_keys[0], dict):
                content_keys = [k.get('s3_key') for k in content_keys if k.get('s3_key')]
        
        if not content_keys:
            return {
                'statusCode': 400,
                'error': 'No content_keys provided for validation'
            }
        
        validator = ContentValidator()
        validation_results = []
        total_errors = 0
        total_warnings = 0
        
        for key in content_keys:
            print(f"\n📄 Validating: {key}")
            
            try:
                content = load_content_from_s3(course_bucket, key)
                
                # Auto-detect content type
                detected_type = content_type
                if content_type == 'auto':
                    if '/lessons/' in key or key.endswith('-lesson.md'):
                        detected_type = 'lesson'
                    elif '/labguide/' in key or 'lab-' in key.lower():
                        detected_type = 'lab'
                    else:
                        # Default to lesson
                        detected_type = 'lesson'
                
                print(f"  Type: {detected_type}")
                
                # Validate
                if detected_type == 'lesson':
                    report = validator.validate_lesson(content)
                else:
                    report = validator.validate_lab(content)
                
                report.content_key = key
                
                # Log results
                print(f"  ✓ Valid: {report.is_valid}")
                print(f"  ❌ Errors: {len(report.errors)}")
                print(f"  ⚠️  Warnings: {len(report.warnings)}")
                
                for error in report.errors:
                    print(f"    ❌ {error.rule}: {error.message}")
                
                for warning in report.warnings[:3]:  # Limit warning output
                    print(f"    ⚠️  {warning.rule}: {warning.message}")
                
                # Save report
                if project_folder:
                    report_key = save_validation_report(course_bucket, project_folder, report, key)
                    print(f"  📝 Report saved: {report_key}")
                
                validation_results.append(report.to_dict())
                total_errors += len(report.errors)
                total_warnings += len(report.warnings)
                
            except Exception as e:
                print(f"  ❌ Error validating {key}: {e}")
                validation_results.append({
                    "content_key": key,
                    "is_valid": False,
                    "errors": [{"rule": "load_error", "message": str(e)}],
                    "warnings": [],
                    "info": []
                })
                total_errors += 1
        
        all_valid = total_errors == 0
        
        print(f"\n{'=' * 70}")
        print(f"📊 VALIDATION SUMMARY")
        print(f"  Files validated: {len(content_keys)}")
        print(f"  All valid: {all_valid}")
        print(f"  Total errors: {total_errors}")
        print(f"  Total warnings: {total_warnings}")
        print(f"{'=' * 70}")
        
        response = {
            'statusCode': 200 if (all_valid or not fail_on_error) else 400,
            'validation_results': validation_results,
            'all_valid': all_valid,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'files_validated': len(content_keys)
        }
        
        return response
        
    except Exception as e:
        print(f"❌ Error in validation: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'error': str(e),
            'errorType': type(e).__name__
        }


# For local testing
if __name__ == "__main__":
    # Test with sample content
    sample_lesson = """
# Lesson 1.1: Introduction to Python

## Learning Objectives

By the end of this lesson, you will be able to:

- Define what Python is and its main use cases
- Explain the difference between Python 2 and Python 3
- Implement a simple Python program

## Introduction

Python is a high-level programming language known for its simplicity and readability.

It was created by Guido van Rossum and first released in 1991.

## Getting Started with Python

### Concept Overview

Python is an interpreted language, which means code is executed line by line.

### Technical Details

Python uses indentation to define code blocks instead of braces.

```python
def hello():
    print("Hello, World!")
```

### Practical Application

Here's a simple example:

```python
name = input("What is your name? ")
print(f"Hello, {name}!")
```

[VISUAL: 01-01-0001 - Diagram showing Python interpreter execution flow]

## Summary

### Key Takeaways

- Python is beginner-friendly
- It uses indentation for code blocks
- It's widely used in data science and web development

## Review Questions

1. What is Python?
2. Who created Python?
"""
    
    validator = ContentValidator()
    report = validator.validate_lesson(sample_lesson)
    
    print(f"\nValidation Report:")
    print(f"Valid: {report.is_valid}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")
    
    for error in report.errors:
        print(f"  ❌ {error.rule}: {error.message}")
    
    for warning in report.warnings:
        print(f"  ⚠️  {warning.rule}: {warning.message}")
