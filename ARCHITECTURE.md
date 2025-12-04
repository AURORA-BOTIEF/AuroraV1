# AURORA V1 - System Architecture Documentation

**Project:** Aurora - AI-Powered Course Generation Platform  
**Organization:** NETEC  
**Last Updated:** December 4, 2025  
**Version:** 1.5  
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

### Key Component Architecture

#### 1. Book Editor (`BookEditor.jsx`)
**Purpose:** Comprehensive WYSIWYG editor for course content.

**Architecture:**
- **Layout Strategy:**
  - **Container:** Uses `.book-content-container` (renamed from `.editor-container`) to prevent CSS collisions with other editors.
  - **Sidebar:** Internal `.lesson-navigator` sidebar with forced visibility (`display: block !important`) to ensure module/lesson navigation is always accessible.
- **State Management:**
  - Manages `bookData` (JSON) and `labGuideData` independently.
  - Handles version control with local history and S3 persistence.
- **Integration:**
  - Direct S3 loading/saving via `LoadBookFunction` and `SaveBookFunction`.
  - PowerPoint generation trigger via `StrandsInfographicGenerator`.

#### 2. Slides Editor & Viewer (`InfographicEditor.jsx` / `InfographicViewer.jsx`)
**Purpose:** Edit and view HTML-first presentations with pixel-perfect rendering.

**Architecture:**
- **Iframe Isolation:**
  - Content rendered inside an `<iframe>` to isolate slide CSS from application styles.
  - `srcDoc` used for immediate rendering of generated HTML.
- **Secure Image Loading (The "S3 Loader" Pattern):**
  - **Problem:** Images are stored in private S3 buckets; standard `<img>` tags cannot load them directly.
  - **Solution:**
    1. **Fetch:** Parent component uses `s3ImageLoader.js` to fetch images using Cognito credentials.
    2. **Blob:** Converts S3 objects to local Blob URLs.
    3. **Transport:** Sends Blob URLs to iframe via `postMessage`.
    4. **Injection:** Injects a client-side script into the iframe that listens for `UPDATE_IMAGE_SRC` events.
    5. **Update:** Script updates both `src` attributes and `background-image` styles dynamically.
- **Sidebar Logic:**
  - Main application sidebar is conditionally hidden in `App.jsx` (`Layout` component) for these routes.
  - Global CSS hiding rules were removed to prevent conflicts with other pages.

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

#### 5. StrandsInfographicGenerator (HTML-First Presentation Generator)

**Purpose:** Generate professional, branded HTML presentations with optional PowerPoint export

**Configuration:**
- Runtime: Python 3.12
- Memory: 1024 MB
- Timeout: 900 seconds (15 minutes)
- Architecture: ARM64
- Layer: None (lightweight HTML generation)

**HTML-First Architecture Philosophy:**

Aurora's presentation generator uses **HTML as the single source of truth** for all slide content and styling. This architectural decision provides several key benefits:

1. **Self-Contained Output**: Complete presentation in a single HTML file with embedded CSS
2. **Universal Compatibility**: Opens in any browser without external dependencies
3. **Easy Debugging**: Inspect slides directly in browser DevTools
4. **Future-Proof**: HTML/CSS is platform-independent and version-stable
5. **Optional PPT Export**: PowerPoint conversion is secondary, not primary

**Key Features:**
- ✅ Self-contained HTML with embedded CSS (no external stylesheets)
- ✅ Professional Netec branding (colors, logo, layouts)
- ✅ AI-powered slide structure generation (Bedrock/OpenAI)
- ✅ Multiple slide types (course title, module title, lesson title, content)
- ✅ Hierarchical bullet lists with nested styling
- ✅ Embedded S3 images with presigned URLs
- ✅ Responsive grid layouts for side-by-side images
- ✅ Print-ready CSS for PDF export
- ✅ Pixel-perfect slide dimensions (1280x720px)

**Architecture: HTML as Source of Truth**

```
Course Book JSON → AI Slide Structure → HTML Generation → Browser Preview
                                            ↓
                                     S3: infographics/*.html
                                            ↓
                                    (Self-contained, ready to use)
```

**Workflow:**

**Phase 1: AI Slide Structure Generation**
```python
def generate_slide_structure(book_data: Dict, slides_per_lesson: int) -> Dict:
    """
    Uses AI (Bedrock Claude / OpenAI GPT) to analyze lesson content
    and create optimal slide structure with proper content distribution.
    
    Returns JSON structure with:
    - slide_type: 'title' | 'content' | 'bullets' | 'image-left' | 'image-right'
    - title: Slide headline
    - subtitle: Optional subheading
    - content_blocks: List of bullets, images, callouts
    - layout: Visual layout strategy
    """
```

**Phase 2: HTML Generation with Embedded CSS**
```python
def generate_complete_html(slides: List[Dict], course_title: str) -> str:
    """
    Generates self-contained HTML with:
    - Embedded CSS in <style> tag (no external files)
    - Semantic HTML structure (<div class="slide">, <ul class="bullets">)
    - Presigned S3 image URLs (valid for 1 hour)
    - Netec branding (logo, colors, gradients)
    
    Output: Single .html file that works standalone
    """
```

**CSS Architecture (Embedded in HTML):**

```css
/* Slide container - Fixed presentation dimensions */
.slide {
    width: 1280px;
    height: 720px;
    background: white;
    overflow: hidden;  /* Prevent scrolling */
    page-break-after: always;  /* Print-friendly */
}

/* Course title slide - Full-screen gradient */
.course-title-slide {
    background: linear-gradient(135deg, #003366, #4682B4);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Module title slide - Branded section divider */
.module-title-slide {
    background: linear-gradient(to right, #003366, #4682B4);
    border-left: 8px solid #FFC000;  /* Netec yellow accent */
}

/* Lesson title slide - Clean white with top accent */
.lesson-title-slide {
    background: white;
    border-top: 10px solid #FFC000;
    color: #003366;
}

/* Hierarchical bullets (agenda slides) */
.bullets li {
    color: #000000;  /* Black text for readability */
    font-size: 20pt;
}

.bullets li:before {
    content: '▶';  /* Primary bullet marker */
    color: #FFC000;  /* Netec yellow */
}

.bullets li ul li {
    font-size: 18pt;
    padding-left: 20px;  /* Indentation for nested items */
}

.bullets li ul li:before {
    content: '○';  /* Secondary bullet marker */
    color: #003366;  /* Netec blue */
}
```

**Special Slide Layouts:**

