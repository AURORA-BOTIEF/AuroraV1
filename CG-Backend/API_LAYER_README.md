# Course Generator API Layer

This document describes the new IAM-authorized API layer for the Aurora Course Generator system.

## Overview

The Course Generator now uses IAM authorization instead of presigned URLs, providing better security and integration with AWS Cognito authenticated users.

## API Endpoints

### 1. Start Course Generation
**Endpoint:** `POST /start-job`

Starts a new course generation execution via AWS Step Functions.

**Request Body:**
```json
{
  "course_topic": "Kubernetes for DevOps Engineers",
  "course_duration_hours": 40,
  "module_to_generate": 1,
  "performance_mode": "balanced",
  "model_provider": "bedrock",
  "max_images": 4
}
```

**Response:**
```json
{
  "execution_arn": "arn:aws:states:region:account:execution:stateMachine:executionName",
  "execution_name": "course-gen-userId-timestamp",
  "course_topic": "Kubernetes for DevOps Engineers",
  "module_to_generate": 1,
  "user_email": "user@example.com",
  "status": "running"
}
```

### 2. Check Execution Status
**Endpoint:** `GET /exec-status/{executionArn}`

Retrieves the current status of a course generation execution.

**Query Parameters:**
- `include_history` (optional): Include execution history events

**Response:**
```json
{
  "execution_arn": "arn:aws:states:region:account:execution:stateMachine:executionName",
  "status": "SUCCEEDED|FAILED|RUNNING|PENDING|TIMED_OUT|ABORTED",
  "start_date": "2025-01-03T10:30:00Z",
  "stop_date": "2025-01-03T11:15:00Z",
  "user_email": "user@example.com",
  "course_topic": "Kubernetes for DevOps Engineers",
  "module_to_generate": 1,
  "result": {
    "content_statistics": {
      "total_words": 2500,
      "average_words_per_lesson": 833,
      "lessons_generated": 3
    },
    "generated_lessons": [
      {
        "lesson_title": "Introduction to Kubernetes",
        "word_count": 800,
        "lesson_bloom_level": "Understand"
      }
    ],
    "project_folder": "250103-kubernetes-for-devops-engineers-01",
    "bucket": "crewai-course-artifacts"
  },
  "execution_history": [...]
}
```

## Authentication

Both endpoints require IAM authorization through AWS Cognito. The API automatically extracts user information from the JWT token claims.

## Deployment

### Prerequisites

1. **AWS SAM CLI** installed
2. **AWS Credentials** configured
3. **Cognito User Pool** with IAM roles configured

### Environment Variables

Set the following environment variables before deployment:

```bash
export AWS_DEFAULT_REGION=us-east-1
export AWS_PROFILE=your-profile
```

### Deploy with SAM

```bash
cd CG-Backend

# Build the application
sam build

# Deploy to AWS
sam deploy --guided
```

During deployment, you'll be prompted for:
- Stack name (default: `crewai-course-generator-stack`)
- AWS Region
- ECR Repository name
- Google API Key (for image generation)

### Update Frontend Configuration

After deployment, update your frontend environment variables:

```bash
# In your .env file
VITE_COURSE_GENERATOR_API_URL=https://your-api-id.execute-api.us-east-1.amazonaws.com/Prod
```

## Architecture

### Step Functions Workflow

The course generation follows this orchestrated workflow:

1. **Content Generation** (`CrewaiContentGen`)
   - Generates lesson content using CrewAI agents
   - Supports multiple AI providers (Bedrock Claude, OpenAI GPT)
   - Performance modes: fast, balanced, maximum_quality

2. **Visual Planning** (`CrewaiVisualPlanner`)
   - Analyzes content for visual aid opportunities
   - Classifies visuals as "diagram" or "artistic_image"
   - Creates structured prompt files

3. **Image Generation** (`CrewaiImagesGen`)
   - Uses Google Gemini to generate images from prompts
   - Saves images to S3 with organized folder structure

### S3 Organization

Generated content is organized in S3 as follows:

```
crewai-course-artifacts/
├── {project_folder}/                    # YYMMDD-course-topic-XX
│   ├── lessons/
│   │   ├── 01-01-lesson-title-bedrock.md
│   │   └── 01-02-lesson-title-bedrock.md
│   ├── prompts/
│   │   ├── 01-01-0001-visual-description.json
│   │   └── 01-02-0002-visual-description.json
│   └── images/
│       ├── 01-01-0001-visual-description.png
│       └── 01-02-0002-visual-description.png
```

## Usage in Frontend

### Amplify Configuration

Add to your `amplify.js`:

```javascript
Amplify.configure({
  // ... existing Auth config ...
  API: {
    endpoints: [
      {
        name: "CourseGeneratorAPI",
        endpoint: import.meta.env.VITE_COURSE_GENERATOR_API_URL,
        region: "us-east-1"
      }
    ]
  }
});
```

### API Calls

```javascript
import { API } from 'aws-amplify';

// Start course generation
const startResponse = await API.post('CourseGeneratorAPI', '/start-job', {
  body: {
    course_topic: "Kubernetes Course",
    course_duration_hours: 40,
    module_to_generate: 1,
    performance_mode: "balanced",
    model_provider: "bedrock",
    max_images: 4
  }
});

// Check execution status
const statusResponse = await API.get('CourseGeneratorAPI', `/exec-status/${executionArn}`);
```

## Monitoring

### CloudWatch Logs

All Lambda functions log to CloudWatch. Key log groups:
- `/aws/lambda/crewai-course-generator-stack-StarterApiFunction-*`
- `/aws/lambda/crewai-course-generator-stack-ExecStatusFunction-*`

### Step Functions Monitoring

Monitor executions in the Step Functions console:
- View execution status and timeline
- Debug failed executions
- Review input/output data

## Troubleshooting

### Common Issues

1. **Access Denied**
   - Verify Cognito user has proper IAM permissions
   - Check API Gateway IAM authorization

2. **Execution Timeout**
   - Course generation can take 10-30 minutes
   - Increase Lambda timeout if needed

3. **S3 Access Issues**
   - Verify S3 bucket permissions
   - Check bucket exists and is accessible

### Testing

Run the test script to verify API functions:

```bash
cd CG-Backend
python3 test_api_functions.py
```

## Security

- **IAM Authorization**: All API calls require valid AWS credentials
- **Cognito Integration**: User identity verified through JWT tokens
- **Resource-Level Permissions**: Step Functions restricted to user's executions
- **No Presigned URLs**: Direct IAM-based access eliminates token management

## Cost Optimization

- **Lambda Memory**: Configured for 2048MB to handle AI workloads
- **Step Functions**: Standard workflow (not Express) for cost efficiency
- **S3 Storage**: Lifecycle policies recommended for temporary artifacts

## Future Enhancements

- **Real-time Progress**: WebSocket support for live updates
- **Batch Processing**: Generate multiple modules simultaneously
- **Custom Models**: Support for fine-tuned AI models
- **Content Validation**: Automated quality checks on generated content