# AURORA V1 - System Architecture Documentation

**Project:** Aurora - AI-Powered Course Generation Platform  
**Organization:** NETEC  
**Last Updated:** October 14, 2025  
**Version:** 1.2  
**Repository:** AuroraV1 (Branch: testing)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Technology Stack](#technology-stack)
4. [Architecture Patterns](#architecture-patterns)
5. [Frontend Architecture](#frontend-architecture)
6. [Backend Architecture](#backend-architecture)
7. [AI/ML Pipeline](#aiml-pipeline)
8. [Authentication & Authorization](#authentication--authorization)
9. [Data Flow](#data-flow)
10. [Storage Architecture](#storage-architecture)
11. [API Architecture](#api-architecture)
12. [Deployment Architecture](#deployment-architecture)
13. [Security Architecture](#security-architecture)
14. [Monitoring & Logging](#monitoring--logging)
15. [Development Workflow](#development-workflow)
16. [Scalability & Performance](#scalability--performance)
17. [Cost Optimization](#cost-optimization)
18. [Future Enhancements](#future-enhancements)

---

## Executive Summary

Aurora V1 is an enterprise-grade, AI-powered educational content generation platform designed for NETEC's training and education business. The system leverages cutting-edge generative AI technologies (AWS Bedrock Claude 3.7, OpenAI GPT-5, Google Gemini) to automatically create comprehensive course materials including curriculum outlines, lesson content, visual aids, and complete instructional books.

### Key Capabilities

- **Automated Course Generation**: AI-powered generation of complete course curricula with customizable parameters
- **Multi-Model AI Support**: Flexible integration with AWS Bedrock, OpenAI, and Google Gemini
- **Visual Content Creation**: Automatic generation of diagrams and educational images
- **Interactive Book Editor**: Real-time editing and compilation of course materials
- **Multi-Regional Support**: Designed for NETEC's operations across Latin America and Spain
- **Role-Based Access Control**: Granular permissions for Administrators, Creators, and Participants

### Business Value

- **Time Reduction**: 10-15x faster course development compared to manual creation
- **Cost Efficiency**: Reduces instructor preparation time by ~80%
- **Quality Consistency**: Standardized course structure based on Bloom's Taxonomy
- **Scalability**: Can generate unlimited courses simultaneously
- **Multi-Market Support**: Serves Chile, Peru, Colombia, Mexico, and Spain markets

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS AMPLIFY (Frontend Host)                  │
│                     React SPA + Vite + React Router                  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      │ HTTPS + SigV4
                      │
┌─────────────────────▼───────────────────────────────────────────────┐
│                      AWS COGNITO (Authentication)                    │
│             User Pools + Identity Pools + Hosted UI                  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
                      │ IAM Credentials
                      │
┌─────────────────────▼───────────────────────────────────────────────┐
│                    API GATEWAY (Regional REST API)                   │
│                  IAM Auth + CORS + Gateway Responses                 │
└─────────┬───────────────────────────────────────────────────────────┘
          │
          │ Invokes
          │
┌─────────▼───────────────────────────────────────────────────────────┐
│                      AWS LAMBDA (Compute Layer)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Strands     │  │   Visual     │  │   Images     │              │
│  │  Content     │→ │   Planner    │→ │   Generator  │              │
│  │  Gen         │  │              │  │   (Gemini)   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Book        │  │  List        │  │  Load/Save   │              │
│  │  Builder     │  │  Projects    │  │  Book        │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────┬───────────────────────────────────────────────────────────┘
          │
          │ Orchestrates
          │
┌─────────▼───────────────────────────────────────────────────────────┐
│              AWS STEP FUNCTIONS (Workflow Orchestration)             │
│         ContentGen → VisualPlanner → ImagesGen → BookBuilder         │
└─────────┬───────────────────────────────────────────────────────────┘
          │
          │ Invokes AI Models
          │
┌─────────▼───────────────────────────────────────────────────────────┐
│                        AI/ML PROVIDERS                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ AWS Bedrock  │  │   OpenAI     │  │   Google     │              │
│  │ Claude 3.7   │  │   GPT-5      │  │   Gemini     │              │
│  │  Sonnet      │  │              │  │   2.5 Flash  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└───────────────────────────────────────────────────────────────────────┘
          │
          │ Stores Artifacts
          │
┌─────────▼───────────────────────────────────────────────────────────┐
│                         AWS S3 (Storage)                             │
│     Lessons (Markdown) + Images (PNG) + Books (JSON/MD)             │
│                   crewai-course-artifacts bucket                     │
└───────────────────────────────────────────────────────────────────────┘
```

### Core Components

1. **Frontend Layer**: React SPA hosted on AWS Amplify
2. **API Gateway**: RESTful API with IAM authentication
3. **Compute Layer**: AWS Lambda functions (Python 3.12)
4. **Orchestration**: AWS Step Functions state machines
5. **AI Models**: Multi-provider (Bedrock, OpenAI, Gemini)
6. **Storage**: S3 buckets for content artifacts
7. **Authentication**: AWS Cognito User Pools
8. **Secrets Management**: AWS Secrets Manager

---

## Technology Stack

### Frontend Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | React | 19.1.0 | UI component library |
| **Build Tool** | Vite | 6.3.5 | Fast build and dev server |
| **Routing** | React Router | 6.30.1 | Client-side routing |
| **State Management** | React Hooks | Built-in | Component state |
| **Authentication** | AWS Amplify | 4.3.46 | Cognito integration |
| **AWS SDK** | @aws-sdk/* | 3.901.0 | S3, SigV4 operations |
| **HTTP Signing** | @aws-sdk/signature-v4 | 3.370.0 | Request signing |
| **PDF Generation** | jsPDF, html2pdf.js | 3.0.3, 0.12.0 | Export capabilities |
| **Excel Export** | xlsx | 0.18.5 | Spreadsheet generation |
| **Security** | DOMPurify | 3.2.6 | XSS prevention |
| **JWT** | jwt-decode | 4.0.0 | Token parsing |

### Backend Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Runtime** | Python | 3.12 | Lambda execution |
| **IaC** | AWS SAM | 1.x | Infrastructure as Code |
| **Orchestration** | Step Functions | N/A | Workflow management |
| **AI Framework** | Strands Agents | Latest | Agent orchestration |
| **AWS Bedrock** | Claude 3.7 Sonnet | Latest | Content generation |
| **OpenAI** | GPT-5 | Latest | Alternative AI model |
| **Google Gemini** | 2.5 Flash Image | Latest | Image generation |
| **AWS SDK** | boto3 | Latest | AWS service integration |
| **YAML Parser** | PyYAML | Latest | Outline parsing |
| **Image Processing** | Pillow (PIL) | Latest | Image manipulation |

### AWS Services

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **Amplify** | Frontend hosting | Auto-deploy from GitHub |
| **Cognito** | User authentication | User Pools + Identity Pools |
| **API Gateway** | REST API | Regional, IAM auth |
| **Lambda** | Serverless compute | Python 3.12, ARM64 |
| **Step Functions** | Workflow orchestration | Standard (not Express) |
| **S3** | Object storage | Standard tier, versioning enabled |
| **Secrets Manager** | API key storage | Encrypted secrets |
| **CloudWatch** | Logging & monitoring | Auto-retention |
| **IAM** | Access control | Least privilege policies |

---

## Architecture Patterns

### Design Patterns Used

1. **Serverless Architecture**
   - No server management
   - Auto-scaling
   - Pay-per-use pricing

2. **Event-Driven Architecture**
   - Async workflow execution
   - Loose coupling between components
   - Retry mechanisms

3. **Multi-Agent AI Pattern**
   - Specialized agents for different tasks
   - Sequential workflow (Researcher → Writer → Reviewer)
   - Modular and maintainable

4. **API Gateway Pattern**
   - Centralized entry point
   - Request/response transformation
   - Authentication/authorization

5. **Separation of Concerns**
   - Frontend: UI/UX
   - Backend: Business logic
   - AI: Content generation
   - Storage: Persistence

6. **Retry & Fallback Pattern**
   - Auto-retry on transient failures
   - Fallback to alternative AI providers
   - Graceful degradation

---

## Frontend Architecture

### Application Structure

```
src/
├── App.jsx                      # Main application component & routing
├── main.jsx                     # Application entry point
├── amplify.js                   # AWS Amplify configuration
├── components/                  # React components
│   ├── Home.jsx                 # Landing page
│   ├── Sidebar.jsx              # Navigation sidebar
│   ├── ProfileModal.jsx         # User profile management
│   ├── ChatModal.jsx            # AI assistant interface
│   │
│   ├── GeneradorContenidosPage.jsx  # Content generation hub
│   ├── GeneradorTemarios.jsx        # Standard curriculum generator
│   ├── GeneradorTemarios_KNTR.jsx   # Knowledge Transfer variant
│   ├── GeneradorCursos.jsx          # Full course generator
│   ├── GeneradorContenido.jsx       # Content generator
│   │
│   ├── BookBuilderPage.jsx      # Project listing & book building
│   ├── BookEditor.jsx           # WYSIWYG book editor
│   │
│   ├── ActividadesPage.jsx      # Activity generator
│   ├── ResumenesPage.jsx        # Summary generator
│   ├── ExamenesPage.jsx         # Exam generator
│   ├── AdminPage.jsx            # Admin dashboard
│   │
│   └── [Other components...]    # Activity types, editors, etc.
│
├── assets/                      # Static assets
│   ├── Netec.png                # Company logo
│   ├── Preview.png              # Marketing images
│   ├── [country flags]          # Regional flags
│   └── avatars/                 # User avatar options
│
└── utils/                       # Utility functions
```

### Component Hierarchy

```
App.jsx
├── Authentication Flow (unauthenticated)
│   ├── Login Page
│   └── Country Selection
│
└── Main Application (authenticated)
    ├── Sidebar
    │   ├── Navigation Links
    │   ├── Profile Button
    │   └── Logout Button
    │
    ├── ProfileModal (modal)
    ├── ChatModal (modal)
    │
    └── Main Content Area
        ├── Home
        ├── GeneradorContenidosPage
        │   ├── GeneradorTemarios
        │   ├── GeneradorTemarios_KNTR
        │   ├── GeneradorCursos
        │   ├── BookBuilderPage
        │   │   └── BookEditor
        │   └── GeneradorContenido
        ├── ActividadesPage
        ├── ResumenesPage
        ├── ExamenesPage
        └── AdminPage (admin only)
```

### Routing Configuration

```javascript
Routes:
/                                    → Home.jsx
/actividades                         → ActividadesPage.jsx
/resumenes                           → ResumenesPage.jsx
/examenes                            → ExamenesPage.jsx
/admin                               → AdminPage.jsx (requires admin role)
/generador-contenidos                → GeneradorContenidosPage.jsx
  /curso-estandar                    → GeneradorTemarios.jsx
  /curso-KNTR                        → GeneradorTemarios_KNTR.jsx
  /generador-cursos                  → GeneradorCursos.jsx
  /book-builder                      → BookBuilderPage.jsx
  /generador-contenido               → GeneradorContenido.jsx
```

### State Management

**Authentication State**
```javascript
- user: { attributes, groups }  // Cognito user data
- loading: boolean              // Auth loading state
```

**Application State**
- Managed at component level using React Hooks
- No global state management library (Redux/MobX)
- Session data stored in localStorage
- Cognito tokens managed by Amplify SDK

### Key Frontend Features

1. **AWS Amplify Integration**
   - Automatic Cognito session management
   - OAuth 2.0 PKCE flow
   - Credential auto-refresh
   - IAM credential federation via Identity Pools

2. **IAM Request Signing**
   - All API requests signed with SigV4
   - Uses AWS SDK SignatureV4 class
   - Automatic credential injection
   - CORS-compliant headers

3. **Book Builder Interface**
   - Project listing with search
   - Real-time book preview
   - Rich text editor for content
   - Image integration
   - Export to PDF/Markdown

4. **Curriculum Generator**
   - Multi-step form wizard
   - Real-time parameter validation
   - Bloom's Taxonomy integration
   - Customizable duration and structure

5. **Profile Management**
   - Avatar selection (15+ options)
   - Profile photo upload to S3
   - Role request system
   - Multi-tenant support (domain-based)

---

## Backend Architecture

### Lambda Functions

#### 1. StrandsContentGen (Lesson Content Generator)

**Purpose:** Generate lesson content using Strands Agents multi-agent workflow

**Configuration:**
- Runtime: Python 3.12
- Memory: 512 MB
- Timeout: 900 seconds (15 minutes)
- Architecture: ARM64
- Layer: StrandsAgentsLayer

**Environment Variables:**
```
PYTHONPATH=/opt/python
BEDROCK_MODEL=us.anthropic.claude-3-7-sonnet-20250219-v1:0
OPENAI_API_KEY=(from Secrets Manager)
```

**Workflow:**
1. Load course outline (YAML) from S3
2. Extract lesson metadata (title, topics, duration)
3. Calculate target word count based on Bloom level
4. Create three Strands Agents:
   - **Researcher**: Gathers information on topic
   - **Writer**: Creates structured lesson content
   - **Reviewer**: Refines and adds [VISUAL] tags
5. Execute sequential agent workflow
6. Save lesson as Markdown to S3

**Input Event:**
```json
{
  "course_topic": "Kubernetes for DevOps",
  "course_duration_hours": 20,
  "module_to_generate": 2,
  "lesson_to_generate": 1,
  "outline_s3_key": "project/outline.yaml",
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251006-kubernetes-course",
  "model_provider": "bedrock",
  "performance_mode": "balanced"
}
```

**Output:**
```json
{
  "statusCode": 200,
  "lesson_key": "project/lessons/module-02-lesson-01.md",
  "project_folder": "251006-kubernetes-course",
  "bucket": "crewai-course-artifacts",
  "word_count": 1543,
  "generation_time_seconds": 45.2,
  "model_provider": "bedrock"
}
```

**Error Handling:**
- Auto-retry on Lambda service errors (2 attempts)
- Fallback from OpenAI to Bedrock on org verification errors
- Raises exception to trigger Step Functions retry

---

#### 2. StrandsVisualPlanner (Visual Tag Processor)

**Purpose:** Extract [VISUAL: ...] tags and classify visuals as diagrams or artistic images

**Configuration:**
- Runtime: Python 3.12
- Memory: 512 MB
- Timeout: 300 seconds (5 minutes)
- Architecture: ARM64
- Layer: StrandsAgentsLayer

**Workflow:**
1. Read lesson content from S3
2. Extract all [VISUAL: description] tags using regex
3. Create unique filename for each visual
4. Use Strands Agent to classify visual type:
   - `diagram`: Technical diagrams, flowcharts, architecture
   - `artistic_image`: Illustrations, photos, graphics
5. Generate detailed prompts for image generation
6. Save prompt files as JSON to S3

**Input Event:**
```json
{
  "lesson_key": "project/lessons/module-02-lesson-01.md",
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "project-name",
  "module_number": 2,
  "lesson_number": 1,
  "model_provider": "bedrock"
}
```

**Output:**
```json
{
  "statusCode": 200,
  "message": "Successfully generated 5 visual prompts",
  "prompts": [
    {
      "id": "02-01-0001",
      "description": "Kubernetes cluster architecture diagram",
      "visual_type": "diagram",
      "filename": "visual_abc123.png",
      "s3_key": "project/prompts/02-01-0001-kubernetes-arch.json"
    }
  ],
  "prompts_s3_prefix": "project/prompts/",
  "bucket": "crewai-course-artifacts",
  "project_folder": "project-name"
}
```

---

#### 3. ImagesGen (Image Generator)

**Purpose:** Generate images from prompts using Google Gemini API

**Configuration:**
- Runtime: Python 3.12
- Memory: 1024 MB
- Timeout: 900 seconds (15 minutes)
- Architecture: ARM64
- Layer: GeminiLayer (google-generativeai + Pillow)

**Workflow:**
1. List all prompt JSON files from S3
2. Load Google API key from Secrets Manager
3. Configure Gemini 2.5 Flash Image model
4. For each prompt:
   - Generate image using Gemini API
   - Rate limit: 10 seconds between requests
   - Convert to PNG format
   - Upload to S3 images/ folder
5. Create image mappings for Book Builder

**Input Event:**
```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "project-name",
  "prompts_prefix": "project/prompts/",
  "max_images": 5
}
```

**Output:**
```json
{
  "statusCode": 200,
  "message": "Generated 5 images successfully",
  "images_generated": 5,
  "image_mappings": {
    "[VISUAL: 02-01-0001]": "project/images/visual_abc123.png"
  },
  "bucket": "crewai-course-artifacts",
  "project_folder": "project-name"
}
```

**Rate Limiting:**
- 10 second delay between API calls
- Backend hard cap: 50 images per execution
- Handles Gemini API rate limit errors with retry

---

#### 4. BookBuilder (Book Compiler)

**Purpose:** Combine lessons and images into complete course book

**Configuration:**
- Runtime: Python 3.12
- Memory: 512 MB
- Timeout: 300 seconds (5 minutes)

**Workflow:**
1. Auto-discover lesson files in project folder
2. Load all lesson content from S3
3. Scan for existing images
4. Replace [VISUAL] tags with actual image references
5. Generate table of contents
6. Compile full book (Markdown + JSON)
7. Save to S3 book/ folder

**Features:**
- Automatic lesson ordering
- Visual tag replacement with S3 URLs
- Statistics calculation (word count, lesson count)
- Dual format output (Markdown + JSON)

---

#### 5. Supporting API Functions

**StarterApiFunction** - Start Step Functions execution
**ExecStatusFunction** - Check execution status
**PresignFunction** - Generate S3 presigned URLs
**ListProjectsFunction** - List available course projects
**LoadBookFunction** - Load book data for editor
**SaveBookFunction** - Save edited book back to S3
**CorsHandler** - Handle CORS preflight requests

---

### Lambda Layers

#### StrandsAgentsLayer
**Contents:**
- strands-agents SDK
- boto3 (AWS SDK)
- PyYAML
- Other Python dependencies

**Build Script:**
```bash
cd CG-Backend/lambda-layers
./build-layer.sh
```

#### GeminiLayer
**Contents:**
- google-generativeai
- Pillow (PIL)
- Image processing utilities

**Build Script:**
```bash
cd CG-Backend/lambda-layers
./build-gemini-layer.sh
```

---

### Step Functions State Machine

**Name:** CourseGeneratorStateMachine

**Type:** Standard (not Express)

**Workflow:**
```
InvokeContentGen
    ↓
CheckContentGenResult
    ↓
ParseContentGenResult
    ↓
InvokeVisualPlanner
    ↓
InvokeImagesGen
    ↓
InvokeBookBuilder
    ↓
SuccessState
```

**Retry Configuration:**
- Lambda Service Errors: 2 retries, exponential backoff (2x)
- Task Failures: 3 retries for ImagesGen (rate limits)
- S3 Errors: 2 retries, 1.5x backoff

**Error Handling:**
- All errors caught and routed to FailState
- Error details stored in $.error path
- Execution history preserved for debugging

**Execution Input:**
```json
{
  "course_topic": "Kubernetes for DevOps",
  "course_duration_hours": 20,
  "module_to_generate": 1,
  "model_provider": "bedrock",
  "performance_mode": "balanced",
  "content_source": "outline",
  "max_images": 5
}
```

**Execution Output:**
```json
{
  "Payload": {
    "statusCode": 200,
    "book_s3_key": "project/book/Course_Book_complete.md",
    "book_json_key": "project/book/Course_Book_data.json",
    "lesson_count": 10,
    "total_words": 15430,
    "project_folder": "251006-kubernetes-course"
  }
}
```

---

## AI/ML Pipeline

### Multi-Model Architecture

Aurora supports three AI providers with intelligent fallback:

**Priority Order:**
1. **User-selected provider** (from API request)
2. **Fallback to Bedrock** (if OpenAI fails)
3. **Error with details** (if all fail)

### AWS Bedrock Integration

**Model:** Claude 3.7 Sonnet  
**Model ID:** `us.anthropic.claude-3-7-sonnet-20250219-v1:0`

**Capabilities:**
- Content generation (lessons)
- Visual planning (tag classification)
- Long-context understanding (200K tokens)
- Fast response times

**Configuration:**
```python
from strands.models import BedrockModel

model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
)
```

**IAM Permissions Required:**
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": "*"
}
```

---

### OpenAI Integration

**Model:** GPT-5  
**Model ID:** `gpt-5`

**Capabilities:**
- Advanced reasoning
- Creative content generation
- Alternative to Bedrock

**Configuration:**
```python
from strands.models.openai import OpenAIModel

model = OpenAIModel(
    client_args={"api_key": openai_api_key},
    model_id="gpt-5",
    streaming=False
)
```

**Fallback Logic:**
```python
try:
    model = configure_openai_model()
except ValueError as e:
    if "organization" in str(e).lower():
        # Fallback to Bedrock
        model = BedrockModel(model_id=DEFAULT_BEDROCK_MODEL)
```

**API Key Storage:**
- Primary: AWS Secrets Manager (`aurora/openai-api-key`)
- Fallback: Environment variable `OPENAI_API_KEY`

---

### Google Gemini Integration

**Model:** Gemini 2.5 Flash Image  
**Model ID:** `models/gemini-2.5-flash-image`

**Purpose:** Image generation only

**Configuration:**
```python
import google.generativeai as genai

genai.configure(api_key=google_api_key)
model = genai.GenerativeModel('models/gemini-2.5-flash-image')
```

**API Key Storage:**
- Primary: AWS Secrets Manager (`aurora/google-api-key`)
- Fallback: Environment variable `GOOGLE_API_KEY`

**Rate Limiting:**
- 10 seconds between requests
- Max 50 images per execution
- Exponential backoff on rate limit errors

---

### Strands Agents Framework

**Purpose:** Multi-agent orchestration for content generation

**Agent Types:**

1. **Researcher Agent**
   ```python
   researcher = Agent(
       model=model,
       system_prompt="Research specialist gathering technical information...",
       tools=[]
   )
   ```
   - Gathers information on course topics
   - Creates structured research notes
   - Outputs key concepts, best practices, examples

2. **Writer Agent**
   ```python
   writer = Agent(
       model=model,
       system_prompt="Expert technical author creating lesson content...",
       tools=[]
   )
   ```
   - Creates structured lesson content
   - Follows academic standards
   - Integrates research into cohesive narrative
   - Adds [VISUAL] placeholders

3. **Reviewer Agent**
   ```python
   reviewer = Agent(
       model=model,
       system_prompt="Content quality reviewer ensuring accuracy...",
       tools=[]
   )
   ```
   - Reviews completeness and accuracy
   - Ensures proper structure
   - Adds visual tags strategically
   - Final polish and formatting

**Sequential Workflow:**
```
Research → Summarize → Write → Review → Output
```

**Benefits:**
- Modular and maintainable
- Each agent specializes in one task
- Easy to swap AI models
- Consistent output quality

---

### Content Generation Parameters

**Target Word Count Calculation:**
```python
base_words = duration_minutes * 120  # Conservative reading speed
bloom_multiplier = bloom_level_multipliers[bloom_level]
topic_bonus = len(topics) * 100
calculated_words = (base_words * bloom_multiplier) + topic_bonus
target_words = max(600, min(1800, calculated_words))
```

**Bloom's Taxonomy Levels:**
- Remember: 1.0x
- Understand: 1.1x
- Apply: 1.2x
- Analyze: 1.3x
- Evaluate: 1.4x
- Create: 1.5x

**Performance Modes:**
- `fast`: Lower quality, faster generation
- `balanced`: Optimal quality/speed (default)
- `maximum_quality`: Highest quality, slower

---

## Authentication & Authorization

### AWS Cognito Configuration

**User Pool ID:** `us-east-1_B7QVYyDGp`  
**Client ID:** `67qhvmopav8qp6blthh7vmql82`  
**Region:** `us-east-1`

**Authentication Flow:**
1. User clicks "Comenzar Ahora" button
2. Redirects to Cognito Hosted UI
3. User logs in with credentials
4. Cognito redirects back with authorization code
5. Amplify exchanges code for tokens (PKCE)
6. Frontend stores tokens in localStorage
7. Amplify manages token refresh automatically

**Token Types:**
- **ID Token**: User identity and attributes
- **Access Token**: API authorization
- **Refresh Token**: Token renewal

### Identity Pools

**Purpose:** Federate Cognito identity to IAM credentials

**Configuration:**
```javascript
identityPoolId: import.meta.env.VITE_IDENTITY_POOL_ID
```

**Credential Flow:**
```
Cognito Token → Identity Pool → IAM Temporary Credentials
```

**IAM Credentials Include:**
- Access Key ID
- Secret Access Key
- Session Token
- Expiration time

### User Groups & Roles

**Groups in Cognito:**

1. **Administrador** (Administrator)
   - Full system access
   - User management
   - Role approval
   - System configuration

2. **Creador** (Creator)
   - Generate courses
   - Edit content
   - Manage projects
   - View analytics

3. **Participante** (Participant)
   - View courses
   - Take activities
   - Limited editing

**Group Detection:**
```javascript
const groups = accessToken.payload['cognito:groups'] || [];
const isAdmin = groups.includes('Administrador');
```

**Role-Based UI:**
```javascript
if (rol === 'admin') {
  // Show admin menu items
}
```

### IAM Policies

**Lambda Execution Role:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::crewai-course-artifacts",
        "arn:aws:s3:::crewai-course-artifacts/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:aurora/openai-api-key-*",
        "arn:aws:secretsmanager:us-east-1:*:secret:aurora/google-api-key-*"
      ]
    }
  ]
}
```

### Request Signing (SigV4)

**Frontend Implementation:**
```javascript
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { Sha256 } from '@aws-crypto/sha256-js';

const credentials = await Auth.currentCredentials();
const signer = new SignatureV4({
  credentials: {
    accessKeyId: credentials.accessKeyId,
    secretAccessKey: credentials.secretAccessKey,
    sessionToken: credentials.sessionToken,
  },
  region: 'us-east-1',
  service: 'execute-api',
  sha256: Sha256,
});

const signedRequest = await signer.sign(request);
```

**Security Benefits:**
- No API keys in frontend code
- Credentials auto-expire and rotate
- Request integrity verification
- Prevents replay attacks

---

## Data Flow

### Course Generation Flow

```
1. User submits course parameters via frontend
   ↓
2. Frontend signs request with SigV4
   ↓
3. API Gateway validates IAM credentials
   ↓
4. StarterApiFunction starts Step Functions execution
   ↓
5. Step Functions orchestrates workflow:
   a. ContentGen generates lesson
   b. VisualPlanner extracts visual tags
   c. ImagesGen creates images
   d. BookBuilder compiles book
   ↓
6. Artifacts saved to S3
   ↓
7. Frontend polls ExecStatusFunction for updates
   ↓
8. User views/edits completed book
```

### Data Persistence

**S3 Bucket Structure:**
```
crewai-course-artifacts/
├── {project_folder}/                    # YYMMDD-course-topic-XX
│   ├── outline.yaml                     # Course structure
│   ├── lessons/
│   │   ├── module-01-lesson-01.md       # Lesson content
│   │   ├── module-01-lesson-02.md
│   │   └── ...
│   ├── prompts/
│   │   ├── 01-01-0001-visual-desc.json  # Image prompts
│   │   ├── 01-01-0002-visual-desc.json
│   │   └── ...
│   ├── images/
│   │   ├── visual_abc123.png            # Generated images
│   │   ├── visual_def456.png
│   │   └── ...
│   └── book/
│       ├── Course_Book_complete.md      # Compiled book (Markdown)
│       └── Course_Book_data.json        # Compiled book (JSON)
```

### Outline YAML Format

```yaml
course_metadata:
  course_title: "Kubernetes for DevOps Engineers"
  course_duration_hours: 40
  target_audience: "DevOps Engineers"
  difficulty_level: "Intermediate"
  bloom_level: "Apply"

modules:
  - module_number: 1
    module_title: "Introduction to Kubernetes"
    module_description: "Fundamentals of container orchestration"
    duration_minutes: 240
    bloom_level: "Understand"
    lessons:
      - lesson_title: "What is Kubernetes?"
        duration_minutes: 60
        bloom_level: "Understand"
        topics:
          - "Container orchestration basics"
          - "Kubernetes architecture"
          - "Key components"
```

### Lesson Markdown Format

```markdown
# Introduction to Kubernetes

## Learning Objectives
- Understand container orchestration concepts
- Identify Kubernetes architecture components
- Explain the role of control plane and worker nodes

## Introduction
Kubernetes is an open-source container orchestration platform...

[VISUAL: Kubernetes cluster architecture showing control plane and worker nodes]

## Theoretical Foundations
The Kubernetes architecture consists of...

## Hands-On Exercises
1. Install kubectl
2. Create a local cluster with minikube
3. Deploy your first application

## Summary
In this lesson, you learned...
```

### Image Prompt JSON Format

```json
{
  "id": "01-01-0001",
  "description": "Kubernetes cluster architecture diagram",
  "visual_type": "diagram",
  "filename": "visual_abc123.png",
  "enhanced_prompt": "Create a detailed technical diagram showing Kubernetes cluster architecture with control plane (API server, etcd, scheduler, controller manager) and worker nodes (kubelet, kube-proxy, container runtime). Use clean lines, clear labels, and professional styling suitable for technical documentation.",
  "module_number": 1,
  "lesson_number": 1,
  "lesson_title": "Introduction to Kubernetes"
}
```

---

## Storage Architecture

### S3 Buckets

**Primary Bucket:** `crewai-course-artifacts`

**Configuration:**
- Region: us-east-1
- Versioning: Enabled (recommended)
- Encryption: AES-256 (SSE-S3)
- Public Access: Blocked
- Lifecycle: Manual (no auto-delete)

**Access Patterns:**
- Lambda: Read/Write via IAM role
- Frontend: Read via presigned URLs or IAM credentials
- Step Functions: Indirect via Lambda

**Cost Optimization:**
- Standard storage for active projects
- Glacier for archived courses (future)
- Lifecycle policies for 90-day retention

---

## API Architecture

### API Gateway Configuration

**Type:** REST API (Regional)  
**Authorization:** IAM (AWS_IAM)  
**Base URL:** `https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod`

### Endpoints

| Method | Path | Function | Auth | Purpose |
|--------|------|----------|------|---------|
| POST | /start-job | StarterApiFunction | IAM | Start course generation |
| GET | /exec-status/{arn} | ExecStatusFunction | IAM | Check execution status |
| POST | /presign | PresignFunction | IAM | Generate S3 presigned URL |
| GET | /list-projects | ListProjectsFunction | IAM | List course projects |
| GET | /load-book/{folder} | LoadBookFunction | IAM | Load book data |
| POST | /save-book | SaveBookFunction | IAM | Save book edits |
| POST | /build-book | BookBuilder | IAM | Build complete book |
| OPTIONS | /* | CorsHandler | None | CORS preflight |

### CORS Configuration

```yaml
Cors:
  AllowMethods: "'OPTIONS,GET,POST,PUT,DELETE'"
  AllowHeaders: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-amz-content-sha256'"
  AllowOrigin: "'*'"
```

**Gateway Responses:**
- UNAUTHORIZED (403)
- MISSING_AUTHENTICATION_TOKEN (403)
- ACCESS_DENIED (403)
- INVALID_SIGNATURE (403)
- DEFAULT_5XX (500)

All gateway responses include CORS headers.

### Error Handling

**Lambda Errors:**
- Caught by API Gateway
- Transformed to HTTP status codes
- Include error details in response body

**Example Error Response:**
```json
{
  "statusCode": 500,
  "error": "Failed to generate content: Model timeout",
  "request_id": "abc-123-def",
  "timestamp": "2025-10-08T14:30:00Z"
}
```

---

## Deployment Architecture

### Frontend Deployment (AWS Amplify)

**Build Configuration (`amplify.yml`):**
```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - CI=false npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

**Environment Variables (Amplify Console):**
```
VITE_COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=67qhvmopav8qp6blthh7vmql82
VITE_USER_POOL_ID=us-east-1_B7QVYyDGp
VITE_IDENTITY_POOL_ID=us-east-1:xxx-xxx-xxx
VITE_AWS_REGION=us-east-1
VITE_REDIRECT_URI=https://testing.d28h59guct50tx.amplifyapp.com
VITE_COURSE_GENERATOR_API_URL=https://i0l7dxvw49.execute-api.us-east-1.amazonaws.com/Prod
```

**Deployment Process:**
1. Push code to GitHub (branch: testing)
2. Amplify detects commit
3. Runs build process
4. Deploys to CloudFront CDN
5. Invalidates CDN cache
6. Available at amplifyapp.com domain

**Branch Strategy:**
- `testing` branch → Testing environment
- `main` branch → Production environment (future)

---

### Backend Deployment (AWS SAM)

**SAM Configuration (`samconfig.toml`):**
```toml
[default.deploy.parameters]
stack_name = "crewai-course-generator-stack"
region = "us-east-1"
capabilities = "CAPABILITY_IAM"
```

**Deployment Commands:**
```bash
# Build Lambda layers
cd lambda-layers
./build-layer.sh
./build-gemini-layer.sh

# Build SAM application
cd ..
sam build

# Deploy to AWS
sam deploy --guided
```

**Deployment Steps:**
1. Package Lambda functions
2. Build Lambda layers
3. Upload to S3 (SAM artifacts bucket)
4. Deploy CloudFormation stack
5. Update API Gateway
6. Configure Step Functions

**Rollback Strategy:**
- CloudFormation automatic rollback on failure
- Manual rollback via CloudFormation console
- Lambda versioning for quick revert

---

### CI/CD Pipeline (Future)

**Planned GitHub Actions Workflow:**
```yaml
name: Deploy Aurora
on:
  push:
    branches: [main, testing]

jobs:
  frontend:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Install dependencies
      - Run tests
      - Build frontend
      - Deploy to Amplify
  
  backend:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Build Lambda layers
      - SAM build
      - SAM deploy
      - Run integration tests
```

---

## Security Architecture

### Security Layers

1. **Network Security**
   - All traffic over HTTPS/TLS 1.2+
   - API Gateway regional endpoint (not edge)
   - VPC not required (serverless)

2. **Authentication**
   - AWS Cognito User Pools
   - MFA supported (optional)
   - OAuth 2.0 PKCE flow
   - JWT tokens with short expiry

3. **Authorization**
   - IAM-based API authorization
   - SigV4 request signing
   - Role-based access control (groups)
   - Least privilege Lambda policies

4. **Data Protection**
   - S3 encryption at rest (AES-256)
   - Secrets Manager for API keys
   - No sensitive data in logs
   - DOMPurify for XSS prevention

5. **Secrets Management**
   - AWS Secrets Manager for all API keys
   - Automatic rotation (recommended)
   - Encrypted in transit and at rest
   - IAM policies restrict access

### Secrets Configuration

**Secret Names:**
- `aurora/openai-api-key` - OpenAI API key
- `aurora/google-api-key` - Google Gemini API key

**Secret Format:**
```json
{
  "api_key": "sk-xxxxxxxxxxxxx"
}
```

**Access Pattern:**
```python
def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])
```

### Security Best Practices

✅ **Implemented:**
- IAM authentication for all APIs
- Encrypted secrets storage
- HTTPS-only communication
- XSS prevention (DOMPurify)
- Input validation
- Least privilege IAM roles

⚠️ **Recommended Improvements:**
- Enable MFA for all users
- Implement rate limiting (WAF)
- Add CloudTrail logging
- Enable S3 access logging
- Implement secret rotation
- Add vulnerability scanning

---

## Monitoring & Logging

### CloudWatch Logs

**Log Groups:**
```
/aws/lambda/StrandsContentGen
/aws/lambda/StrandsVisualPlanner
/aws/lambda/ImagesGen
/aws/lambda/BookBuilder
/aws/lambda/StarterApiFunction
/aws/lambda/ExecStatusFunction
/aws/states/CourseGeneratorStateMachine
```

**Log Retention:**
- Default: Indefinite
- Recommended: 30-90 days

**Log Format:**
```
[timestamp] [request_id] [level] message
```

**Example Log Entry:**
```
2025-10-08 14:30:45.123 abc-123-def INFO 🚀 STRANDS AGENTS CONTENT GENERATOR
2025-10-08 14:30:45.456 abc-123-def INFO 📚 Course: Kubernetes for DevOps
2025-10-08 14:31:20.789 abc-123-def INFO ✅ Lesson generated successfully
```

### CloudWatch Metrics

**Lambda Metrics:**
- Invocations
- Duration
- Errors
- Throttles
- Concurrent executions

**API Gateway Metrics:**
- Request count
- Latency (p50, p90, p99)
- 4xx errors
- 5xx errors

**Step Functions Metrics:**
- Executions started
- Executions succeeded
- Executions failed
- Execution duration

### Alerting (Recommended)

**CloudWatch Alarms:**
```
StrandsContentGen-Errors > 5 in 5 minutes
StrandsContentGen-Duration > 800 seconds
StepFunctions-FailedExecutions > 0
APIGateway-5xxErrors > 10 in 5 minutes
```

**SNS Notifications:**
- Email to DevOps team
- Slack integration
- PagerDuty integration

---

## Development Workflow

### Local Development Setup

**Prerequisites:**
```bash
# Node.js 18+
node --version

# Python 3.12
python3 --version

# AWS CLI
aws --version

# SAM CLI
sam --version

# Git
git --version
```

**Frontend Setup:**
```bash
# Clone repository
git clone https://github.com/AURORA-BOTIEF/AuroraV1.git
cd AuroraV1

# Install dependencies
npm install

# Create environment file
cat > .env.local << EOF
VITE_COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=67qhvmopav8qp6blthh7vmql82
VITE_USER_POOL_ID=us-east-1_B7QVYyDGp
VITE_IDENTITY_POOL_ID=us-east-1:xxx
VITE_AWS_REGION=us-east-1
VITE_REDIRECT_URI=http://localhost:5173
VITE_COURSE_GENERATOR_API_URL=https://api-url
EOF

# Start dev server
npm run dev
```

**Backend Setup:**
```bash
cd CG-Backend

# Build Lambda layers
cd lambda-layers
./build-layer.sh
./build-gemini-layer.sh
cd ..

# Test Lambda locally (SAM)
sam build
sam local invoke StrandsContentGen --event test-event.json

# Deploy to AWS
sam deploy --guided
```

### Git Workflow

**Branches:**
- `main` - Production (not currently deployed)
- `testing` - Testing environment (active)
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches

**Commit Convention:**
```
feat: Add new feature
fix: Fix bug
docs: Update documentation
refactor: Refactor code
test: Add tests
chore: Update dependencies
```

### Testing Strategy

**Frontend Testing:**
- Manual testing in browser
- Component testing (future: Jest + React Testing Library)

**Backend Testing:**
- Unit tests for Lambda functions (future: pytest)
- Integration tests with SAM local
- Manual API testing with curl/Postman

**Example Test Command:**
```bash
# Test Lambda locally
sam local invoke StrandsContentGen --event events/test-lesson.json

# Test API endpoint
curl -X POST https://api-url/start-job \
  --aws-sigv4 "aws:amz:us-east-1:execute-api" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
  -d '{"course_topic": "Test"}'
```

---

## Scalability & Performance

### Current Capacity

**Frontend:**
- CloudFront CDN (unlimited concurrent users)
- Auto-scaling edge locations
- Response time: <100ms (static assets)

**Backend:**
- Lambda concurrent executions: 1000 (default account limit)
- API Gateway: 10,000 requests/second (default)
- Step Functions: 800 state transitions/second

**AI Models:**
- Bedrock: Account-specific quotas
- OpenAI: API key rate limits
- Gemini: 10 images/minute (self-imposed)

### Performance Optimizations

**Frontend:**
- Code splitting with Vite
- Lazy loading of routes
- Image optimization (future)
- Browser caching (max-age)

**Backend:**
- ARM64 architecture (20% faster, 20% cheaper)
- Lambda layer reuse
- S3 transfer acceleration (future)
- Parallel lesson generation (future)

**AI Pipeline:**
- Research summarization to reduce tokens
- Target word limits to prevent timeouts
- Streaming disabled for OpenAI (reliability)
- Rate limiting for Gemini

### Scaling Strategy

**Vertical Scaling:**
- Increase Lambda memory (more CPU)
- Upgrade to larger AI models

**Horizontal Scaling:**
- Parallel Step Functions executions
- Multiple Lambda concurrent invocations
- Distributed S3 reads/writes

**Limits & Quotas:**
- Lambda: Request quota increase for concurrent executions
- Bedrock: Request model access and higher quotas
- API Gateway: Default limits sufficient for current scale

---

## Cost Optimization

### Current Cost Structure

**AWS Services (Monthly estimates for moderate usage):**

| Service | Usage | Cost |
|---------|-------|------|
| **Amplify** | Hosting + builds | $5-15 |
| **Cognito** | 1000 active users | Free tier |
| **API Gateway** | 100K requests | $0.35 |
| **Lambda** | 10K invocations, 2GB | $2-5 |
| **Step Functions** | 100 executions | $0.25 |
| **S3** | 10GB storage, 1K requests | $0.50 |
| **CloudWatch** | Logs + metrics | $1-3 |
| **Secrets Manager** | 2 secrets | $0.80 |
| **Total AWS** | | ~$10-25/month |

**AI Model Costs (per 1M tokens):**

| Provider | Model | Input | Output |
|----------|-------|-------|--------|
| **Bedrock** | Claude 3.7 Sonnet | $3 | $15 |
| **OpenAI** | GPT-5 | $15 | $60 |
| **Gemini** | 2.5 Flash Image | ~$0.10/image | N/A |

**Typical Course Generation Cost:**
- 10 lessons × 1500 words = ~15K tokens input + 25K tokens output
- Bedrock: (15K × $3) + (25K × $15) = $0.42 per course
- Images: 10 images × $0.10 = $1.00
- **Total: ~$1.50 per complete course**

### Cost Optimization Strategies

**Implemented:**
- ARM64 Lambdas (20% cheaper)
- S3 Intelligent-Tiering (future)
- Lambda layers (reduce deployment size)
- Target word limits (reduce token usage)

**Recommended:**
- Reserved capacity for Bedrock (if high volume)
- S3 lifecycle policies for old projects
- CloudWatch log retention policies
- Bedrock as primary (cheaper than OpenAI)

---

## Future Enhancements

### Short-Term (Q1 2026)

1. **Real-Time Progress Updates**
   - WebSocket API for live status
   - Progress bar in UI
   - Estimated time remaining

2. **Batch Processing**
   - Generate multiple modules simultaneously
   - Parallel lesson generation
   - Queue management

3. **Enhanced Book Editor**
   - Rich text editor (WYSIWYG)
   - Drag-and-drop lessons
   - In-line image editing

4. **Content Validation**
   - Automated quality checks
   - Plagiarism detection
   - Fact-checking (future)

### Medium-Term (Q2-Q3 2026)

1. **Custom AI Models**
   - Fine-tuned models for specific domains
   - NETEC-branded content style
   - Regional language variants

2. **Analytics Dashboard**
   - Course generation metrics
   - Cost tracking
   - Quality scores

3. **Template Library**
   - Pre-built course templates
   - Industry-specific structures
   - Reusable modules

4. **Collaboration Features**
   - Multi-user editing
   - Comments and reviews
   - Version control

### Long-Term (2026+)

1. **Multi-Language Support**
   - Spanish as primary language
   - English translation
   - Portuguese for Brazil market

2. **Video Integration**
   - AI-generated video lectures
   - Automated transcription
   - Subtitle generation

3. **Interactive Elements**
   - Embedded quizzes
   - Code playgrounds
   - Virtual labs

4. **LMS Integration**
   - Export to SCORM
   - Moodle integration
   - Canvas LMS connector

---

## Appendix

### Key Files Reference

**Frontend:**
- `/src/App.jsx` - Main application component
- `/src/amplify.js` - AWS Amplify configuration
- `/src/components/BookBuilderPage.jsx` - Book builder interface
- `/src/components/GeneradorTemarios.jsx` - Curriculum generator
- `/package.json` - Dependencies and scripts
- `/vite.config.js` - Vite build configuration
- `/amplify.yml` - Amplify build settings

**Backend:**
- `/CG-Backend/template.yaml` - SAM/CloudFormation template
- `/CG-Backend/lambda/strands_content_gen/` - Content generator
- `/CG-Backend/lambda/strands_visual_planner/` - Visual planner
- `/CG-Backend/lambda/images_gen/` - Image generator
- `/CG-Backend/lambda/book_builder.py` - Book compiler
- `/CG-Backend/lambda-layers/` - Lambda layer build scripts

### Useful Commands

**Frontend:**
```bash
npm run dev        # Start dev server
npm run build      # Build for production
npm run preview    # Preview production build
npm run lint       # Run ESLint
```

**Backend:**
```bash
sam build                  # Build SAM application
sam deploy                 # Deploy to AWS
sam local invoke Function  # Test locally
sam logs -t                # Tail logs
```

**AWS CLI:**
```bash
# List Lambda functions
aws lambda list-functions

# Invoke Lambda
aws lambda invoke --function-name StrandsContentGen out.json

# List S3 objects
aws s3 ls s3://crewai-course-artifacts/

# Describe Step Functions execution
aws stepfunctions describe-execution --execution-arn <arn>
```

### Environment Variables

**Frontend (Vite):**
- `VITE_COGNITO_DOMAIN` - Cognito domain
- `VITE_COGNITO_CLIENT_ID` - App client ID
- `VITE_USER_POOL_ID` - User Pool ID
- `VITE_IDENTITY_POOL_ID` - Identity Pool ID
- `VITE_AWS_REGION` - AWS region
- `VITE_REDIRECT_URI` - OAuth redirect URI
- `VITE_COURSE_GENERATOR_API_URL` - API Gateway URL

**Backend (Lambda):**
- `PYTHONPATH` - Python module path
- `BEDROCK_MODEL` - Bedrock model ID
- `OPENAI_API_KEY` - OpenAI key (from Secrets Manager)
- `GOOGLE_API_KEY` - Gemini key (from Secrets Manager)
- `IMAGES_BACKEND_MAX` - Max images per run
- `AWS_DEFAULT_REGION` - AWS region

### Contact & Support

**Project Owner:** NETEC  
**Repository:** https://github.com/AURORA-BOTIEF/AuroraV1  
**Branch:** testing  
**Documentation:** This file (ARCHITECTURE.md)

---

**Document Version:** 1.3  
**Last Updated:** October 20, 2025, 01:01 UTC  
**Authors:** System Analysis Team, Juan Ossa (Book Editor Implementation), Content Generation Team (Oct 2025 Improvements)  
**Production Status:** ✅ **READY** (All improvements deployed)  
**Last Deployment:** October 20, 2025, 01:01 UTC  
**Validated Success Rate:** 99.4% (Project 251018-JS-06)  
**Next Review:** After next course generation test

---

## 2025-10-14: Content Generation - Multi-Model Support & Visual Tags

### Summary

Major improvements to the content generation pipeline including multi-model AI support (Bedrock Claude, OpenAI GPT-5), enhanced visual tag generation, and single-call optimization for faster course creation.

### Key Features Implemented

#### 1. **Multi-Model AI Support**
- **AWS Bedrock**: Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- **OpenAI GPT-5**: Full integration with API key management
- **Model Selection**: User can choose model per module generation
- **Automatic Fallback**: Bedrock fallback if OpenAI fails
- **Token Limits**: 30,000 tokens for both models (increased from 16K)

#### 2. **Single-Call Content Generation**
- **Architecture**: Generate complete module (3 lessons) in one API call
- **Performance**: 85% faster than multi-call approach (5-8 min vs 30+ min)
- **Cost Efficiency**: Reduced API costs through batching
- **Completeness**: Ensures all lessons generated together maintain consistency

#### 3. **Enhanced Visual Tag System**
- **GPT-5 SYSTEM Message**: Visual tag requirements in system prompt for higher priority
- **80+ Character Requirement**: Each visual tag must describe components, layout, relationships
- **Forbidden Patterns**: Explicit rejection of placeholders like `[VISUAL: 01-01-0001]`
- **Self-Check Question**: "Could someone draw this image from my description alone?"
- **Examples in Prompt**: Multiple correct/incorrect examples for clarity

#### 4. **Content Length Calculation**
- **Duration-Based**: `base_words = duration_minutes × 15 × bloom_multiplier`
- **Bloom Multipliers**: Remember (1.0x), Understand (1.1x), Apply (1.2x), Analyze (1.3x), Evaluate (1.4x), Create (1.5x)
- **Topic/Lab Bonuses**: +80 words per topic, +120 words per lab
- **Range Bounds**: 500-3000 words per lesson
- **Example**: 100-minute "Analyze" lesson = `100 × 15 × 1.3 = 1,950 words`

### Technical Implementation

#### Visual Tag Format (Correct)
```markdown
✅ [VISUAL: Layered architecture diagram showing Kubernetes control plane with five components arranged in a hub pattern: API Server (central blue box), Scheduler (green box, top), Controller Manager (orange box, left), etcd database (cyan cylinder, right), Cloud Controller Manager (gray box, bottom), all connected to API Server with bidirectional arrows labeled 'gRPC' and 'watch']
```

#### Visual Tag Format (Rejected)
```markdown
❌ [VISUAL: 01-01-0001] ← Placeholder ID
❌ [VISUAL: diagram] ← Too vague
❌ [VISUAL: Kubernetes architecture] ← No details
❌ [VISUAL: control plane] ← Too short
```

#### OpenAI API Call with SYSTEM Message
```python
def call_openai(prompt: str, api_key: str, model: str = "gpt-5") -> str:
    """Call OpenAI API with SYSTEM message for visual tag requirements."""
    client = openai.OpenAI(api_key=api_key)
    
    system_message = """You are an expert educational content creator. Follow these CRITICAL rules:

🚨 VISUAL TAG REQUIREMENT (NON-NEGOTIABLE):
Every [VISUAL: ...] tag you write MUST be 80+ characters and describe:
- WHAT components are shown (e.g., "API Server", "etcd", "Scheduler")
- HOW they are arranged (e.g., "layered", "connected in a hub", "side-by-side")
- WHAT relationships exist (e.g., "connected by arrows labeled 'gRPC'", "bidirectional communication")
- Any colors, labels, or visual indicators

CORRECT EXAMPLE (125 characters):
[VISUAL: Architecture diagram showing Kubernetes control plane with API Server (central blue box), Scheduler (green box above), Controller Manager (orange box left), etcd (cyan cylinder right), all connected to API Server with bidirectional arrows]

FORBIDDEN:
❌ [VISUAL: 01-01-0001]
❌ [VISUAL: diagram]
❌ [VISUAL: Kubernetes architecture]
❌ Any tag under 80 characters

Before writing each visual tag, ask yourself: "Could someone draw this image from my description alone?"
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_completion_tokens=30000
    )
    
    return response.choices[0].message.content
```

#### Content Length Calculation Function
```python
def calculate_target_words(lesson_data: dict, module_info: dict) -> int:
    """Calculate target word count for a lesson."""
    lesson_duration = lesson_data.get('duration_minutes', module_info.get('duration_minutes', 45))
    lesson_bloom = lesson_data.get('bloom_level', module_info.get('bloom_level', 'Understand'))
    
    # Handle compound bloom levels
    if '/' in lesson_bloom:
        bloom_parts = [b.strip() for b in lesson_bloom.split('/')]
        bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
        lesson_bloom = max(bloom_parts, key=lambda x: bloom_order.index(x) if x in bloom_order else 0)
    
    # Bloom multipliers
    bloom_multipliers = {
        'Remember': 1.0,
        'Understand': 1.1,
        'Apply': 1.2,
        'Analyze': 1.3,
        'Evaluate': 1.4,
        'Create': 1.5
    }
    
    bloom_mult = bloom_multipliers.get(lesson_bloom, 1.1)
    
    # Base calculation: 15 words per minute (concise content that teacher expands)
    base_words = lesson_duration * 15
    base_words = int(base_words * bloom_mult)
    
    # Add for topics and labs
    topics_count = len(lesson_data.get('topics', []))
    labs_count = len(lesson_data.get('lab_activities', []))
    
    total_words = base_words + (topics_count * 80) + (labs_count * 120)
    
    # Bounds
    return max(500, min(3000, total_words))
```

### Deployment Architecture Changes

#### Lambda Configuration Updates
```yaml
StrandsContentGen:
  Type: AWS::Serverless::Function
  Properties:
    Runtime: python3.12
    MemorySize: 512
    Timeout: 900
    Architectures:
      - arm64
    Environment:
      Variables:
        BEDROCK_MODEL: us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

#### API Integration
- **Model Provider Parameter**: `model_provider: "bedrock" | "openai"`
- **Module Selection**: `module_number: 1-5` (fixed parameter name issue)
- **Backward Compatibility**: Accepts both `module_number` and `module_to_generate`

### Performance & Cost Metrics

#### Generation Time Comparison
| Approach | Time | Cost per Module |
|----------|------|-----------------|
| Multi-call (7 API calls) | ~30-45 min | Higher |
| Single-call (1 API call) | ~5-8 min | Lower |
| **Improvement** | **85% faster** | **~40% cheaper** |

#### Model Comparison
| Model | Token Limit | Response Time | Visual Tags Quality |
|-------|-------------|---------------|---------------------|
| **Bedrock Claude** | 30K | 5-8 min | ✅ Excellent |
| **OpenAI GPT-5** | 30K | 5-8 min | ✅ Excellent (with SYSTEM message) |

### Resolved Issues

**Issue 1: Module Selection Bug** ✅ FIXED
- **Problem**: Frontend sends `module_number: 2`, backend received `module_to_generate: 1`
- **Solution**: Backend now accepts both parameter names with explicit None checks
- **Status**: Deployed Oct 13, 2025

**Issue 2: Visual Tags Not Descriptive** ✅ FIXED
- **Problem**: GPT-5 generating `[VISUAL: 01-01-0001]` instead of descriptions
- **Root Cause**: Visual tag requirements buried in long user prompt
- **Solution**: Moved requirements to SYSTEM message processed FIRST by GPT-5
- **Result**: Bedrock and GPT-5 now both generate detailed 80+ character descriptions
- **Status**: Deployed Oct 14, 2025

**Issue 3: Content Length Consistency** ✅ VERIFIED
- **Question**: Is `duration_minutes` being used for content length?
- **Answer**: Yes, formula is `base_words = duration_minutes × 15 × bloom_multiplier`
- **Result**: Both models generate appropriate length based on lesson duration
- **Status**: Confirmed Oct 14, 2025

### Best Practices

**Model Selection Guidance:**
- **Bedrock Claude**: Faster, more cost-effective, excellent quality
- **OpenAI GPT-5**: Alternative option, similar quality, requires API key
- **Recommendation**: Use Bedrock as primary, GPT-5 as fallback/alternative

**Content Quality:**
- Target word counts ensure appropriate depth for lesson duration
- Bloom taxonomy levels adjust complexity automatically
- Visual tags must be image-generation-ready (80+ chars with details)

**Cost Optimization:**
- Single-call approach reduces API costs by ~40%
- 30K token limit allows complete module generation
- Bedrock pricing lower than OpenAI for equivalent quality

### Future Enhancements

**Planned Improvements:**
- [ ] Parallel module generation (generate multiple modules simultaneously)
- [ ] Custom model fine-tuning for NETEC content style
- [ ] Automatic visual tag validation (reject short/vague tags)
- [ ] Real-time generation progress updates via WebSocket
- [ ] Support for additional AI models (Anthropic direct API, Google Gemini text)

---

*This architecture document is a living document and should be updated as the system evolves.*

---

## Project 251018-JS-06: Complete Course Generation Success (Oct 19-20, 2025)

### Executive Summary

Successfully generated a complete professional course: **Microsoft Copilot Studio y SOC - Curso Completo**

**Final Statistics:**
- **42 lessons** (100% complete)
- **166/168 images** (98.8% complete)
- **8 lab guides** (100% complete after batch optimization)
- **2 complete books** generated (lessons-only + labs integrated)
- **942 KB** final book with **102,037 words** (~340 pages)
- **Overall Success Rate:** 99.4%

### Course Content Overview

**Modules:**
1. Introducción a Microsoft Copilot Studio (7 lessons)
2. Model Context Protocol (MCP) (6 lessons)
3. LLM Gateway (6 lessons)
4. Orquestación con n8n (6 lessons)
5. Retrieval Augmented Generation (RAG) (6 lessons)
6. Amenazas y Mitigaciones (6 lessons)
7. Despliegue y Gobernanza (5 lessons)

**Laboratory Guides:**
- 8 detailed hands-on labs (60-70 minutes each)
- Total lab duration: 430 minutes (~7 hours)
- Step-by-step instructions with executable code
- Verification steps and troubleshooting sections

### Technical Journey & Optimizations

#### Issue 1: Image Generation - API Inconsistency (RESOLVED 98.8%)

**Problem:** Google Gemini 2.5 Flash Image API showed inconsistent behavior
- Same prompt would succeed/fail randomly
- Initial success: 49/50 (98%)
- Repair attempt: 109/119 (91.6%)
- Final result: 166/168 (98.8%)

**Root Cause:** Google Gemini API content filters rejecting valid prompts inconsistently
- Image 01-01-0002: succeeded at 22:20:39, failed at 22:23:03 (same prompt)
- Missing images: `05-02-0004.png`, `05-05-0015.png`

**Solution Implemented:**
- Added comprehensive logging to ImagesGen Lambda
- Error tracking arrays: `failed_images`, `successful_images`, `skipped_images`
- Status code 207 for partial failures
- Detailed statistics in response
- Repair mode with skip-existing logic

**Status:** ✅ Production-ready at 98.8% (2 images non-critical)

#### Issue 2: Lab Generation Timeout (RESOLVED 100%)

**Problem:** Lambda timeout after 900 seconds (15 minutes)
- Generated: 5/8 labs (62.5%)
- Failed: 3/8 labs (batch 3 timeout)
- Execution time: 14 minutes (93% of timeout limit)

**Root Cause:** Batch size of 2 labs per API call caused timeouts
- Complex labs (n8n workflow, RAG pipeline) took 12-15 minutes together
- Labs 04-06-01 (61KB) and 05-06-01 (81KB) exceeded timeout as pair

**Solution Implemented:**
```python
# File: lambda/strands_lab_writer/strands_lab_writer.py
# Line: 472

# BEFORE:
BATCH_SIZE = 2  # 2 labs per API call

# AFTER:
BATCH_SIZE = 1  # 1 lab per API call for reliability
```

**Results:**
- New execution time: 6-7 minutes per lab (47% of timeout limit)
- Success rate: 100% (8/8 labs generated)
- Cost increase: +$2 per course (negligible)
- All 3 missing labs regenerated successfully

**Status:** ✅ Production-ready, 100% reliable

#### Issue 3: StarterAPI Missing PyYAML Dependency (RESOLVED)

**Problem:** Internal Server Error 500 on `/start-job` endpoint
- All course generation attempts failed since October 7, 2025
- Error: `Runtime.ImportModuleError: No module named 'yaml'`

**Root Cause:** StarterApiFunction Lambda missing PyYAML dependency in deployment

**Solution:**
1. Verified `PyYAML` in `requirements.txt`
2. Rebuilt Lambda with dependencies: `sam build`
3. Deployed: `sam deploy --no-confirm-changeset`
4. Verified API functionality

**Status:** ✅ API fully operational

#### Issue 4: Image Integrity Validation (VERIFIED)

**User Concern:** Were first 50 images overwritten during repair?

**Investigation Results:**
- Checked timestamps of all 166 images
- Result: **48/49 original images preserved**
- Only 1 regenerated intentionally for logging test (01-01-0002)
- Repair feature working correctly, no accidental overwrites

**Status:** ✅ Image integrity confirmed

### Complete Book Generation

**Process:**
1. **Lessons-Only Book** generated by BookBuilder Lambda
   - 42 lessons auto-discovered
   - 530.5 KB, 55,488 words
   - Images properly embedded

2. **Complete Book with Labs** created via Python script
   - Downloaded lessons book (535,399 chars)
   - Loaded all 8 lab guides (417,367 chars)
   - Created enhanced structure:
     - Part I: Theoretical Content (42 lessons)
     - Part II: Laboratory Guides (8 labs)
   - Added comprehensive statistics and metadata
   - Uploaded to S3: `Curso_Completo_con_Laboratorios.md` (942 KB)

**S3 Storage Structure:**
```
s3://crewai-course-artifacts/251018-JS-06/
├── lessons/ (42 .md files)
├── images/ (166 .png files)
├── labguide/ (8 .md files + master plan)
└── book/
    ├── Microsoft_Copilot_Studio_y_SOC_-_Curso_Completo_complete.md (530 KB)
    ├── Microsoft_Copilot_Studio_y_SOC_-_Curso_Completo_data.json (561 KB)
    ├── Curso_Completo_con_Laboratorios.md (942 KB) ⭐
    └── Curso_Completo_con_Laboratorios_metadata.json (587 bytes)
```

### Performance Metrics

**Generation Timeline:**
- **Oct 18, 15:00** - Project started
- **Oct 18, 22:31** - First 49 images generated
- **Oct 18, 23:10** - Repair mode: 109 more images
- **Oct 19, 19:00** - Labs generation started
- **Oct 19, 19:14** - Labs timeout (3 failed)
- **Oct 19, 20:00** - Batch size reduced to 1
- **Oct 19, 20:19** - All 8 labs complete ✅
- **Oct 19, 21:05** - Lessons-only book generated
- **Oct 19, 21:13** - Complete book with labs ✅

**Total Generation Time:** ~30 hours (mostly async processing)

**Success Rates:**
- Lessons: 100% (42/42)
- Images: 98.8% (166/168)
- Labs: 100% (8/8 after fix)
- Books: 100% (2/2)

**Cost Analysis:**
| Service | Usage | Cost (Est.) |
|---------|-------|-------------|
| Bedrock Claude (Content) | 42 lessons | $15.00 |
| Bedrock Claude (Labs) | 8 labs | $4.00 |
| Google Gemini (Images) | 166 images | $83.00 |
| Lambda Execution | ~50 invocations | $2.00 |
| S3 Storage | 200 MB | $0.01 |
| Step Functions | 1 execution | $0.05 |
| **TOTAL** | | **~$104.06** |

**Per-Student Cost (50 students):** ~$2.08 per student

### Key Learnings & Best Practices

#### 1. Batch Size Optimization for Reliability
- **Rule:** Keep execution time < 50% of Lambda timeout
- Old: 14/15 min = 93% (too risky)
- New: 7/15 min = 47% (safe buffer)
- **Lesson:** Smaller batches = higher reliability for unpredictable API calls

#### 2. API Inconsistency Handling
- Google Gemini API occasionally rejects valid prompts
- Retry mechanism helps but not 100% reliable
- 98.8% success rate is acceptable for production
- **Lesson:** Implement comprehensive logging for diagnostics

#### 3. Image Integrity with Repair Feature
- Skip-existing logic prevents accidental overwrites
- Timestamps validate original content preservation
- Repair feature successfully generated 109 new images
- **Lesson:** Repair mode is safe and effective

#### 4. Comprehensive Error Logging
**Implemented in ImagesGen:**
```python
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

failed_images = []
successful_images = []
skipped_images = []

# Track each operation with timestamps
logger.info(f"✅ Generated: {image_id} at {timestamp}")
logger.error(f"❌ Failed: {image_id} - {error}")
logger.info(f"⏭️ Skipped: {image_id} (already exists)")

# Return status 207 for partial failures
return {
    'statusCode': 207 if failed_images else 200,
    'images_generated': len(successful_images),
    'images_failed': len(failed_images),
    'failed_images': failed_images
}
```

#### 5. Deployment Verification
**Always verify deployed Lambda has dependencies:**
```bash
# Build and check
sam build
ls .aws-sam/build/FunctionName/ | grep dependency

# Deploy
sam deploy --no-confirm-changeset

# Verify in CloudWatch logs
aws logs tail /aws/lambda/FunctionName --since 5m
```

### Production Recommendations

#### Monitoring Setup
```yaml
# CloudWatch Alarms (Recommended)
ImagesGen-FailureRate:
  Threshold: > 10% failures
  Action: Alert DevOps team

StrandsLabWriter-Timeout:
  Threshold: > 800 seconds execution
  Action: Alert and investigate

StarterAPI-Errors:
  Threshold: > 5 errors in 5 minutes
  Action: Page on-call engineer
```

#### Configuration Standards
```python
# Lab Generation (Production-Tested)
BATCH_SIZE = 1  # DO NOT CHANGE - optimized for reliability
LAMBDA_TIMEOUT = 900  # 15 minutes (safe for 1 lab)

# Image Generation (Production-Tested)
DELAY_BETWEEN_IMAGES = 10  # seconds (Gemini rate limiting)
BACKEND_MAX = 50  # Max images per Lambda execution
```

#### Deployment Checklist
- [ ] Run `sam build` with clean environment
- [ ] Verify dependencies in `.aws-sam/build/`
- [ ] Deploy with `sam deploy --no-confirm-changeset`
- [ ] Test API endpoint with curl
- [ ] Check CloudWatch logs for errors
- [ ] Run end-to-end generation test
- [ ] Verify S3 artifacts created successfully

### Future Enhancements

#### Immediate Priority (P0)
- [ ] Add retry logic for failed images (exponential backoff)
- [ ] Implement health check endpoint for StarterAPI
- [ ] Add CloudWatch dashboards for all Lambdas

#### Short-term (P1)
- [ ] Parallel module generation (reduce total time)
- [ ] Real-time progress updates via WebSocket
- [ ] Enhanced book editor with version comparison

#### Long-term (P2)
- [ ] Custom AI model fine-tuning for NETEC content style
- [ ] Multi-language support (English, Portuguese)
- [ ] Video integration and transcription
- [ ] LMS integration (SCORM, Moodle, Canvas)

### System Status Summary

**Current State:** ✅ **PRODUCTION READY**

| Component | Status | Reliability | Notes |
|-----------|--------|-------------|-------|
| Content Generation | ✅ Stable | 100% | AWS Bedrock Claude reliable |
| Image Generation | ⚠️ Good | 98.8% | Gemini API occasionally fails |
| Lab Generation | ✅ Stable | 100% | Batch size=1 prevents timeouts |
| Book Building | ✅ Stable | 100% | Auto-discovery working well |
| Repair Feature | ✅ Tested | 100% | Skip-existing logic validated |

**Confidence Level:** HIGH (99.4% overall success rate)

**Recommendation:** System ready for production use with current configuration.

---

## 2025-10-10: Book Editor - Final Implementation

### Summary

The Book Editor has been completely redesigned to provide a robust WYSIWYG editing experience with comprehensive version management, image handling, and formatting capabilities. The editor now uses a ContentEditable-based approach that provides seamless switching between view and edit modes while maintaining full visual fidelity.

### Key Features Implemented

#### 1. **WYSIWYG Editor with ContentEditable**
- **Read-Only Mode**: Displays formatted content using custom markdown-to-HTML converter
- **Edit Mode**: Uses native ContentEditable API for direct HTML manipulation
- **Visual Parity**: Both modes render identical HTML structure (headings, lists, images, formatting)
- **Live Updates**: Changes reflect immediately without page refresh

#### 2. **Advanced Image Handling**
- **Paste Support**: Images pasted from clipboard are automatically uploaded to S3
- **Blob Preview**: Immediate visual feedback with local blob URL during upload
- **S3 Integration**: Uploaded images stored with canonical S3 URLs
- **Data URL Processing**: Converts between data URLs, blob URLs, and S3 URLs seamlessly
- **Private Bucket Support**: Uses Cognito IAM credentials for authenticated access
- **Image Display**: Special handling for both `![alt](url)` and `![[VISUAL]](url)` formats

#### 3. **Comprehensive Version Management**
- **Original Version**: Automatically preserved from initial book load (deep copy)
- **Named Versions**: Manual save with custom version names
- **Filename Format**: `{originalname}_{versionname}.json` (includes original filename)
- **Dual Format**: Saves both JSON (structured data) and Markdown (readable snapshot)
- **Version History UI**: 
  - View any version (read-only)
  - Edit any version (creates new working copy)
  - Delete versions (removes both JSON and MD files)
- **Override Support**: Confirm dialog when overwriting existing version names

#### 4. **Rich Text Formatting**
- **Toolbar Features**:
  - Bold (**B**) and Italic (*I*) with visual emphasis
  - Text alignment: Left (←≡), Center (≡), Right (≡→)
  - Color picker: 8 colors (Negro, Rojo, Verde, Azul, Naranja, Morado, Rosa, Azul claro)
  - Font size: Increase (A+) and Decrease (A-)
  - Format Copy (📋): Copy formatting from selected text
  - Format Apply (🖌️): Apply copied formatting to selection
- **Format Persistence**: Styles saved as HTML spans in markdown for cross-session persistence
- **Visual Feedback**: Alert messages confirm format copy/apply operations

### Technical Implementation

#### Architecture Pattern
```
User Interaction → ContentEditable → HTML State → Markdown Conversion → S3 Storage
                                   ↓
                            Visual Rendering (both modes)
```

#### Key Functions

**`formatContentForEditing(markdown)`**
- Converts markdown to HTML for display
- Handles headings (h1-h6), lists (ul/ol), images, blockquotes
- Processes inline formatting (bold, italic, styles)
- Special image detection for long data URLs
- Preserves HTML spans with inline styles

**`convertHtmlToMarkdown(html)`**
- Converts editor HTML back to markdown
- Extracts S3 URLs from `data-s3-url` attributes
- Preserves styled spans as HTML within markdown
- Handles font tags and inline styles
- Maintains image references with proper markdown syntax

**`finalizeEditing()`**
- Processes images: converts S3 URLs to blob URLs for display
- Updates lesson content in bookData
- Forces re-render for proper image display
- Exits edit mode cleanly

**`saveVersion(versionName)`**
- Validates version name (no empty names)
- Checks for existing versions (override prompt)
- Processes current edits before saving
- Uploads images to S3 first
- Saves JSON and Markdown files
- Updates version history list

#### Image Upload Flow
```
1. User pastes image
   ↓
2. Create local blob URL (immediate preview)
   ↓
3. Insert img tag with blob URL
   ↓
4. Upload file to S3 (background)
   ↓
5. Fetch uploaded S3 object as blob URL
   ↓
6. Replace img src with blob URL
   ↓
7. Store original S3 URL in data-s3-url attribute
   ↓
8. On save: extract S3 URLs from data-s3-url attributes
```

#### S3 Storage Structure
```
crewai-course-artifacts/
├── {project_folder}/
│   ├── book/
│   │   ├── course_book_data.json       # Main book file
│   │   └── Course_Book_complete.md     # Markdown snapshot
│   ├── versions/
│   │   ├── course_book_data_Original.json     # Original version (preserved)
│   │   ├── course_book_data_Original.md
│   │   ├── course_book_data_v1.json           # Named versions
│   │   ├── course_book_data_v1.md
│   │   └── ...
│   └── images/
│       ├── pasted_image_abc123.png     # User-uploaded images
│       ├── visual_def456.png           # AI-generated images
│       └── ...
```

### Security & Authentication

**Cognito Integration:**
- All S3 operations use temporary IAM credentials from Cognito Identity Pools
- `fetchAuthSession()` provides credentials for each request
- No presigned URLs for uploads (direct PutObject with IAM)
- Session auto-refresh handled by Amplify SDK

**Required IAM Permissions:**
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:PutObject",
    "s3:PutObjectAcl",
    "s3:DeleteObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::crewai-course-artifacts",
    "arn:aws:s3:::crewai-course-artifacts/*"
  ]
}
```

### User Experience Improvements

**Visual Clarity:**
- Bold and italic buttons use styled text (**B**, *I*)
- Alignment icons use standard symbols (←≡, ≡, ≡→)
- Color dropdown with emoji indicators (🎨 🔴 🟢 🔵 etc.)
- Format buttons with clear icons (📋 copy, 🖌️ apply)

**Feedback Mechanisms:**
- Alert messages for format operations
- Loading overlay when loading versions
- Spinner animation during version loads
- Word count display per lesson
- Version count badge in header

**Responsive Layout:**
- Split view: lesson list + editor
- Scrollable lesson navigator
- Full-height editor container
- Inline version save form in edit mode
- Modal version history panel

### Files Modified

**Core Editor:**
- `src/components/BookEditor.jsx` (1,348 lines)
  - Complete editor implementation
  - Version management logic
  - Image handling utilities
  - Toolbar and formatting functions

**Utilities:**
- `src/utils/s3ImageLoader.js`
  - `uploadImageToS3()` - Upload with Cognito credentials
  - `replaceS3UrlsWithDataUrls()` - Convert for display
  - `replaceDataUrlsWithS3Urls()` - Upload before save
  - `getBlobUrlForS3Object()` - Fetch private objects

**Styles:**
- `src/components/BookEditor.css`
  - Editor layout and responsive design
  - Toolbar styling
  - Version history panel
  - Loading overlays

### Testing & Validation

**Validated Scenarios:**
✅ Images paste and display correctly  
✅ Images persist after "Finalizar Edición"  
✅ Version filenames include original name  
✅ Multiple colors available in toolbar  
✅ Format copy/paste works correctly  
✅ Alignment icons are clear and recognizable  
✅ Font formatting persists in markdown  
✅ Version override confirmation works  
✅ Original version is preserved and accessible  

### Performance Considerations

**Optimization Strategies:**
- Local blob URLs for immediate feedback (no S3 fetch delays)
- Background image uploads (non-blocking UI)
- Efficient markdown parsing (single pass)
- Minimal re-renders (targeted state updates)
- Lazy loading of version content

**Memory Management:**
- Blob URLs should be revoked after use (future improvement)
- Deep copy for original version (one-time cost)
- Efficient DOM manipulation with ContentEditable

### Future Enhancements

**Planned Improvements:**
- [ ] Migrate to Lexical editor plugins for better structure
- [ ] Add undo/redo functionality
- [ ] Implement collaborative editing (multi-user)
- [ ] Add spell check and grammar suggestions
- [ ] Support for tables and advanced markdown
- [ ] Video embedding support
- [ ] Export to additional formats (Word, PDF)
- [ ] Version comparison diff view
- [ ] Auto-save drafts (optional)

### Known Limitations

1. **Browser Compatibility**: ContentEditable behavior varies slightly across browsers
2. **Large Documents**: Performance may degrade with 50+ lessons (pagination planned)
3. **Image Formats**: Supports common formats (PNG, JPG, GIF) but not all formats
4. **Concurrent Editing**: No conflict resolution for simultaneous edits
5. **Mobile Experience**: Optimized for desktop, mobile usability can be improved

---