1. **Course Title Slide**
   - Full-screen gradient background
   - 72pt title
   - Logo in top-right corner
   - Used for: Opening slide

2. **Module Title Slide**
   - Gradient background
   - 56pt title with left accent border
   - Logo centered at bottom
   - Used for: Section dividers

3. **Lesson Title Slide**
   - White background with top accent bar
   - 48pt title + module name subtitle
   - Logo in top-right
   - Used for: Topic introductions

4. **Content Slides**
   - Header with title/subtitle
   - Max content height: 520px (prevents overflow)
   - Supports: bullets, images, callouts
   - Logo in bottom-right

**Image Integration:**

```python
def generate_presigned_image_urls(image_mapping: Dict) -> Dict:
    """
    Converts S3 paths to presigned URLs for HTML embedding.
    
    - Expires: 1 hour (sufficient for viewing/editing)
    - Permissions: Read-only
    - CORS: Enabled for browser access
    
    Note: Images load directly in browser without auth
    """
```

**Side-by-Side Image Layout (Fixed Nov 2025):**

```html
<!-- Grid layout for multiple images -->
<div class="image-grid">
    <div class="image-wrapper">
        <img src="presigned-url-1.png" alt="Image 1">
    </div>
    <div class="image-wrapper">
        <img src="presigned-url-2.png" alt="Image 2">
    </div>
</div>
```

```css
/* CSS Grid for side-by-side images */
.image-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;  /* Equal columns */
    gap: 30px;
    padding: 20px;
}

.image-wrapper img {
    max-width: 100%;
    max-height: 400px;
    object-fit: contain;  /* Preserve aspect ratio */
}
```

**Agenda Slide with Nested Bullets (Fixed Nov 2025):**

**Problem:** Double bullets appeared (CSS bullet + text ○ symbol)

**Solution:** Proper HTML nesting with CSS classes

```python
# Python: Generate structured agenda data
def create_agenda_slides(modules: List[Dict]) -> List[Dict]:
    agenda_items = []
    for module in modules:
        # Level 1: Module (no nested list)
        agenda_items.append({
            'text': module['title'],
            'lessons': []  # Nested lessons
        })
        
        for lesson in module['lessons']:
            # Level 2: Lesson (nested under module)
            agenda_items[-1]['lessons'].append(lesson['title'])
    
    return [{
        'slide_type': 'single-column',
        'content_blocks': [{
            'type': 'nested-bullets',  # Special type for hierarchy
            'items': agenda_items
        }]
    }]
```

```python
# HTML Generation: Nested <ul> structure
html = '<ul class="bullets">'
for item in agenda_items:
    html += f'<li>{item["text"]}'  # Module title
    
    if item['lessons']:
        html += '<ul>'  # Nested list for lessons
        for lesson in item['lessons']:
            html += f'<li>{lesson}</li>'
        html += '</ul>'
    
    html += '</li>'
html += '</ul>'
```

**Result:** Clean hierarchy with proper indentation, no double bullets

**Batch Processing Architecture:**

Aurora uses a sophisticated batch processing system to handle large courses (16+ lessons) within Lambda timeout limits:

```
Step Functions Orchestration
    ↓
PptBatchOrchestrator (State Machine)
    ├── Batch 0: Lessons 1-3  → Generate slides → Save to shared JSON
    ├── Batch 1: Lessons 4-6  → Generate slides → Append to JSON
    ├── Batch 2: Lessons 7-9  → Generate slides → Append to JSON
    ...
    └── Batch N (final): Lessons 13-16
            ↓
        Generate slides → Append to JSON
            ↓
        completion_status = 'complete'
            ↓
        Generate HTML from complete JSON
            ↓
        Save final HTML to S3
```

**Shared State Management:**

```python
# infographic_structure.json accumulates slides from all batches
{
    "course_title": "Course Name",
    "slides": [
        # Batch 0 slides (lessons 1-3)
        {"slide_number": 1, "title": "Agenda", ...},
        {"slide_number": 2, "title": "Module 1", ...},
        ...
        # Batch 1 slides (lessons 4-6) - APPENDED
        {"slide_number": 15, "title": "Lesson 4", ...},
        ...
        # Batch N slides (final lessons) - APPENDED
        {"slide_number": 45, "title": "Thank You", ...}
    ],
    "total_slides": 46,
    "image_url_mapping": {
        # Merged from all batches
        "01-01-0001": "s3://bucket/image1.png",
        "02-03-0005": "s3://bucket/image2.png"
    },
    "completion_status": "complete",  # Only set by final batch
    "last_batch_index": 5
}
```

**Batch Completion Detection:**

```python
def determine_completion_status(
    lesson_batch_end: int,
    total_lessons: int
) -> str:
    """
    Critical logic: Only final batch generates HTML
    
    - Batches 0-4: completion_status = 'partial' (save JSON only)
    - Batch 5 (final): completion_status = 'complete' (generate HTML)
    
    Bug Fix (Nov 2025):
    - lesson_batch_end must be absolute lesson number (3, 6, 9, 12, 15, 16)
    - NOT capped at len(lessons)=3 (caused all batches to be partial)
    """
    is_final_batch = (lesson_batch_end >= total_lessons)
    return 'complete' if is_final_batch else 'partial'
```

**Benefits of Batch Architecture:**

- ✅ Handles unlimited course size (no Lambda timeout)
- ✅ Parallel processing (6 batches can run simultaneously)
- ✅ Better error isolation (one batch fails, others continue)
- ✅ Memory efficient (processes 3 lessons at a time)
- ✅ Single final HTML output (no fragmentation)

**Input Event:**
```json
{
  "course_bucket": "crewai-course-artifacts",
  "project_folder": "251104-mini-cisco",
  "book_version_key": "project/book/Generated_Course_Book_data.json",
  "book_type": "theory",
  "lesson_start": 1,
  "lesson_end": 3,
  "total_lessons": 16,
  "batch_index": 0,
  "model_provider": "bedrock",
  "style": "professional"
}
```

**Output (Final Batch Only):**
```json
{
  "statusCode": 200,
  "message": "Complete presentation generated successfully",
  "course_title": "Fundamentos de Redes y Cisco IOS",
  "total_slides": 46,
  "completion_status": "complete",
  "structure_s3_key": "project/infographics/infographic_structure.json",
  "html_s3_key": "project/infographics/infographic.html",
  "pptx_s3_key": null
}
```

