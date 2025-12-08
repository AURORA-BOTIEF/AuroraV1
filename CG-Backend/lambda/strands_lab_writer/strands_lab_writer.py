"""
Lab Writer - Agent 2: Step-by-Step Instructions
Reads master plan and generates detailed lab guides.

Features:
- Generates detailed step-by-step instructions for each lab
- Includes prerequisites, setup, execution, verification
- Adds troubleshooting tips
- Formats as professional Markdown
- Considers duration and Bloom level
"""

import os
import json
import boto3
from botocore.config import Config
from datetime import datetime
from typing import Dict, List, Any, Optional

# AWS Clients with extended timeout for Bedrock
bedrock_config = Config(
    read_timeout=600,  # 10 minutes for generating multiple labs
    connect_timeout=60,
    retries={'max_attempts': 3}
)
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=bedrock_config)
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

# Model Configuration
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-5"


def get_secret(secret_name: str) -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"⚠️  Error retrieving secret {secret_name}: {e}")
        return {}


def load_master_plan_from_s3(bucket: str, key: str) -> dict:
    """Load master plan JSON from S3."""
    try:
        print(f"📥 Loading master plan from s3://{bucket}/{key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        plan_data = json.loads(response['Body'].read().decode('utf-8'))
        print(f"✅ Master plan loaded successfully")
        return plan_data
    except Exception as e:
        print(f"❌ Error loading master plan: {e}")
        raise


def call_bedrock_agent(prompt: str, model_id: str) -> str:
    """Call AWS Bedrock with Strands Agents pattern."""
    try:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 32000,  # Enough for 2 labs @ ~15K each
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7
        }
        
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(payload),
            contentType='application/json',
            accept='application/json'
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    
    except Exception as e:
        print(f"❌ Bedrock API error: {e}")
        raise


def call_openai_agent(prompt: str, api_key: str, model_id: str = "gpt-5") -> str:
    """Call OpenAI API."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        # GPT-5 (o1) models use max_completion_tokens instead of max_tokens
        # and don't support temperature or system messages
        if model_id.startswith("o1-") or model_id == "gpt-5":
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=16000
            )
        else:
            # GPT-4 and earlier models
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are an expert technical instructor creating detailed, professional laboratory guides."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=16000,
                temperature=0.7
            )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"❌ OpenAI API error: {e}")
        raise


def generate_lab_guide(
    lab_plan: dict,
    master_context: dict,
    model_provider: str = "bedrock"
) -> str:
    """
    Generate detailed step-by-step lab guide for a single lab.
    
    Args:
        lab_plan: Individual lab plan from master plan
        master_context: Overall context (hardware, software, objectives)
        model_provider: "bedrock" or "openai"
    
    Returns:
        Markdown formatted lab guide
    """
    
    lab_id = lab_plan['lab_id']
    lab_title = lab_plan['lab_title']
    
    print(f"  🔨 Generating lab guide: [{lab_id}] {lab_title}")
    
    # Build context from master plan
    hw_requirements = master_context.get('hardware_requirements', [])
    sw_requirements = master_context.get('software_requirements', [])
    special_considerations = master_context.get('special_considerations', [])
    
    # Build software list
    sw_list = []
    for sw in sw_requirements:
        if isinstance(sw, dict):
            sw_list.append(f"- {sw.get('name')} ({sw.get('version')}): {sw.get('purpose')}")
        else:
            sw_list.append(f"- {sw}")
    
    # Build prompt with standardized schema
    prompt = f"""
You are creating a professional, detailed laboratory guide for technical training.

LAB INFORMATION:
- Lab ID: {lab_id}
- Title: {lab_title}
- Duration: {lab_plan['estimated_duration']} minutes
- Bloom Level: {lab_plan['bloom_level']}
- Complexity: {lab_plan.get('complexity', 'medium')}

OBJECTIVES:
{chr(10).join(f'- {obj}' for obj in lab_plan['objectives'])}

SCOPE:
{lab_plan['scope']}

PREREQUISITES:
{chr(10).join(f'- {prereq}' for prereq in lab_plan.get('prerequisites', ['None']))}

