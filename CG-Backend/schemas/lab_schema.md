# Aurora Content Generation - Lab Guide Schema v1.0

## Overview

This document defines the **mandatory structure** for all generated lab guides.
All AI models (Bedrock Claude, OpenAI GPT, etc.) MUST follow this exact hierarchy.

---

## Heading Hierarchy Rules

| Level | Markdown | Usage | Required |
|-------|----------|-------|----------|
| H1 | `#` | Lab title ONLY (one per document) | ✅ Yes |
| H2 | `##` | Major sections | ✅ Yes |
| H3 | `###` | Steps within instructions OR subsections | ✅ Yes |
| H4 | `####` | Details within steps | Optional |

**CRITICAL**: Never skip heading levels (e.g., H1 → H3 is INVALID)

---

## Standard Lab Guide Structure

```markdown
# Lab {MM-LL-NN}: {Lab Title}

## Metadata

| Property | Value |
|----------|-------|
| **Duration** | {XX} minutes |
| **Complexity** | {Beginner / Intermediate / Advanced} |
| **Bloom Level** | {Remember / Understand / Apply / Analyze / Evaluate / Create} |
| **Module** | {Module Number} - {Module Title} |

## Overview

{2-3 sentences describing what this lab accomplishes}
{Explain the practical value and real-world relevance}

## Learning Objectives

By completing this lab, you will be able to:

- [ ] {Objective 1 - specific and measurable}
- [ ] {Objective 2 - specific and measurable}
- [ ] {Objective 3 - specific and measurable}

## Prerequisites

### Required Knowledge

- {Prior concept or skill 1}
- {Prior concept or skill 2}

### Required Access

- {Account, permission, or credential 1}
- {Account, permission, or credential 2}

## Lab Environment

### Hardware Requirements

| Component | Specification |
|-----------|---------------|
| {Component 1} | {Spec details} |
| {Component 2} | {Spec details} |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| {Software 1} | {X.Y.Z} | {Why it's needed} |
| {Software 2} | {X.Y.Z} | {Why it's needed} |

### Initial Setup

```bash
# Commands to prepare the environment
{setup_command_1}
{setup_command_2}
```

## Step-by-Step Instructions

### Step 1: {Clear Action Title}

**Objective:** {What this step accomplishes in one sentence}

**Instructions:**

1. {First action with specific details}
   
   ```bash
   {exact command to run}
   ```

2. {Second action}

3. {Third action}

**Expected Output:**

```
{What the user should see after completing this step}
```

**Verification:**

- {How to confirm this step succeeded}
- {What to check or look for}

---

### Step 2: {Next Action Title}

**Objective:** {What this step accomplishes}

**Instructions:**

1. {Action details}

   ```{language}
   {code or command}
   ```

2. {Continue with numbered actions}

**Expected Output:**

```
{Expected result}
```

**Verification:**

- {Verification criteria}

---

### Step 3: {Continue Pattern}

{Same structure for all remaining steps}

---

### Step N: {Final Step Title}

{Complete the lab with final configuration or deployment}

## Validation & Testing

### Success Criteria

Verify your lab is complete by confirming:

- [ ] {Criterion 1 - specific and testable}
- [ ] {Criterion 2 - specific and testable}
- [ ] {Criterion 3 - specific and testable}

### Testing Procedure

1. {Test action 1}
   
   ```bash
   {test command}
   ```
   
   **Expected Result:** {what should happen}

2. {Test action 2}
   
   **Expected Result:** {what should happen}

## Troubleshooting

### Issue 1: {Common Problem Description}

**Symptoms:**
- {What the user observes}

**Cause:**
{Why this happens}

**Solution:**

```bash
{Command or steps to fix}
```

---

### Issue 2: {Another Common Problem}

**Symptoms:**
- {Observable behavior}

**Cause:**
{Root cause explanation}

**Solution:**

```bash
{Fix command}
```

---

### Issue 3: {Third Common Problem}

{Same structure}

## Cleanup

To reset your environment after completing this lab:

```bash
# Cleanup commands
{cleanup_command_1}
{cleanup_command_2}
{cleanup_command_3}
```

> ⚠️ **Warning:** {Any important notes about cleanup, e.g., data loss}

## Summary

### What You Accomplished

- {Accomplishment 1}
- {Accomplishment 2}
- {Accomplishment 3}

### Key Takeaways

- {Important concept or skill learned}
- {Best practice discovered}
- {Connection to broader course material}

### Next Steps

- {Suggested follow-up lab or lesson}
- {Additional practice recommendation}

## Additional Resources

- [{Resource 1 title}]({URL}) - {Brief description}
- [{Resource 2 title}]({URL}) - {Brief description}
- [{Official documentation}]({URL}) - {Brief description}
```

---

## Required Sections Checklist