**Output (Partial Batches):**
```json
{
  "statusCode": 200,
  "message": "Partial presentation generated (lessons 1-3 of 16)",
  "batch_slides": 10,
  "total_slides_so_far": 10,
  "completion_status": "partial",
  "structure_s3_key": "project/infographics/infographic_structure.json",
  "html_s3_key": null,  # Not generated for partial batches
  "pptx_s3_key": null
}
```

**S3 Artifacts:**

```
project/infographics/
├── infographic_structure.json    # Shared state (all batches)
├── infographic.html              # Final HTML (final batch only)
└── (optional) course.pptx        # PowerPoint export (if enabled)
```

**HTML File Characteristics:**

- **Size:** ~50-200 KB (depends on slide count)
- **Dependencies:** None (self-contained)
- **Images:** Presigned S3 URLs (expire after 1 hour)
- **Compatibility:** Any modern browser (Chrome, Firefox, Safari, Edge)
- **Print:** CSS print rules for PDF export
- **Editing:** Can be edited in browser DevTools or text editor

**Why No PPT Generation?**

HTML-first architecture makes PowerPoint conversion **optional**, not required:

1. **HTML is sufficient**: Instructors can present directly from browser
2. **Print to PDF**: Browser print → PDF gives presentation file
3. **Universal access**: No PowerPoint license needed
4. **Easier editing**: HTML/CSS is text-based, version-controllable
5. **Future flexibility**: Can convert to any format (PDF, PPTX, Google Slides)

**Error Handling:**
- AI generation failures → Retry with simplified prompt
- Image load failures → Display placeholder with description
- S3 access errors → Retry with exponential backoff
- Timeout → Save partial progress to shared JSON

**Performance:**
- Typical execution: 60-120 seconds per batch (3 lessons)
- Memory usage: ~300-500 MB
- Supports: Unlimited slides (batched processing)

**Future Enhancements:**
- Interactive slides (JavaScript animations)
- Speaker notes export
- Video embedding
- Live collaboration mode

---

#### 6. Supporting API Functions

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

#### PPTLayer
**Contents:**
- python-pptx
- lxml
- Pillow (PIL)

**Build Script:**
```bash
cd CG-Backend/lambda-layers
./build-ppt-layer.sh
```

---

## Complete Course Generation Workflow

Aurora implements a sophisticated batch processing workflow for generating complete courses with parallel execution, retry logic, and intelligent orchestration.

### High-Level Flow

```
User Request → API Gateway → StarterApiFunction → Step Functions
                                                        ↓
                            ┌───────────────────────────┴───────────────────────────┐
                            ↓                                                       ↓
                   InitializeImageGeneration                            BatchExpander
                   (Setup image state)                                  (Split into batches)
                            ↓                                                       ↓
                            │                                             ┌─────────┴─────────┐
                            │                                             ↓                   ↓
                            │                                      Batch 1 (3 lessons)  Batch 2 (3 lessons)
                            │                                             ↓                   ↓
                            │                                      StrandsContentGen    StrandsContentGen
                            │                                      (Parallel Map)       (Parallel Map)
                            │                                             ↓                   ↓
                            │                                      Content + Visual Tags Generated
                            │                                             ↓
                            │                                      StrandsVisualPlanner
                            │                                      (Classify all visual tags)
                            │                                             ↓
                            └────────────────────────────────────────────┤
                                                                         ↓
                                                              ProcessImageBatch
                                                              (Map over prompts)
                                                                         ↓
                                                                    ImagesGen
                                                            (Gemini 2.5 Flash Image
                                                         with prompt optimization & retry)
                                                                         ↓
                                                                  100% Success Rate
                                                                         ↓
                                                                  LabBatchExpander
                                                                  (Split lab guides)
                                                                         ↓
                                                                  StrandsLabPlanner
                                                                  & StrandsLabWriter
                                                                         ↓
                                                                   BookBuilder
                                                                  (Assemble final book)
                                                                         ↓
                                                                Complete Course Ready
```

### Batch Processing Strategy

**Purpose:** Handle large courses (40+ hours, 100+ lessons) within Lambda execution limits

**Implementation:**
- **BatchExpander**: Splits modules into batches of 3 lessons each
- **Parallel Execution**: Each batch runs independently in Step Functions Map state
- **Aggregation**: Results merged after all batches complete

**Benefits:**
- ✅ No Lambda timeout (900s limit avoided)
- ✅ Faster execution (parallel processing)
- ✅ Better error isolation (one batch fails, others continue)
- ✅ Cost optimization (shorter-lived functions)

**Configuration:**
```python
# lambda/batch_expander.py
MAX_LESSONS_PER_BATCH = 3  # Optimized for 900s Lambda timeout
```

### Image Generation System

**Model:** Gemini 2.5 Flash Image (`models/gemini-2.5-flash-image`)  
**Status:** Production-ready, 100% success rate (November 2025)  
**Architecture:** Lambda function + Lambda Layer with Vertex AI SDK support

#### Layer Configuration

**GeminiLayer v18:**
- Size: 191 MB unzipped (optimized with cache removal)
- Dependencies:
  - `google-generativeai` (Gemini API)
  - `google-cloud-aiplatform` (Vertex AI/Imagen 4.0)
  - `Pillow` (image processing)
- Build: `/CG-Backend/lambda-layers/build-gemini-layer.sh`

**ImagesGen Function:**
- Code size: 26 KB (minimal, no dependencies)
- Total with layer: ~191 MB (under 250 MB limit)
- Requirements.txt: Empty (all deps in layer)
- Timeout: 900 seconds
- Memory: 1024 MB

#### Key Improvements (November 2025)

**1. Prompt Optimization**
```python
def optimize_prompt_for_gemini(prompt_text: str) -> str:
    """
    Enhances prompts for better Gemini results:
    - Detects text-heavy content (tables, screenshots, code)
    - Converts to conceptual illustrations
    - Adds style guidance: "professional, modern, clean"
    - Includes quality keywords
    """
```

**2. Automatic Retry Logic**
- MAX_RETRIES = 2 (up to 3 total attempts)
- RETRY_DELAY = 3 seconds between attempts
- Simplified fallback prompts on failure
- Handles empty image data gracefully

**3. Safety Settings (Permissive for Educational Content)**
```python
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
]
```

**4. Enhanced Error Recovery**
- Safety filter blocks → retry with simplified prompt
- Empty responses → automatic retry with fallback
- Detailed logging: prompt_feedback, finish_reason, safety_ratings

#### Performance Metrics

- **Success Rate:** 100% (up from ~50% before improvements)
- **Average Time:** ~7 seconds per image
- **Retry Usage:** ~10% of images need 1 retry attempt
- **Safety Blocks:** 0% (permissive settings for education)
- **Cost:** ~$0.001 per image

