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
            "max_tokens": 16000,
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
    
    # Build prompt
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

YOUR TASK:
Create a complete, professional laboratory guide in Markdown format following this EXACT structure:

```markdown
# Lab {lab_id}: {lab_title}

## Overview
Brief description of what this lab accomplishes and why it matters.

## Learning Objectives
- Objective 1 (copy from above)
- Objective 2
- ...

## Prerequisites
- Prerequisite 1 (from above)
- Prerequisite 2
- ...

## Estimated Duration
{lab_plan['estimated_duration']} minutes

## Lab Environment Setup

### Hardware Requirements
- Requirement 1
- Requirement 2

### Software Requirements
- Software 1 (version): purpose
- Software 2 (version): purpose

### Initial Setup Steps
1. First setup step with clear command or action
2. Second setup step
3. ...

## Step-by-Step Instructions

### Step 1: [Clear Step Title]
**Objective:** What this step accomplishes

**Instructions:**
1. First action with exact command if applicable
   ```bash
   # Example command with explanation
   command here
   ```
2. Second action
3. Third action

**Verification:**
- How to verify this step worked
- Expected output or result

**Troubleshooting:**
- Common issue 1: solution
- Common issue 2: solution

### Step 2: [Next Step Title]
[Same structure as Step 1]

### Step 3: [Continue...]
[Continue for all major steps needed to complete the lab]

## Validation & Testing

### Success Criteria
- Criterion 1: How to verify
- Criterion 2: How to verify
- ...

### Testing Procedure
1. Test step 1
2. Test step 2
3. Expected results

## Cleanup (if applicable)
1. Cleanup action 1
2. Cleanup action 2
3. ...

## Summary
Brief recap of what was accomplished and key takeaways.

## Additional Resources
- Resource 1: Brief description
- Resource 2: Brief description
- ...

## Common Issues & Solutions

### Issue 1: [Issue Description]
**Symptoms:** What the user sees
**Cause:** Why it happens
**Solution:** How to fix it

### Issue 2: [Next Issue]
[Same structure]

## Notes
- Important note 1
- Important note 2
```

CRITICAL REQUIREMENTS:
1. Use EXACT commands and file paths - be specific, not generic
2. Include actual code/commands in code blocks with syntax highlighting
3. Each step should be clear enough for someone to follow without prior knowledge
4. Include verification steps after major actions
5. Anticipate 2-3 common errors and provide solutions
6. Time estimates should match the {lab_plan['estimated_duration']} minute duration
7. Difficulty should match "{lab_plan.get('complexity', 'medium')}" complexity
8. All instructions must be actionable and testable
9. Use professional technical writing style
10. Include success criteria that are measurable

Consider the Bloom level "{lab_plan['bloom_level']}":
- Remember/Understand: More explanation, guided steps
- Apply: Balanced guidance and independent work
- Analyze/Evaluate: More independent problem-solving
- Create: Less hand-holding, more open-ended challenges

Return ONLY the Markdown content, no additional commentary.
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

YOUR TASK:
Generate COMPLETE, DETAILED step-by-step instructions for ALL {len(lab_plans)} labs above.

OUTPUT FORMAT (use delimiters):
---LAB_START---
LAB_ID: 03-01-01
---MARKDOWN---
# Lab 03-01-01: Full Title

## Overview
...complete markdown content...

---LAB_END---

---LAB_START---
LAB_ID: 03-02-01
---MARKDOWN---
# Lab 03-02-01: Next Lab Title
...
---LAB_END---

For EACH lab, the markdown MUST include:

1. **Header**: Lab ID, title, duration, complexity
2. **Overview**: Brief description (2-3 sentences)
3. **Learning Objectives**: 3-5 specific, measurable outcomes
4. **Prerequisites**: Knowledge/skills/tools needed
5. **Lab Environment Setup**: 
   - Hardware/software requirements specific to this lab
   - Initial configuration steps
6. **Step-by-Step Instructions** (numbered):
   - Clear, actionable steps
   - EXACT commands with syntax highlighting
   - Expected outputs
   - Verification steps
7. **Validation**: How to confirm successful completion
8. **Troubleshooting**: 3-5 common issues with solutions
9. **Cleanup**: Steps to reset environment (if needed)
10. **Next Steps/Additional Resources**: What to explore next

CRITICAL REQUIREMENTS:
- Use REAL, EXECUTABLE commands - no placeholders like <filename>
- Include actual code in ```language blocks
- Each step must be testable and verifiable
- Match the specified duration and complexity
- Adapt detail level to Bloom taxonomy level
- Professional technical writing style
- Success criteria must be measurable

IMPORTANT: Use the delimiter format exactly as shown. Do NOT use JSON format.
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
                print(f"❌ Fallback JSON parsing also failed: {fallback_error}")
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
        
        print(f"📦 Bucket: {course_bucket}")
        print(f"📋 Master Plan: {master_plan_key}")
        print(f"📁 Project: {project_folder}")
        print(f"🤖 Model: {model_provider}")
        
        # Step 1: Load master plan
        master_plan = load_master_plan_from_s3(course_bucket, master_plan_key)
        
        lab_plans = master_plan.get('lab_plans', [])
        if not lab_plans:
            print("⚠️  No lab plans found in master plan!")
            return {
                'statusCode': 400,
                'error': 'No lab plans found in master plan'
            }
        
        print(f"\n📊 Total labs to generate: {len(lab_plans)}\n")
        
        # Build master context for all labs
        master_context = {
            'hardware_requirements': master_plan.get('hardware_requirements', []),
            'software_requirements': master_plan.get('software_requirements', []),
            'special_considerations': master_plan.get('special_considerations', []),
            'overall_objectives': master_plan.get('overall_objectives', [])
        }
        
        # Step 2: Generate ALL lab guides in a SINGLE API call
        try:
            labs_markdown = generate_all_labs_batch(
                lab_plans=lab_plans,
                master_context=master_context,
                model_provider=model_provider
            )
        except Exception as e:
            print(f"❌ Batch generation failed: {e}")
            return {
                'statusCode': 500,
                'error': f'Failed to generate labs: {str(e)}'
            }
        
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