KEY TECHNOLOGIES:
{chr(10).join(f'- {tech}' for tech in lab_plan.get('key_technologies', []))}

EXPECTED OUTCOMES:
{chr(10).join(f'- {outcome}' for outcome in lab_plan.get('expected_outcomes', []))}

AVAILABLE HARDWARE:
{chr(10).join(f'- {hw}' for hw in hw_requirements)}

AVAILABLE SOFTWARE:
{chr(10).join(sw_list)}

SPECIAL CONSIDERATIONS:
{chr(10).join(f'- {consideration}' for consideration in special_considerations)}

═══════════════════════════════════════════════════════════════════════════════
MANDATORY LAB GUIDE STRUCTURE SCHEMA (FOLLOW EXACTLY)
═══════════════════════════════════════════════════════════════════════════════

```markdown
# Lab {lab_id}: {lab_title}

## Metadata

| Property | Value |
|----------|-------|
| **Duration** | {lab_plan['estimated_duration']} minutes |
| **Complexity** | {lab_plan.get('complexity', 'medium').capitalize()} |
| **Bloom Level** | {lab_plan['bloom_level']} |

## Overview

[2-3 sentences describing what this lab accomplishes]
[Explain the practical value and real-world relevance]

## Learning Objectives

By completing this lab, you will be able to:

- [ ] [Objective 1 - specific and measurable]
- [ ] [Objective 2 - specific and measurable]
- [ ] [Objective 3 - specific and measurable]

## Prerequisites

### Required Knowledge

- [Prior concept or skill 1]
- [Prior concept or skill 2]

### Required Access

- [Account, permission, or credential 1]
- [Account, permission, or credential 2]

## Lab Environment

### Hardware Requirements

| Component | Specification |
|-----------|---------------|
| [Component 1] | [Spec details] |
| [Component 2] | [Spec details] |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| [Software 1] | [X.Y.Z] | [Why it's needed] |
| [Software 2] | [X.Y.Z] | [Why it's needed] |

### Initial Setup

```bash
# Commands to prepare the environment
[setup_command_1]
[setup_command_2]
```

## Step-by-Step Instructions

### Step 1: [Clear Action Title]

**Objective:** [What this step accomplishes in one sentence]

**Instructions:**

1. [First action with specific details]
   
   ```bash
   [exact command to run]
   ```

2. [Second action]

3. [Third action]

**Expected Output:**

```
[What the user should see after completing this step]
```

**Verification:**

- [How to confirm this step succeeded]
- [What to check or look for]

---

### Step 2: [Next Action Title]

**Objective:** [What this step accomplishes]

**Instructions:**

1. [Action details]

   ```[language]
   [code or command]
   ```

2. [Continue with numbered actions]

**Expected Output:**

```
[Expected result]
```

**Verification:**

- [Verification criteria]

---

### Step N: [Final Step Title]

[Complete the lab with final configuration or deployment]

## Validation & Testing

### Success Criteria

Verify your lab is complete by confirming:

- [ ] [Criterion 1 - specific and testable]
- [ ] [Criterion 2 - specific and testable]
- [ ] [Criterion 3 - specific and testable]

### Testing Procedure

1. [Test action 1]
   
   ```bash
   [test command]
   ```
   
   **Expected Result:** [what should happen]

2. [Test action 2]
   
   **Expected Result:** [what should happen]

## Troubleshooting

### Issue 1: [Common Problem Description]

**Symptoms:**
- [What the user observes]

**Cause:**
[Why this happens]

**Solution:**

```bash
[Command or steps to fix]
```

---

### Issue 2: [Another Common Problem]

**Symptoms:**
- [Observable behavior]

**Cause:**
[Root cause explanation]

**Solution:**

```bash
[Fix command]
```

---

### Issue 3: [Third Common Problem]

[Same structure]

## Cleanup

To reset your environment after completing this lab:

```bash
# Cleanup commands
[cleanup_command_1]
[cleanup_command_2]
[cleanup_command_3]
```

> ⚠️ **Warning:** [Any important notes about cleanup]

## Summary

### What You Accomplished

- [Accomplishment 1]
- [Accomplishment 2]
- [Accomplishment 3]

### Key Takeaways

- [Important concept or skill learned]
- [Best practice discovered]

### Next Steps

- [Suggested follow-up lab or lesson]
- [Additional practice recommendation]

## Additional Resources

- [Resource 1 title] - [Brief description]
- [Resource 2 title] - [Brief description]
```