#### Future Model Support

**Vertex AI SDK (Imagen 4.0 Ultra):**
- ✅ Deployed in GeminiLayer v18
- ✅ Available but not currently active
- ✅ Can switch via `DEFAULT_IMAGE_MODEL = 'imagen'`
- Expected: Better text rendering, technical diagrams

### Lab Guide Generation

**Process:**
1. **LabBatchExpander**: Splits lab guides into batches of 3
2. **StrandsLabPlanner**: Plans hands-on exercises using AI
3. **StrandsLabWriter**: Writes step-by-step instructions
4. **Output**: Markdown files with practical exercises

**Integration:** Lab guides embedded in lessons via `[VISUAL: type=labguide ...]` tags

### Final Book Assembly

**BookBuilder Function:**
- Collects all lessons from S3 (`{project}/lessons/*.md`)
- Replaces visual tags with image links
- Replaces lab guide tags with lab content
- Generates two outputs:
  - `Course_Book_complete.md`: Full Markdown book
  - `Course_Book_data.json`: Structured JSON for editor

**Image Mapping Format (Optimized):**
```json
{
  "image_mappings": {
    "image-001": {
      "s3_key": "project/images/image-001.png",
      "description": "Cloud architecture diagram"
    }
  }
}
```
*Note: Changed from `[VISUAL:...]` keys to IDs to stay under Step Functions 40KB limit*

**Book Structure:**
```markdown
# Course Title
## Module 1: Module Name
### Lesson 1: Lesson Title
#### Learning Objectives
- Objective 1
- Objective 2

#### Introduction
Content...

#### Theoretical Foundations
Content with ![Image](s3://bucket/project/images/image-001.png)

#### Hands-On Exercises
Lab guide content...

#### Summary
Content...
```

---

### Step Functions State Machine

**Name:** CourseGeneratorStateMachine

**Type:** Standard (not Express)

**Updated Workflow (November 2025):**
```
StarterApiFunction (Entry Point)
    ↓
InitializeImageGeneration (Setup remaining_prompts=[])
    ↓
BatchExpander (Split modules into lesson batches)
    ↓
ProcessBatches (Map State - Parallel Execution)
    ├── Batch 1 → StrandsContentGen (3 lessons)
    ├── Batch 2 → StrandsContentGen (3 lessons)
    └── Batch N → StrandsContentGen (3 lessons)
    ↓
StrandsVisualPlanner (Classify all visual tags)
    ↓
ProcessImageBatch (Map State - Generate all images)
    ├── Image 1 → ImagesGen (with retry)
    ├── Image 2 → ImagesGen (with retry)
    └── Image N → ImagesGen (with retry)
    ↓
LabBatchExpander (Split lab guides)
    ↓
ProcessLabBatches (Map State)
    ├── Lab 1 → StrandsLabPlanner → StrandsLabWriter
    ├── Lab 2 → StrandsLabPlanner → StrandsLabWriter
    └── Lab N → StrandsLabPlanner → StrandsLabWriter
    ↓
BookBuilder (Assemble final book)
    ↓
SuccessState (Complete)
```

---

### Step Functions State Machine (Legacy)

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

**Document Version:** 1.5  
**Last Updated:** December 4, 2025  
**Authors:** System Analysis Team, Juan Ossa (Book Editor Implementation, Regenerate Lesson Feature), Content Generation Team  
**Production Status:** ✅ **READY** (All improvements deployed)  
**Last Deployment:** December 4, 2025  
**Validated Success Rate:** 99.4%+ (Multiple production courses)  
**New Features:** Regenerate Lesson/Lab, State Machine Conditional Routing, Lab Guide Deduplication

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

## 2025-11-04: Production Milestone - Batch Processing & 100% Image Success Rate

### Executive Summary

**Achievement:** Complete course generation system with **100% image generation success rate** and robust batch processing for large courses (40+ hours).

**Impact:**
- ✅ Large courses (100+ lessons) generate successfully
- ✅ Image generation: 100% success (up from ~50%)
- ✅ No Lambda timeouts (optimized batch sizes)
- ✅ Production-ready deployment workflow
- ✅ Comprehensive monitoring and error recovery

### Key Improvements Implemented

#### 1. Batch Processing Architecture

**Problem:** Large courses (40-hour, 100+ lessons) exceeded Lambda 900s timeout limit.

**Solution:** Implemented intelligent batch processing system
- `BatchExpander`: Splits modules into batches of 3 lessons
- `LabBatchExpander`: Splits lab guides into batches of 3
- Step Functions Map States: Parallel execution
- Optimized for AWS Lambda limits

**Results:**
- ✅ Large courses complete in 15-20 minutes (previously timed out)
- ✅ Better error isolation (batch-level failures)
- ✅ Cost optimized (shorter function executions)
- ✅ Scalable to unlimited course sizes

**Implementation:**
```python
# CG-Backend/lambda/batch_expander.py
MAX_LESSONS_PER_BATCH = 3  # Optimized for 900s Lambda timeout
```

#### 2. Image Generation System Overhaul

**Problem:** Gemini 2.5 Flash Image had ~50% success rate, inconsistent results.

**Solution:** Comprehensive improvements to image generation pipeline

**2.1. Prompt Optimization**
```python
def optimize_prompt_for_gemini(prompt_text: str) -> str:
    # Key features:
    # - Detects text-heavy content (tables, screenshots)
    # - Converts to conceptual illustrations
    # - Adds professional style guidance
    # - Includes quality keywords
```

**2.2. Automatic Retry Logic**
- MAX_RETRIES = 2 (3 total attempts)
- RETRY_DELAY = 3 seconds
- Intelligent fallback prompts
- Handles empty responses gracefully

**2.3. Safety Settings Optimization**
```python
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
]
```

**2.4. Lambda Layer Optimization**
- **Challenge:** Vertex AI SDK (google-cloud-aiplatform) = 250+ MB
- **Solution:** 
  - Optimized layer build (removed 90MB discovery cache)
  - Removed ALL dependencies from function requirements.txt
  - Result: 191 MB layer + 26 KB function = under 250 MB limit

**Layer Configuration:**
```bash
# GeminiLayer v18
Dependencies:
- google-generativeai (Gemini API)
- google-cloud-aiplatform (Vertex AI/Imagen 4.0)
- Pillow (image processing)

Build: ./build-gemini-layer.sh
Size: 43 MB zipped, 191 MB unzipped
```

