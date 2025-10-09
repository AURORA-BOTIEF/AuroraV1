# AURORA V1 - System Architecture Documentation

**Project:** Aurora - AI-Powered Course Generation Platform  
**Organization:** NETEC  
**Last Updated:** October 8, 2025  
**Version:** 1.0  
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

**Document Version:** 1.0  
**Last Updated:** October 8, 2025  
**Authors:** System Analysis Team  
**Next Review:** Q1 2026

---

*This architecture document is a living document and should be updated as the system evolves.*