═══════════════════════════════════════════════════════════════════════════════
CRITICAL FORMATTING RULES
═══════════════════════════════════════════════════════════════════════════════

**HEADING HIERARCHY (MANDATORY):**
- H1 (#): ONLY for lab title - ONE per document
- H2 (##): Major sections (Metadata, Overview, Steps, Troubleshooting, etc.)
- H3 (###): Steps within instructions, subsections, individual issues
- H4 (####): Details within H3 (if needed)
- NEVER skip heading levels (H1 → H3 is INVALID)

**REQUIRED SECTIONS (ALL MUST BE PRESENT):**
1. Metadata (H2) - Table with Duration, Complexity, Bloom Level
2. Overview (H2) - Brief description
3. Learning Objectives (H2) - 3-5 checkboxes
4. Prerequisites (H2) - Knowledge and access requirements
5. Lab Environment (H2) - Hardware, software, setup
6. Step-by-Step Instructions (H2) - Numbered steps as H3
7. Validation & Testing (H2) - Success criteria
8. Troubleshooting (H2) - At least 2-3 common issues
9. Cleanup (H2) - Reset commands
10. Summary (H2) - Accomplishments and takeaways

**STEP STRUCTURE (EVERY STEP MUST HAVE):**
- Objective - One sentence stating what this step accomplishes
- Instructions - Numbered list with specific actions
- Expected Output - Code block showing what user should see
- Verification - How to confirm success
- Use `---` horizontal rules between steps

**CODE BLOCKS (ALWAYS SPECIFY LANGUAGE):**
- Use REAL, EXECUTABLE commands - NO placeholders like <filename> or YOUR_VALUE
- Specify language: bash, python, yaml, json, etc.
- Include actual expected output

**COMPLEXITY GUIDELINES:**
- Beginner: 3-5 steps, heavy guidance, explicit commands
- Intermediate: 5-10 steps, balanced guidance
- Advanced: 10+ steps, less hand-holding

**BLOOM LEVEL ADAPTATION:**
- Remember/Understand: More explanation, guided steps
- Apply: Balanced guidance and independent work
- Analyze/Evaluate: More independent problem-solving
- Create: Less hand-holding, open-ended challenges

═══════════════════════════════════════════════════════════════════════════════

Return ONLY the Markdown content following this schema exactly, no additional commentary.
"""
    
    try:
        if model_provider == "openai":
            secret_data = get_secret("aurora/openai-api-key")
            api_key = secret_data.get('api_key') or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                print("    ⚠️  OpenAI API key not found, falling back to Bedrock")
                model_provider = "bedrock"
            else:
                lab_guide = call_openai_agent(prompt, api_key, DEFAULT_OPENAI_MODEL)
        
        if model_provider == "bedrock":
            lab_guide = call_bedrock_agent(prompt, DEFAULT_BEDROCK_MODEL)
        
        # Clean up markdown if wrapped in code blocks
        if "```markdown" in lab_guide:
            lab_guide = lab_guide.split("```markdown")[1].split("```")[0].strip()
        elif lab_guide.startswith("```") and lab_guide.endswith("```"):
            lab_guide = lab_guide[3:-3].strip()
        
        print(f"    ✅ Lab guide generated ({len(lab_guide)} characters)")
        return lab_guide
    
    except Exception as e:
        print(f"    ❌ Error generating lab guide: {e}")
        raise


def save_lab_guide_to_s3(
    bucket: str,
    project_folder: str,
    lab_id: str,
    lab_title: str,
    lab_guide: str
) -> str:
    """Save lab guide Markdown to S3."""
    try:
        # Format filename
        safe_title = lab_title.lower()
        safe_title = ''.join(c if c.isalnum() or c.isspace() else '' for c in safe_title)
        safe_title = '-'.join(safe_title.split())[:50]  # Limit length
        
        filename = f"lab-{lab_id}-{safe_title}.md"
        key = f"{project_folder}/labguide/{filename}"
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=lab_guide.encode('utf-8'),
            ContentType='text/markdown'
        )
        
        print(f"    💾 Saved to s3://{bucket}/{key}")
        return key
    
    except Exception as e:
        print(f"    ❌ Error saving lab guide: {e}")
        raise


def generate_all_labs_batch(
    lab_plans: List[Dict[str, Any]],
    master_context: dict,
    model_provider: str = "bedrock"
) -> Dict[str, str]:
    """
    Generate ALL lab guides in a SINGLE API call for efficiency.
    
    Returns dict mapping lab_id to markdown content.
    """
    print(f"\n🚀 Generating {len(lab_plans)} labs in SINGLE API CALL...")
    
    # Build comprehensive prompt for ALL labs
    labs_summary = []
    for lab in lab_plans:
        labs_summary.append(f"""
**Lab {lab['lab_id']}: {lab['lab_title']}**
- Duration: {lab['estimated_duration']} minutes
- Complexity: {lab.get('complexity', 'medium')}
- Bloom Level: {lab['bloom_level']}
- Objectives: {', '.join(lab['objectives'])}
- Scope: {lab['scope']}
- Prerequisites: {', '.join(lab.get('prerequisites', []))}
- Technologies: {', '.join(lab.get('key_technologies', []))}
""")
    
    prompt = f"""
You are an expert technical instructor creating detailed, professional laboratory guides.

LANGUAGE REQUIREMENT:
**GENERATE ALL LAB CONTENT IN: {master_context.get('target_language', 'English')}**

- All headings, instructions, explanations must be in {master_context.get('target_language', 'English')}
- Use proper {master_context.get('target_language', 'English')} terminology and idioms
- Command outputs can remain in their original language (usually English)
- Code comments should be in {master_context.get('target_language', 'English')} where appropriate

MASTER CONTEXT:
Overall Objectives: {', '.join(master_context.get('overall_objectives', []))}

Hardware Requirements:
{chr(10).join('- ' + req for req in master_context.get('hardware_requirements', []))}

Software Requirements:
{chr(10).join(f"- {sw['name']} ({sw['version']}): {sw['purpose']}" for sw in master_context.get('software_requirements', []))}

Special Considerations:
{chr(10).join('- ' + con for con in master_context.get('special_considerations', []))}

LABS TO GENERATE ({len(lab_plans)} total):
{chr(10).join(labs_summary)}

═══════════════════════════════════════════════════════════════════════════════
MANDATORY LAB GUIDE STRUCTURE SCHEMA (FOLLOW EXACTLY FOR EACH LAB)
═══════════════════════════════════════════════════════════════════════════════

Each lab MUST follow this EXACT structure with proper heading hierarchy:

```
# Lab [LAB_ID]: [Lab Title]

## Metadata

| Property | Value |
|----------|-------|
| **Duration** | XX minutes |
| **Complexity** | Beginner/Intermediate/Advanced |
| **Bloom Level** | [Level] |

## Overview

[2-3 sentences describing what this lab accomplishes]
[Explain the practical value and real-world relevance]

## Learning Objectives

By completing this lab, you will be able to:

- [ ] [Objective 1 - specific and measurable]
- [ ] [Objective 2 - specific and measurable]
- [ ] [Objective 3 - specific and measurable]

## Prerequisites

### Required Knowledge

- [Prior concept or skill 1]
- [Prior concept or skill 2]

### Required Access

- [Account, permission, or credential 1]

## Lab Environment

### Hardware Requirements

| Component | Specification |
|-----------|---------------|
| [Component] | [Spec] |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| [Software] | [X.Y.Z] | [Why needed] |

### Initial Setup

```bash
# Setup commands
```

## Step-by-Step Instructions

### Step 1: [Clear Action Title]

**Objective:** [What this step accomplishes]

**Instructions:**

1. [First action]
   
   ```bash
   [exact command]
   ```

2. [Second action]

**Expected Output:**

```
[What user should see]
```

**Verification:**

- [How to confirm success]

---

### Step 2: [Next Action Title]

[Same structure - Objective, Instructions, Expected Output, Verification]

---

[Continue for all steps needed]

## Validation & Testing

### Success Criteria

- [ ] [Criterion 1 - testable]
- [ ] [Criterion 2 - testable]

### Testing Procedure

1. [Test action]
   ```bash
   [test command]
   ```
   **Expected Result:** [result]

## Troubleshooting

### Issue 1: [Problem Description]

**Symptoms:**
- [What user observes]

**Cause:**
[Why it happens]

**Solution:**
```bash
[fix command]
```

---

### Issue 2: [Another Problem]

[Same structure]

## Cleanup

```bash
# Cleanup commands
```

> ⚠️ **Warning:** [Important notes]

## Summary

### What You Accomplished

- [Accomplishment 1]
- [Accomplishment 2]

### Key Takeaways

- [Concept learned]

### Next Steps

- [Follow-up recommendation]

## Additional Resources

- [Resource 1] - [Description]
```

═══════════════════════════════════════════════════════════════════════════════
CRITICAL FORMATTING RULES
═══════════════════════════════════════════════════════════════════════════════

**HEADING HIERARCHY (MANDATORY):**
- H1 (#): ONLY for lab title - ONE per lab
- H2 (##): Major sections
- H3 (###): Steps, subsections, issues
- NEVER skip heading levels (H1 → H3 is INVALID)

**REQUIRED SECTIONS (ALL MUST BE PRESENT FOR EACH LAB):**
1. Metadata (H2) - Table with Duration, Complexity, Bloom Level
2. Overview (H2)
3. Learning Objectives (H2) - With checkboxes
4. Prerequisites (H2)
5. Lab Environment (H2)
6. Step-by-Step Instructions (H2) - Steps as H3
7. Validation & Testing (H2)
8. Troubleshooting (H2) - At least 2 issues
9. Cleanup (H2)
10. Summary (H2)

**STEP STRUCTURE (EVERY STEP MUST HAVE):**
- Objective, Instructions, Expected Output, Verification
- Use `---` between steps

**CODE BLOCKS:**
- REAL, EXECUTABLE commands - NO placeholders like <filename>
- Always specify language (bash, python, yaml, etc.)

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (USE DELIMITERS)
═══════════════════════════════════════════════════════════════════════════════

---LAB_START---
LAB_ID: [lab_id]
---MARKDOWN---
# Lab [lab_id]: [Full Title]

[Complete markdown following the schema above]

---LAB_END---

---LAB_START---
LAB_ID: [next_lab_id]
---MARKDOWN---
# Lab [next_lab_id]: [Next Lab Title]
...
---LAB_END---

IMPORTANT: Use the delimiter format exactly as shown. Do NOT use JSON format.
Generate ALL {len(lab_plans)} labs now:
"""
    
    try:
        if model_provider == "openai":
            secret_data = get_secret("aurora/openai-api-key")
            api_key = secret_data.get('api_key') or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                print("⚠️  OpenAI API key not found, falling back to Bedrock")
                model_provider = "bedrock"
            else:
                response_text = call_openai_agent(prompt, api_key, DEFAULT_OPENAI_MODEL)
        
        if model_provider == "bedrock":
            response_text = call_bedrock_agent(prompt, DEFAULT_BEDROCK_MODEL)
        
        print("✅ AI response received, parsing with delimiters...")
        
        # Parse using delimiters instead of JSON
        labs_dict = {}
        
        # Split by lab sections
        lab_sections = response_text.split('---LAB_START---')
        
        for section in lab_sections[1:]:  # Skip first empty split
            if '---LAB_END---' not in section:
                continue
            
            # Extract lab_id and markdown
            try:
                header_part, rest = section.split('---MARKDOWN---', 1)
                markdown_part = rest.split('---LAB_END---')[0].strip()
                
                # Extract lab_id from header
                for line in header_part.split('\n'):
                    if line.startswith('LAB_ID:'):
                        lab_id = line.replace('LAB_ID:', '').strip()
                        labs_dict[lab_id] = markdown_part
                        print(f"  ✓ Lab {lab_id}: {len(markdown_part)} characters")
                        break
            except Exception as e:
                print(f"  ⚠️  Failed to parse lab section: {e}")
                continue
        
        if not labs_dict:
            print("⚠️  No labs found in response, trying fallback JSON parsing...")
            # Fallback to JSON if delimiter format failed
            try:
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0]
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0]
                
                result = json.loads(response_text.strip())
                for lab_data in result.get('labs', []):
                    lab_id = lab_data['lab_id']
                    markdown = lab_data['markdown']
                    labs_dict[lab_id] = markdown
                    print(f"  ✓ Lab {lab_id}: {len(markdown)} characters (from JSON)")
            except Exception as fallback_error:
                print(f"⚠️  Fallback JSON parsing also failed: {fallback_error}")
                
                # Third fallback: If only ONE lab requested and response looks like markdown, use it directly
                if len(lab_plans) == 1:
                    print("🔄 Trying raw markdown fallback for single lab...")
                    raw_response = response_text if 'response_text' in dir() else ""
                    # Check if the response looks like valid markdown (starts with # or has markdown patterns)
                    if raw_response and (raw_response.strip().startswith('#') or 
                                        raw_response.strip().startswith('```') or
                                        '##' in raw_response[:500]):
                        lab_id = lab_plans[0]['lab_id']
                        labs_dict[lab_id] = raw_response.strip()
                        print(f"  ✓ Lab {lab_id}: {len(raw_response)} characters (from raw markdown)")
                    else:
                        raise ValueError("Could not parse labs from AI response in any format")
                else:
                    raise ValueError("Could not parse labs from AI response in any format")
        
        print(f"✅ Successfully generated {len(labs_dict)} lab guides")
        return labs_dict
    
    except Exception as e:
        print(f"❌ Error generating batch labs: {e}")
        print(f"Response preview: {response_text[:1000] if 'response_text' in locals() else 'N/A'}...")
        raise


def lambda_handler(event, context):
    """
    Lambda handler for Lab Writer (Agent 2).
    
    Input event:
    {
        "course_bucket": "crewai-course-artifacts",
        "master_plan_key": "project/labguide/lab-master-plan.json",
        "project_folder": "251014-kubernetes-course",
        "model_provider": "bedrock"
    }
    
    Output:
    {
        "statusCode": 200,
        "lab_guides_generated": 15,
        "lab_guide_keys": ["project/labguide/lab-01-01-01-setup.md", ...],
        "project_folder": "251014-kubernetes-course",
        "bucket": "crewai-course-artifacts"
    }
    """
    
    print("\n" + "="*70)
    print("📝 LAB WRITER - AGENT 2: STEP-BY-STEP INSTRUCTIONS")
    print("="*70)
    
    try:
        # Extract parameters
        course_bucket = event.get('course_bucket', 'crewai-course-artifacts')
        master_plan_key = event['master_plan_key']
        project_folder = event['project_folder']
        model_provider = event.get('model_provider', 'bedrock')
        
        # FORCE Bedrock for lab generation (more reliable format compliance)
        # GPT-5 shows model drift: correct format initially, missing headers later
        # Claude Sonnet 4.5 consistently generates proper lab headers
        model_provider = 'bedrock'
        
        lab_ids_to_process = event.get('lab_ids', [])  # NEW: For batch processing
        
        print(f"📦 Bucket: {course_bucket}")
        print(f"📋 Master Plan: {master_plan_key}")
        print(f"📁 Project: {project_folder}")
        print(f"🤖 Model: {model_provider} (forced to Bedrock for lab reliability)")
        if lab_ids_to_process:
            print(f"🎯 Batch Mode: Processing specific labs: {', '.join(lab_ids_to_process)}")
        else:
            print(f"🎯 Full Mode: Processing all labs")
        
        # Step 1: Load master plan
        master_plan = load_master_plan_from_s3(course_bucket, master_plan_key)
        
        lab_plans = master_plan.get('lab_plans', [])
        if not lab_plans:
            print("⚠️  No lab plans found in master plan!")
            return {
                'statusCode': 400,
                'error': 'No lab plans found in master plan'
            }
        
        # NEW: Filter to only process specified labs if batch mode
        if lab_ids_to_process:
            original_count = len(lab_plans)
            lab_plans = [lab for lab in lab_plans if lab['lab_id'] in lab_ids_to_process]
            print(f"📊 Filtered {original_count} labs → {len(lab_plans)} labs for this batch")
        
        # Extract language from metadata
        course_language = master_plan.get('metadata', {}).get('course_language', 'en')
        language_names = {
            'en': 'English',
            'es': 'Spanish (Español)',
            'fr': 'French (Français)',
            'de': 'German (Deutsch)',
            'pt': 'Portuguese (Português)',
            'it': 'Italian (Italiano)'
        }
        target_language = language_names.get(course_language, 'English')
        
        print(f"\n🌐 Target Language: {target_language} ({course_language})")
        print(f"📊 Total labs to generate: {len(lab_plans)}\n")
        
        # Build master context for all labs (including language)
        master_context = {
            'hardware_requirements': master_plan.get('hardware_requirements', []),
            'software_requirements': master_plan.get('software_requirements', []),
            'special_considerations': master_plan.get('special_considerations', []),
            'overall_objectives': master_plan.get('overall_objectives', []),
            'target_language': target_language  # NEW: Pass language to prompt
        }
        
        # Step 2: Generate lab guides ONE AT A TIME for reliability
        # Both GPT-5 and Bedrock handle single-lab requests reliably
        # GPT-5 sometimes skips labs in multi-lab requests
        labs_markdown = {}
        
        for idx, lab_plan in enumerate(lab_plans, start=1):
            lab_id = lab_plan['lab_id']
            print(f"\n📦 Lab {idx}/{len(lab_plans)}: Generating {lab_id}...")
            
            try:
                # Generate ONE lab at a time (pass as single-item list)
                batch_results = generate_all_labs_batch(
                    lab_plans=[lab_plan],  # Always single lab for reliability
                    master_context=master_context,
                    model_provider=model_provider
                )
                labs_markdown.update(batch_results)
            except Exception as e:
                print(f"❌ Lab {lab_id} generation failed: {e}")
                # Continue with next lab instead of failing completely
                continue
        
        # Step 3: Save each lab guide to S3
        lab_guide_keys = []
        print(f"\n💾 Saving {len(labs_markdown)} lab guides to S3...")
        
        for lab_plan in lab_plans:
            lab_id = lab_plan['lab_id']
            
            if lab_id not in labs_markdown:
                print(f"  ⚠️  Lab {lab_id} not found in generated content, skipping")
                continue
            
            try:
                lab_key = save_lab_guide_to_s3(
                    bucket=course_bucket,
                    project_folder=project_folder,
                    lab_id=lab_id,
                    lab_title=lab_plan['lab_title'],
                    lab_guide=labs_markdown[lab_id]
                )
                lab_guide_keys.append(lab_key)
                print(f"  ✅ Saved lab {lab_id}")
            except Exception as e:
                print(f"  ❌ Failed to save lab {lab_id}: {e}")
                continue
        
        print(f"\n{'='*70}")
        print(f"✅ LAB WRITING COMPLETED")
        print(f"   Generated: {len(lab_guide_keys)}/{len(lab_plans)} labs")
        print(f"{'='*70}\n")
        
        return {
            'statusCode': 200,
            'lab_guides_generated': len(lab_guide_keys),
            'lab_guide_keys': lab_guide_keys,
            'project_folder': project_folder,
            'bucket': course_bucket,
            'model_provider': model_provider
        }
    
    except KeyError as e:
        print(f"❌ Missing required parameter: {e}")
        return {
            'statusCode': 400,
            'error': f'Missing required parameter: {e}'
        }
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'error': str(e)
        }