**Function Configuration:**
```
ImagesGen:
- Code: 26 KB
- Requirements.txt: Empty (all deps in layer)
- Total with layer: ~191 MB
- Memory: 1024 MB
- Timeout: 900 seconds
```

**Results:**
- ✅ **100% success rate** (tested on multiple large courses)
- ✅ ~10% retry usage (1 attempt recovers most failures)
- ✅ 0% safety filter blocks
- ✅ Average 7 seconds per image
- ✅ Vertex AI SDK available for future Imagen 4.0 use

#### 3. Image Mapping Optimization

**Problem:** Step Functions JsonMerge intrinsic function has 40KB payload limit. Large courses with 50+ images exceeded limit.

**Solution:** Optimized image mapping structure

**Before (40+ KB):**
```json
{
  "[VISUAL: 001 - Cloud architecture diagram showing...]": "s3://bucket/path/001.png"
}
```

**After (~10 KB):**
```json
{
  "001": {
    "s3_key": "project/images/001.png",
    "description": "Cloud architecture diagram"
  }
}
```

**Results:**
- ✅ 80% size reduction
- ✅ No JsonMerge errors on large courses
- ✅ Better BookBuilder performance

#### 4. Deployment System Improvements

**Enhanced `deploy-with-dependencies.sh` script:**

**New Features:**
- Prerequisite validation (sam, aws, jq, template.yaml)
- Build error detection and reporting
- Build directory verification
- Dependency detection logging
- Zip size reporting
- Deployment output capture and parsing
- Per-function success/failure tracking
- Comprehensive summary with statistics
- Conditional exit codes

**Example Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEPLOYMENT SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Successfully deployed: 10/10 functions
❌ Failed: 0/10 functions

Functions deployed:
  ✅ StarterApiFunction (16 MiB)
  ✅ StrandsContentGen (16 MiB)
  ✅ ImagesGen (26 KB)
  ...
```

### Performance Metrics (Production)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Image Success Rate | 50% | 100% | +100% |
| Large Course Success | 0% (timeout) | 100% | N/A |
| Average Image Time | 10s | 7s | -30% |
| Deployment Reliability | ~80% | 100% | +25% |
| Step Functions Payload | 40KB+ | <10KB | -75% |

### Test Results

**Test Course 1 (Small):**
- Duration: 8 hours
- Lessons: 10
- Images: 10
- Result: ✅ 100% success, 0 failures
- Execution: arn:aws:states:us-east-1:746434296869:execution:CourseGeneratorStateMachine:course-gen-unknown-user-1761951049

**Test Course 2 (Large):**
- Duration: 40+ hours
- Lessons: 100+
- Images: 50+
- Result: ✅ 100% success, 0 failures
- Time: ~18 minutes
- Retries used: ~5 images needed 1 retry

### Architecture Changes

**New Lambda Functions:**
1. `BatchExpander` - Splits content generation into manageable batches
2. `LabBatchExpander` - Splits lab guide generation into batches
3. `InitializeImageGeneration` - Sets up image generation state

**Updated Lambda Functions:**
1. `ImagesGen` - Complete rewrite with retry logic and prompt optimization
2. `StrandsContentGen` - Batch-aware content generation
3. `StrandsLabPlanner` - Batch-aware lab planning
4. `StrandsLabWriter` - Batch-aware lab writing
5. `BookBuilder` - Optimized image mapping format

**Updated Step Functions:**
- Added `ProcessBatches` Map State
- Added `ProcessImageBatch` Map State
- Added `ProcessLabBatches` Map State
- Added `InitializeImageGeneration` state
- Updated error handling and retry policies

**New Lambda Layer:**
- GeminiLayer v18 with Vertex AI SDK support

### Deployment Configuration

**SAM Template Updates:**
```yaml
ImagesGen:
  Type: AWS::Serverless::Function
  Properties:
    Layers:
      - !Ref GeminiLayer  # v18 with Vertex AI SDK
    MemorySize: 1024
    Timeout: 900
