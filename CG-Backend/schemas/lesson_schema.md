# Aurora Content Generation - Lesson Schema v1.0

## Overview

This document defines the **mandatory structure** for all generated lesson content.
All AI models (Bedrock Claude, OpenAI GPT, etc.) MUST follow this exact hierarchy.

---

## Heading Hierarchy Rules

| Level | Markdown | Usage | Required |
|-------|----------|-------|----------|
| H1 | `#` | Lesson title ONLY (one per document) | ✅ Yes |
| H2 | `##` | Major sections | ✅ Yes |
| H3 | `###` | Subsections within H2 | Optional |
| H4 | `####` | Details within H3 | Optional |

**CRITICAL**: Never skip heading levels (e.g., H1 → H3 is INVALID)

---

## Standard Lesson Structure

**IMPORTANT: ALL section titles MUST be in the same language as the course.**
The examples below show Spanish titles. If the course is in English, use English equivalents.

```markdown
# Lección {M}.{L}: {Título de la Lección}  <!-- Or "Lesson" if course is in English -->

## Objetivos de Aprendizaje  <!-- Or "Learning Objectives" -->

Al finalizar esta lección, serás capaz de:  <!-- Or "By the end of this lesson, you will be able to:" -->

- {Verbo Bloom} + {resultado medible 1}
- {Verbo Bloom} + {resultado medible 2}
- {Verbo Bloom} + {resultado medible 3}

## Introducción  <!-- Or "Introduction" -->

{2-3 paragraphs introducing the lesson topic}
{Explain the importance and relevance}
{Preview what will be covered}

## {Tema 1: Título del Tema Principal}  <!-- Topic title in course language -->

### Visión General del Concepto  <!-- Or "Concept Overview" -->

{Explain WHAT the concept is}
{Explain WHY it matters in context}

### Detalles Técnicos  <!-- Or "Technical Details" -->

{Deep dive into the mechanics, architecture, or theory}
{Include specific details appropriate for the Bloom level}

### Aplicación Práctica  <!-- Or "Practical Application" -->

{Real-world example or scenario}
{Code example if applicable}

```language
// Code example with proper syntax highlighting
```

[VISUAL: MM-LL-XXXX - Clear description of diagram/image needed]

## {Tema 2: Siguiente Título del Tema}

### Visión General del Concepto

{Same structure as Topic 1}

### Detalles Técnicos

{Continue pattern}

### Aplicación Práctica

{Continue pattern}

## {Tema N: Temas Adicionales según sea necesario}

{Follow same H2 > H3 structure}

## Resumen  <!-- Or "Summary" -->

### Puntos Clave  <!-- Or "Key Takeaways" -->

- {Main point 1 from the lesson}
- {Main point 2 from the lesson}
- {Main point 3 from the lesson}

### Próximos Pasos  <!-- Or "What's Next" -->

{Brief preview of how this connects to upcoming lessons}

## Referencias Bibliográficas  <!-- Or "Bibliographic References" -->

- [{Reference 1}]({URL or reference})
- [{Reference 2}]({URL or reference})
- [{Reference 3}]({URL or reference})
```

**NOTE: Do NOT include a "Review Questions" section. Quizzes will be handled separately.**

---

## Required Sections Checklist

**All section titles must match the course language (Spanish/English/etc.)**

| Section | H Level | Required | Spanish Title | English Title |
|---------|---------|----------|---------------|---------------|
| Lesson Title | H1 | ✅ | `# Lección M.L: Título` | `# Lesson M.L: Title` |
| Learning Objectives | H2 | ✅ | `## Objetivos de Aprendizaje` | `## Learning Objectives` |
| Introduction | H2 | ✅ | `## Introducción` | `## Introduction` |
| Topic Sections | H2 | ✅ | `## [Título del Tema]` | `## [Topic Title]` |
| Concept Overview | H3 | ✅ | `### Visión General del Concepto` | `### Concept Overview` |
| Technical Details | H3 | ✅ | `### Detalles Técnicos` | `### Technical Details` |
| Practical Application | H3 | Recommended | `### Aplicación Práctica` | `### Practical Application` |
| Summary | H2 | ✅ | `## Resumen` | `## Summary` |
| Key Takeaways | H3 | ✅ | `### Puntos Clave` | `### Key Takeaways` |
| What's Next | H3 | Recommended | `### Próximos Pasos` | `### What's Next` |
| Bibliographic References | H2 | ✅ | `## Referencias Bibliográficas` | `## Bibliographic References` |