| Section | H Level | Required | Description |
|---------|---------|----------|-------------|
| Lab Title | H1 | ✅ | Format: `# Lab MM-LL-NN: Title` |
| Metadata | H2 | ✅ | Duration, Complexity, Bloom Level table |
| Overview | H2 | ✅ | 2-3 sentence description |
| Learning Objectives | H2 | ✅ | 3-5 checkboxes with measurable outcomes |
| Prerequisites | H2 | ✅ | Knowledge and access requirements |
| Lab Environment | H2 | ✅ | Hardware, software, setup |
| Step-by-Step Instructions | H2 | ✅ | Numbered steps with H3 |
| Each Step | H3 | ✅ | Objective, Instructions, Expected Output, Verification |
| Validation & Testing | H2 | ✅ | Success criteria checklist |
| Troubleshooting | H2 | ✅ | At least 2-3 common issues |
| Cleanup | H2 | ✅ | Commands to reset environment |
| Summary | H2 | ✅ | Accomplishments and takeaways |
| Additional Resources | H2 | Recommended | Links for further learning |

---

## Lab ID Format

Lab IDs follow the pattern: `MM-LL-NN`

| Component | Description | Example |
|-----------|-------------|---------|
| MM | Module number (2 digits) | 01, 02, 10 |
| LL | Lesson number within module (2 digits) | 01, 02, 03 |
| NN | Lab sequence within lesson (2 digits) | 01, 02 |

**Examples:**
- `01-01-01` = Module 1, Lesson 1, Lab 1
- `03-02-01` = Module 3, Lesson 2, Lab 1
- `05-00-01` = Module 5, Module-level lab (not lesson-specific)

---

## Step Structure Rules

### Required Elements per Step

Every step (H3) MUST include:

1. **Objective** - Single sentence stating what this step accomplishes
2. **Instructions** - Numbered list with specific actions
3. **Expected Output** - Code block showing what user should see
4. **Verification** - How to confirm success

### Horizontal Rule Between Steps

Use `---` between steps for visual separation:

```markdown
### Step 1: Title
{content}

---

### Step 2: Title
{content}
```

---

## Code Block Rules

### Always Specify Language

```bash
# Good: Language specified for shell commands
kubectl get pods -n default
```

```yaml
# Good: Language specified for config files
apiVersion: v1
kind: ConfigMap
```

### Use Realistic Commands

**DO:**
```bash
# Real, executable command
kubectl apply -f deployment.yaml
```

**DON'T:**
```bash
# Generic placeholder - AVOID
kubectl apply -f <your-file.yaml>
```

### Supported Languages

- Shell: `bash`, `shell`, `sh`, `powershell`, `cmd`
- Config: `yaml`, `json`, `xml`, `toml`, `ini`
- Code: `python`, `javascript`, `java`, `go`, `rust`
- Infrastructure: `terraform`, `dockerfile`, `kubernetes`

---

## Complexity Guidelines

### Beginner Labs

- 15-30 minutes duration
- 3-5 steps maximum
- Heavy guidance, explicit commands
- Simple success criteria
- Basic troubleshooting

### Intermediate Labs

- 30-60 minutes duration
- 5-10 steps
- Balanced guidance
- Multiple verification points
- Detailed troubleshooting

### Advanced Labs

- 60-120 minutes duration
- 10+ steps
- Less hand-holding
- Complex scenarios
- Comprehensive troubleshooting
- Edge cases covered

---

## Bloom Level Adaptation

| Level | Lab Characteristics |
|-------|---------------------|
| **Remember** | Follow exact commands, reproduce steps |
| **Understand** | Explain what commands do, interpret outputs |
| **Apply** | Modify commands for new scenarios |
| **Analyze** | Debug issues, compare approaches |
| **Evaluate** | Choose between options, justify decisions |
| **Create** | Design solutions, extend functionality |

---

## Troubleshooting Section Rules

### Minimum Requirements

- At least **3 common issues** for Intermediate/Advanced labs
- At least **2 common issues** for Beginner labs

### Issue Structure

Each issue MUST have:
- **Symptoms** - What the user observes
- **Cause** - Why it happens
- **Solution** - Exact commands or steps to fix

### Error Message Inclusion

When relevant, include the actual error message:

```markdown
### Issue: Pod Stuck in CrashLoopBackOff

**Symptoms:**
- Pod status shows `CrashLoopBackOff`
- Error message: `Error: container "app" failed to start`

**Cause:**
The container image is missing or the entrypoint command fails.

**Solution:**
```bash
# Check pod logs
kubectl logs <pod-name> --previous
# Verify image exists
docker pull <image-name>
```
```

---

## Validation Checklist

Before finalizing lab content, verify:

- [ ] Single H1 heading with proper Lab ID format
- [ ] Metadata table with Duration, Complexity, Bloom Level
- [ ] No skipped heading levels (H1 → H2 → H3)
- [ ] All required sections present
- [ ] Each step has Objective, Instructions, Expected Output, Verification
- [ ] Horizontal rules (`---`) between steps
- [ ] Code blocks have language specified
- [ ] Commands are real and executable (no placeholders)
- [ ] At least 2-3 troubleshooting issues
- [ ] Cleanup section with actual commands
- [ ] Duration estimate is realistic for content

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-08 | Initial schema definition |