```

**Requirements Changes:**
```
# lambda/images_gen/requirements.txt
# Empty - all dependencies in GeminiLayer
```

### Operational Impact

**Before November 2025:**
- Small courses: 70% success rate
- Large courses: Timeout failures
- Image generation: ~50% success
- Manual fixes required: Frequent
- Deployment: Error-prone

**After November 2025:**
- Small courses: 100% success rate
- Large courses: 100% success rate
- Image generation: 100% success
- Manual fixes required: None
- Deployment: Automated and reliable

### Future Enhancements

**Ready for Implementation:**
1. **Imagen 4.0 Ultra:** Vertex AI SDK deployed, can switch via config
2. **Dynamic Batch Sizing:** Adjust batch size based on content complexity
3. **Parallel Image Generation:** Multiple images per batch
4. **Cost Optimization:** Use cheaper models for simple images

**Under Consideration:**
1. **Container Images:** For future dependencies > 250 MB
2. **S3 Event Triggers:** Real-time image processing
3. **CloudFront CDN:** Faster image delivery
4. **Image Caching:** Reuse similar images across courses

### Lessons Learned

1. **Lambda Limits Are Real:** 250 MB uncompressed code+layers, 900s timeout
2. **Batch Processing Essential:** Large workloads need intelligent splitting
3. **Retry Logic Saves The Day:** 100% → 10% failure with 2 retries
4. **Prompt Engineering Matters:** Better prompts = better AI results
5. **Deployment Automation Critical:** Error tracking prevents silent failures
6. **Step Functions Payload Limits:** Keep intrinsic function data < 40KB
7. **Layer Optimization:** Remove unnecessary files (discovery caches, tests)

### Conclusion

The Aurora V1 course generation system has reached **production maturity** with:
- ✅ 100% success rate for all course sizes
- ✅ Robust error recovery and retry mechanisms
- ✅ Scalable batch processing architecture
- ✅ Comprehensive deployment automation
- ✅ Future-ready with Vertex AI SDK support

**Status:** Production-ready, battle-tested, reliable.

---

## 2025-12-04: Course Generator State Machine - Complete Architecture

### Overview

The **CourseGeneratorStateMachine** is the central orchestration engine for Aurora's course generation system. It handles three distinct content types (theory, labs, both) with intelligent routing, supports both new course generation and selective regeneration of individual lessons/labs.

### State Machine Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CourseGeneratorStateMachine                             │
│                 (AWS Step Functions - Standard Type)                         │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │ DetermineContent │
                              │      Type        │
                              └────────┬─────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
  ┌────────────────┐         ┌────────────────┐         ┌────────────────┐
  │ TheoryOnly     │         │ LabsOnly       │         │ BothTheory     │
  │ Branch         │         │ Branch         │         │ AndLabsBranch  │
  └───────┬────────┘         └───────┬────────┘         └───────┬────────┘
          │                          │                          │
          ▼                          ▼                          ▼
  ┌────────────────┐         ┌────────────────┐         ┌────────────────┐
  │ ExpandModules  │         │ InvokeLab      │         │ GenerateMaster │
  │ ToBatches      │         │ Planner        │         │ LabPlan        │
  └───────┬────────┘         └───────┬────────┘         └───────┬────────┘
          │                          │                          │
          ▼                          ▼                          ▼
  ┌────────────────┐         ┌────────────────┐         ┌────────────────┐
  │ CheckIfRegen   │         │ CheckLabPlan   │         │ CheckMasterLab │
  │ erationMode    │         │ nerResult      │         │ PlanResult     │
  └───────┬────────┘         └───────┬────────┘         └───────┬────────┘
          │                          │                          │
     ┌────┴────┐                     ▼                          ▼
     │         │             ┌────────────────┐         ┌────────────────┐
     ▼         ▼             │ ExpandLabs     │         │ ExpandModules  │
┌─────────┐┌─────────┐       │ ToBatches      │         │ ToBatches      │
│ Prepare ││ Prepare │       └───────┬────────┘         └───────┬────────┘
│ NewCrse ││ Regen   │               │                          │
│ Params  ││ Params  │               ▼                          ▼
└────┬────┘└────┬────┘       ┌────────────────┐         ┌────────────────┐
     │         │             │ ProcessLab     │         │ ProcessBatches │
     └────┬────┘             │ BatchesParallel│         │ InParallel     │ (Theory)
          │                  └───────┬────────┘         └───────┬────────┘
          ▼                          │                          │
  ┌────────────────┐                 ▼                          ▼
  │ ProcessBatches │         ┌────────────────┐         ┌────────────────┐
  │ InParallel     │         │ CombineLab     │         │ ChooseCombine  │
  └───────┬────────┘         │ Results        │         │ ResultsPath    │
          │                  └───────┬────────┘         └───────┬────────┘
          ▼                          │                     ┌────┴────┐
  ┌────────────────┐                 ▼                     ▼         ▼
  │ CombineResults │         ┌────────────────┐   ┌──────────┐┌──────────┐
  │ AndBuildBook   │         │ InvokeLab      │   │ Combine  ││ Combine  │
  └───────┬────────┘         │ GuideBuilder   │   │ Results  ││ Results  │
          │                  └───────┬────────┘   │ (Theory) ││ (Both)   │
          ▼                          │            └────┬─────┘└────┬─────┘
  ┌────────────────┐                 ▼                 │           │
  │ InvokeBook     │         ┌────────────────┐        └─────┬─────┘
  │ Builder        │         │ Notify         │              │
  └───────┬────────┘         │ Completion     │              ▼
          │                  └───────┬────────┘      ┌────────────────┐
          ▼                          │               │ InvokeBook     │
  ┌────────────────┐                 ▼               │ Builder        │
  │ Notify         │         ┌────────────────┐      └───────┬────────┘
  │ Completion     │         │ SuccessState   │              │
  └───────┬────────┘         └────────────────┘              ▼
          │                                          ┌────────────────┐
          ▼                                          │ CheckIfLabs    │
  ┌────────────────┐                                 │ Needed         │
  │ SuccessState   │                                 └───────┬────────┘
  └────────────────┘                                    ┌────┴────┐
                                                        ▼         ▼
                                                 ┌──────────┐┌──────────┐
                                                 │ Validate ││ Notify   │
                                                 │ LabPlan  ││ Complete │
                                                 │ Exists   ││ (theory) │
                                                 └────┬─────┘└──────────┘
                                                      │
                                                      ▼
                                              ┌────────────────┐
                                              │ ExpandLabs     │
                                              │ ToBatchesBoth  │
                                              └───────┬────────┘
                                                      │
                                                      ▼
                                              ┌────────────────┐
                                              │ ProcessLab     │
                                              │ BatchesBoth    │
                                              └───────┬────────┘
                                                      │
                                                      ▼
                                              ┌────────────────┐
                                              │ CombineLab     │
                                              │ ResultsBoth    │
                                              └───────┬────────┘
                                                      │
                                                      ▼
                                              ┌────────────────┐
                                              │ InvokeLab      │
                                              │ GuideBuilder   │
                                              └───────┬────────┘
                                                      │
                                                      ▼
                                              ┌────────────────┐
                                              │ Notify         │
                                              │ Completion     │
                                              └───────┬────────┘
                                                      │
                                                      ▼
                                              ┌────────────────┐
                                              │ SuccessState   │
                                              └────────────────┘
```

### All States Reference

| State Name | Type | Purpose |
|------------|------|---------|
| **DetermineContentType** | Choice | Routes to theory, labs, or both branch |
| **TheoryOnlyBranch** | Pass | Prepares params for theory-only generation |
| **LabsOnlyBranch** | Pass | Prepares params for labs-only generation |
| **BothTheoryAndLabsBranch** | Pass | Prepares params for combined generation |
| **GenerateLabMasterPlan** | Task | Creates master lab plan (StrandsLabPlanner) |
| **CheckMasterLabPlanResult** | Choice | Validates master lab plan success |
| **ExpandModulesToBatches** | Task | Splits modules into batches (BatchExpander) |
| **CheckBatchExpansionSuccess** | Choice | Validates batch expansion result |
| **CheckIfRegenerationMode** | Choice | Detects regeneration vs new course |
| **PrepareNewCourseParams** | Pass | Sets null defaults for new courses |
| **PrepareRegenerationParams** | Pass | Preserves regeneration parameters |
| **ProcessBatchesInParallel** | Map | Parallel execution of content generation |
| **ChooseCombineResultsPath** | Choice | Routes based on content_type |
| **CombineResultsAndBuildBook** | Pass | Flattens results (theory-only) |
| **CombineResultsAndBuildBookBoth** | Pass | Flattens results preserving master_lab_plan |
| **InvokeBookBuilder** | Task | Compiles final book (BookBuilder) |
| **CheckIfLabsNeeded** | Choice | Routes to lab generation for "both" mode |
| **ValidateLabPlanExists** | Choice | Validates master_lab_plan_result exists |
| **InvokeLabPlanner** | Task | Creates lab plan (StrandsLabPlanner) |
| **CheckLabPlannerResult** | Choice | Validates lab planner success |
| **ExpandLabsToBatches** | Task | Splits labs into batches (LabBatchExpander) |
| **ExpandLabsToBatchesBoth** | Task | Splits labs for "both" mode |
| **CheckLabBatchExpansionSuccess** | Choice | Validates lab batch expansion |
| **CheckLabBatchExpansionSuccessBoth** | Choice | Validates lab batch expansion (both) |
| **ProcessLabBatchesInParallel** | Map | Parallel lab generation |
| **ProcessLabBatchesInParallelBoth** | Map | Parallel lab generation (both mode) |
| **CombineLabResults** | Pass | Flattens lab results (labs-only) |
| **CombineLabResultsBoth** | Pass | Flattens lab results (both mode) |
| **InvokeLabGuideBuilder** | Task | Compiles lab guide book |
| **NotifyCompletion** | Task | Sends success notification |
| **NotifyFailure** | Task | Sends failure notification |
| **SuccessState** | Succeed | Marks execution complete |
| **FailWorkflow** | Fail | Marks execution failed |