**⚠️ DO NOT include Review Questions section - quizzes are handled separately.**

---

## Bloom's Taxonomy Verb Reference

Use these verbs in Learning Objectives based on the lesson's Bloom level:

| Level | Verbs |
|-------|-------|
| **Remember** | Define, List, Identify, Name, Recall, Recognize |
| **Understand** | Describe, Explain, Summarize, Interpret, Classify |
| **Apply** | Implement, Execute, Use, Demonstrate, Solve |
| **Analyze** | Compare, Differentiate, Examine, Investigate, Distinguish |
| **Evaluate** | Assess, Critique, Judge, Justify, Recommend |
| **Create** | Design, Develop, Construct, Produce, Compose |

---

## Visual Tag Format

All visual elements MUST use this EXACT format:

```
[VISUAL: MM-LL-XXXX - Description of the visual element]
```

Where:
- `MM` = Module number (2 digits, zero-padded)
- `LL` = Lesson number (2 digits, zero-padded)  
- `XXXX` = Global image counter (4 digits, zero-padded)
- Description = 10-20 words describing what the image should show

### Valid Examples

```markdown
[VISUAL: 01-02-0001 - Architecture diagram showing client-server communication flow]
[VISUAL: 03-01-0015 - Flowchart of the authentication process from login to session]
[VISUAL: 05-03-0042 - Comparison chart of synchronous vs asynchronous processing]
```

### Invalid Examples (DO NOT USE)

```markdown
[VISUAL: 1-2-1 - diagram]                    ❌ Not zero-padded
[VISUAL: Description without ID]              ❌ Missing ID
[visual: 01-02-0001 - lowercase]             ❌ Not uppercase
[VISUAL: 01-02-0001]                          ❌ Missing description
```

---

## Code Block Rules

### Always Specify Language

```python
# Good: Language specified
def example():
    return "Hello"
```

```
# Bad: No language specified
def example():
    return "Hello"
```

### Supported Languages for Syntax Highlighting

- `python`, `javascript`, `typescript`, `java`, `go`, `rust`, `c`, `cpp`
- `bash`, `shell`, `powershell`, `cmd`
- `yaml`, `json`, `xml`, `html`, `css`
- `sql`, `graphql`
- `dockerfile`, `terraform`, `kubernetes`

---

## Table Format

Use standard Markdown tables for structured data:

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |
```

**DO NOT** create VISUAL tags for tabular data - use native tables.

---

## Content Quality Guidelines

### Word Count Targets

| Lesson Duration | Target Words | Min Words | Max Words |
|-----------------|--------------|-----------|-----------|
| 15 minutes | 1,000 | 800 | 1,200 |
| 30 minutes | 1,800 | 1,500 | 2,200 |
| 45 minutes | 2,500 | 2,000 | 3,000 |
| 60 minutes | 3,500 | 3,000 | 4,000 |
| 90 minutes | 5,000 | 4,500 | 6,000 |

### Depth by Bloom Level

| Bloom Level | Content Depth | Example Focus |
|-------------|---------------|---------------|
| Remember | Definitions, facts, terminology | Lists, key terms |
| Understand | Explanations, interpretations | How things work |
| Apply | Step-by-step procedures | Hands-on examples |
| Analyze | Comparisons, breakdowns | Case studies |
| Evaluate | Assessments, recommendations | Trade-off analysis |
| Create | Design patterns, synthesis | Building solutions |

---

## Validation Checklist

Before finalizing content, verify:

- [ ] Single H1 heading at the start
- [ ] No skipped heading levels
- [ ] All required sections present
- [ ] Learning objectives use appropriate Bloom verbs
- [ ] VISUAL tags follow exact format `[VISUAL: MM-LL-XXXX - description]`
- [ ] Code blocks have language specified
- [ ] Tables use Markdown syntax (not VISUAL tags)
- [ ] Word count within target range
- [ ] Content depth matches Bloom level

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-08 | Initial schema definition |
