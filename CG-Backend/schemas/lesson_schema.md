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

```markdown
# Lesson {M}.{L}: {Lesson Title}

## Learning Objectives

By the end of this lesson, you will be able to:

- {Bloom verb} + {measurable outcome 1}
- {Bloom verb} + {measurable outcome 2}
- {Bloom verb} + {measurable outcome 3}

## Introduction

{2-3 paragraphs introducing the lesson topic}
{Explain the importance and relevance}
{Preview what will be covered}

## {Topic 1: Main Topic Title}

### Concept Overview

{Explain WHAT the concept is}
{Explain WHY it matters in context}

### Technical Details

{Deep dive into the mechanics, architecture, or theory}
{Include specific details appropriate for the Bloom level}

### Practical Application

{Real-world example or scenario}
{Code example if applicable}

```language
// Code example with proper syntax highlighting
```

[VISUAL: MM-LL-XXXX - Clear description of diagram/image needed]

## {Topic 2: Next Topic Title}

### Concept Overview

{Same structure as Topic 1}

### Technical Details

{Continue pattern}

### Practical Application

{Continue pattern}

## {Topic N: Additional Topics as Needed}

{Follow same H2 > H3 structure}

## Summary

### Key Takeaways

- {Main point 1 from the lesson}
- {Main point 2 from the lesson}
- {Main point 3 from the lesson}

### What's Next

{Brief preview of how this connects to upcoming lessons}

## Review Questions

1. {Question testing understanding of key concept 1}
2. {Question testing understanding of key concept 2}
3. {Question requiring application of learned material}

## Additional Resources

- [{Resource 1 title}]({URL or reference})
- [{Resource 2 title}]({URL or reference})
- [{Resource 3 title}]({URL or reference})
```

---

## Required Sections Checklist

| Section | H Level | Required | Description |
|---------|---------|----------|-------------|
| Lesson Title | H1 | ✅ | Format: `# Lesson M.L: Title` |
| Learning Objectives | H2 | ✅ | 3-5 measurable objectives with Bloom verbs |
| Introduction | H2 | ✅ | Context and importance |
| Topic Sections | H2 | ✅ | At least one topic section |
| Concept Overview | H3 | ✅ | Under each topic |
| Technical Details | H3 | ✅ | Under each topic |
| Practical Application | H3 | Recommended | Examples and use cases |
| Summary | H2 | ✅ | Key takeaways |
| Review Questions | H2 | Recommended | 2-3 comprehension questions |
| Additional Resources | H2 | Optional | Links and references |

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