### Content Type Routing

The state machine supports three content types:

**1. `theory` (Theory Only)**
- Generates lesson content and images
- Skips lab generation entirely
- Fastest execution path

**2. `labs` (Labs Only)**
- Generates lab guides based on outline
- Skips theory content generation
- Used for lab-only regeneration

**3. `both` (Theory + Labs)**
- Full course generation
- First generates all theory content
- Then generates lab guides
- Most comprehensive path

### New Course vs Regeneration Mode

The state machine intelligently handles both new course generation and selective regeneration:

**New Course Generation:**
- `lesson_to_generate = null`
- `lab_ids_to_regenerate = null`
- Generates all modules/lessons in the outline

**Lesson Regeneration:**
- `lesson_to_generate = "MM-LL"` (e.g., "01-02")
- `module_number = N` (specific module)
- Regenerates only the specified lesson

**Lab Regeneration:**
- `lab_ids_to_regenerate = ["07-00-01"]`
- Regenerates only the specified lab(s)

### Key Lambda Functions Invoked

| Lambda | Invoked By | Purpose |
|--------|------------|---------|
| **BatchExpander** | ExpandModulesToBatches | Splits modules into batches of 3 lessons |
| **StrandsContentGen** | ProcessBatchesInParallel | Generates lesson content |
| **StrandsVisualPlanner** | ProcessBatchesInParallel | Plans visual content |
| **ImagesGen** | ProcessBatchesInParallel | Generates images |
| **BookBuilder** | InvokeBookBuilder | Compiles theory book |
| **StrandsLabPlanner** | GenerateLabMasterPlan, InvokeLabPlanner | Creates lab plans |
| **LabBatchExpander** | ExpandLabsToBatches | Splits labs into batches |
| **StrandsLabWriter** | ProcessLabBatchesInParallel | Writes lab content |
| **LabGuideBuilder** | InvokeLabGuideBuilder | Compiles lab guide |
| **NotificationFunction** | NotifyCompletion, NotifyFailure | Sends email notifications |

---

## 2025-12-04: Regenerate Lesson/Lab Feature

### Overview

Aurora now supports **selective regeneration** of individual lessons and labs without regenerating the entire course. This feature significantly reduces time and cost when only specific content needs to be updated.

### Use Cases

1. **Content Improvement**: Regenerate a lesson with additional requirements (e.g., "add more real-world examples")
2. **Error Correction**: Fix issues in a specific lesson without affecting others
3. **Lab Updates**: Regenerate a lab to match updated lesson content
4. **Customization**: Tailor specific sections for different audiences

### Frontend Component: RegenerateLesson

**Location:** `src/components/RegenerateLesson.jsx`

**Purpose:** Provides UI for regenerating individual lessons with optional additional requirements.

**Props:**
```javascript
{
  projectFolder: string,      // Current project folder name
  outlineKey: string,         // S3 key to the outline file
  currentLessonId: string,    // e.g., "01-02" for module 1, lesson 2
  currentLessonTitle: string, // Display title
  moduleNumber: number,       // Module number (1-based)
  lessonNumber: number,       // Lesson number within module
  onClose: function,          // Close modal callback
  onSuccess: function         // Success callback
}
```

**Features:**
- ✅ Displays current lesson info (ID, title, module)
- ✅ Optional text area for additional requirements
- ✅ Spanish UI ("Regenerar Lección", "Requisitos Adicionales")
- ✅ Loading state with spinner
- ✅ Success modal with estimated time
- ✅ Error handling with user-friendly messages

**API Request Format:**
```javascript
{
  course_bucket: 'crewai-course-artifacts',
  outline_s3_key: 'project/outline/course.yaml',
  project_folder: '251202-curso-ejemplo',
  content_type: 'theory',           // Theory only for lessons
  model_provider: 'bedrock',
  image_model: 'models/gemini-2.5-flash-image',
  module_number: 2,                 // Specific module
  lesson_to_generate: '02-01',      // Specific lesson ID
  lesson_requirements: 'Optional additional instructions',
  user_email: 'user@example.com'
}
```

### Backend Changes for Regeneration

#### 1. StarterApiFunction Updates

**File:** `CG-Backend/lambda/starter_api.py`

**Changes:**
- Accepts `module_number` parameter (single module for regeneration)
- Accepts `lesson_to_generate` parameter (specific lesson ID)
- Accepts `lesson_requirements` parameter (additional instructions)
- Accepts `lab_ids_to_regenerate` parameter (specific lab IDs)
- Passes these to state machine for selective processing

**Parameter Handling:**
```python
# For regeneration
module_number = body.get('module_number')          # Single module
lesson_to_generate = body.get('lesson_to_generate')  # Specific lesson
lesson_requirements = body.get('lesson_requirements')  # Additional reqs
lab_ids_to_regenerate = body.get('lab_ids_to_regenerate')  # Specific labs

# For new courses (backwards compatible)
modules_to_generate = body.get('modules_to_generate', 'all')  # All modules
```

#### 2. BatchExpander Updates

**File:** `CG-Backend/lambda/batch_expander.py`

**Changes:**
- Handles `module_number` for single-module regeneration
- Handles `lesson_to_generate` for single-lesson regeneration
- Creates minimal batch for regeneration (1 lesson instead of full batches)

**Batch Logic:**
```python
if lesson_to_generate:
    # Regeneration mode: create single-lesson batch
    batches = [{
        'module_number': module_number,
        'lesson_id': lesson_to_generate,
        'lesson_requirements': lesson_requirements
    }]
else:
    # New course mode: batch all lessons (3 per batch)
    batches = create_batches(modules, MAX_LESSONS_PER_BATCH=3)
```

#### 3. StrandsContentGen Updates

**File:** `CG-Backend/lambda/strands_content_gen/strands_content_gen.py`

**Changes:**
- Passes `lesson_requirements` to AI prompt
- Enhances content based on additional requirements
- Logs regeneration context for debugging

**Prompt Enhancement:**
```python
if lesson_requirements:
    prompt += f"""
    
    ADDITIONAL REQUIREMENTS (PRIORITY):
    {lesson_requirements}
    
    Please ensure the generated content addresses these specific requirements.
    """
```

#### 4. StrandsLabPlanner Updates

**File:** `CG-Backend/lambda/strands_lab_planner/strands_lab_planner.py`

**Changes:**
- Handles `lab_ids_to_regenerate` for selective lab planning
- Filters labs to only those specified
- Enforces outline titles over AI-generated titles

**Title Enforcement (Bug Fix):**
```python
# Post-process to enforce outline titles
outline_lab_titles = extract_lab_titles_from_outline(outline)
for lab_plan in batch_plan.get('lab_plans', []):
    lab_id = lab_plan.get('lab_id')
    if lab_id in outline_lab_titles:
        # Override AI title with outline title
        lab_plan['lab_title'] = outline_lab_titles[lab_id]
```

#### 5. StrandsLabWriter Updates

**File:** `CG-Backend/lambda/strands_lab_writer/strands_lab_writer.py`

**Changes:**
- Added raw markdown fallback for single-lab generation
- Handles cases where AI doesn't use delimiter format
- Improved error recovery

**Raw Markdown Fallback:**
```python
# If delimiter parsing fails for single lab, accept raw markdown
if len(lab_plans) == 1:
    if response_text.strip().startswith('#') or '##' in response_text:
        labs_dict[lab_plans[0]['lab_id']] = response_text.strip()
        logger.info("Using raw markdown fallback for single lab")
```

#### 6. LabGuideBuilder Updates

**File:** `CG-Backend/lambda/lab_guide_builder.py`

**Changes:**
- Auto-deduplicates labs by ID
- Keeps most recent file when duplicates exist
- Logs deduplication decisions

**Deduplication Logic:**
```python
# When multiple files exist for same lab ID, keep most recent
for lab_id, files in labs_by_id.items():
    if len(files) > 1:
        # Sort by modification time, keep newest
        files.sort(key=lambda f: f['LastModified'], reverse=True)
        selected = files[0]
        logger.info(f"Lab ID {lab_id}: using {selected['Key']} (newest)")
```

### State Machine Changes for Regeneration

**Key States Added:**

1. **CheckIfRegenerationMode**: Detects if `lesson_to_generate` is present
2. **PrepareNewCourseParams**: Sets null defaults for new courses
3. **PrepareRegenerationParams**: Preserves regeneration parameters
4. **ChooseCombineResultsPath**: Routes based on content_type to preserve master_lab_plan
5. **CombineResultsAndBuildBookBoth**: Special path for "both" mode that preserves master_lab_plan_result

**Routing Logic:**
```json
"CheckIfRegenerationMode": {
  "Type": "Choice",
  "Choices": [
    {
      "Variable": "$.lesson_to_generate",
      "IsPresent": true,
      "Next": "PrepareRegenerationParams"
    }
  ],
  "Default": "PrepareNewCourseParams"
}
```

### Book Editor Integration

**File:** `src/components/BookEditor.jsx`

**Changes:**
- Added "Regenerar Lección" button in lesson view
- Added "Regenerar Lab" button in lab view
- Added "🔄 Recargar Lecciones" button to refresh from S3
- Added "🔄 Recargar Labs" button for lab guide refresh
- Improved header matching for "Capítulo" titles
- Fixed token overlap to not match lab headers for module search

**Reload Buttons:**
```jsx
<button
    onClick={loadBook}
    title="Recargar lecciones desde S3"
>
    {loadingImages ? '⏳ Recargando...' : '🔄 Recargar Lecciones'}
</button>
```

**Header Matching Fix:**
```javascript
// Added Capítulo support alongside Module/Módulo
const modMatch = title.match(/(?:Module|Módulo|Capitulo|Capítulo)\s+(\d+)/i);

// Prevent token overlap from matching lab headers
if (moduleNum === null && /^lab\s+\d/.test(normH)) {
    return false; // Skip lab headers when searching for modules
}
```

### Usage Flow

**1. Lesson Regeneration:**
```
User clicks "Regenerar Lección" on a lesson
    ↓
RegenerateLesson modal opens
    ↓
User optionally adds requirements
    ↓
User clicks "Regenerar Lección"
    ↓
API call to /start-job with:
  - content_type: 'theory'
  - module_number: N
  - lesson_to_generate: 'MM-LL'
  - lesson_requirements: 'optional text'
    ↓
State Machine:
  - Routes to TheoryOnlyBranch
  - Detects regeneration mode
  - Creates single-lesson batch
  - Generates only specified lesson
  - Updates book
    ↓
User clicks "🔄 Recargar Lecciones"
    ↓
New content appears in editor
```

**2. Lab Regeneration:**
```
User clicks "Regenerar Lab" on a lab
    ↓
Similar flow with:
  - content_type: 'labs'
  - lab_ids_to_regenerate: ['07-00-01']
    ↓
State Machine:
  - Routes to LabsOnlyBranch
  - Filters to specified lab(s)
  - Regenerates only those labs
  - Updates lab guide
    ↓
User clicks "🔄 Recargar Labs"
    ↓
New lab content appears
```

### Performance

| Operation | Time | Cost |
|-----------|------|------|
| Single lesson regeneration | 2-3 minutes | ~$0.15 |
| Single lab regeneration | 3-5 minutes | ~$0.20 |
| Full course (40 lessons) | 15-25 minutes | ~$15-20 |

### Error Handling

**Frontend:**
- Displays error message if API call fails
- Shows loading spinner during regeneration
- Success modal with estimated time

**Backend:**
- State machine catches failures
- Routes to NotifyFailure on error
- Sends failure notification email

**Common Errors:**
- "No se pudo determinar el número de módulo" - Missing moduleNumber prop
- "Invalid outline format" - Malformed YAML in outline
- Lambda timeout - Very complex lesson (rare)

---
