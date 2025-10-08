# ERRORS.md

## State Machine Workflow

### Errors Detected

#### 1. Null Bucket Parameter Error
**Error**: `TypeError: expected string or bytes-like object, got 'NoneType'`
**Location**: `strands_content_gen.py`, line 676 - `s3_client.put_object(Bucket=course_bucket, ...)`
**Cause**: The `course_bucket` parameter was `null` in the Step Functions execution input, causing the S3 operation to fail with a boto3 validation error.
**Impact**: Step Functions execution failed during the content generation phase, preventing course creation.

#### 2. Missing Course Outline File
**Error**: File not found errors when trying to load `outline.yaml`
**Location**: Course generation initialization in `strands_content_gen.py`
**Cause**: The lambda function expected an `outline.yaml` file to be present in the deployment package, but it was missing.
**Impact**: Lambda function crashed during initialization, causing Step Functions task failure.

#### 3. Lambda Layer Dependency Import Errors
**Error**: `Runtime.ImportModuleError` for multiple packages
**Affected Packages**:
- `opentelemetry`
- `typing_extensions`
- `importlib_metadata`
- `pydantic`
- `pydantic_core`
**Cause**: Lambda layer was missing transitive dependencies required by Strands Agents.
**Impact**: Lambda function failed to start, causing Step Functions execution to fail immediately.

#### 5. Lambda Package Structure Error
**Error**: `Runtime.ImportModuleError: Unable to import module 'strands_content_gen': No module named 'strands_content_gen'`
**Location**: Lambda function initialization
**Cause**: The Lambda deployment package had incorrect directory structure. Files were nested in `lambda/strands_content_gen/` instead of being at the root level of the zip file. Lambda expects the handler file (`strands_content_gen.py`) to be at the root of the deployment package.
**Impact**: Lambda function failed to start, causing Step Functions execution to fail immediately with import errors.
**Resolution**: Repackage the Lambda function with files at the root level:
```bash
cd lambda/strands_content_gen && zip -r ../../strands_content_gen_fixed.zip .
```

#### 6. OpenAI Model Provider Fallback Configuration
**Error**: OpenAI requests automatically falling back to Bedrock when organization verification failed
**Location**: `strands_content_gen.py` and `starter_api.py` - model provider configuration
**Cause**: The system was configured to automatically fallback from OpenAI to Bedrock when OpenAI streaming failed due to organization verification requirements. User preference was for OpenAI GPT-5 to work exclusively or fail cleanly without fallback.
**Impact**: OpenAI requests would succeed with Bedrock instead of using GPT-5, potentially not meeting user requirements for specific model usage.
**Resolution**: Modified fallback logic to disable automatic fallback for OpenAI by default:
```python
# In strands_content_gen.py
allow_openai_fallback = event.get('allow_openai_fallback', model_provider != 'openai')

# In starter_api.py  
allow_openai_fallback = body.get('allow_openai_fallback', model_provider != 'openai')
```

#### 7. S3 Access Denied During Testing
**Error**: `ClientError: An error occurred (AccessDenied) when calling the PutObject operation: Access Denied`
**Location**: S3 put_object operation during content saving
**Cause**: Test requests used invalid bucket names ("test-bucket") that either don't exist or the Lambda function lacks write permissions to. Production requests use proper bucket names with correct IAM permissions.
**Impact**: Test executions failed during the final S3 storage step, but production functionality remained intact.
**Resolution**: Use proper bucket names and ensure IAM permissions are correctly configured for Lambda functions.

### Recommendations to Avoid Errors

#### 1. Parameter Validation and Defaults
**Recommendation**: Implement robust parameter validation and default values in all lambda functions.

```python
# In starter_api.py and lambda handlers
course_bucket = event.get('course_bucket', 'crewai-course-artifacts')  # Always provide default
project_folder = event.get('project_folder')  # Validate if required

# Add parameter validation
if not course_bucket:
    raise ValueError("course_bucket is required")
```

**Benefits**:
- Prevents null parameter errors
- Ensures consistent behavior
- Provides clear error messages

#### 2. Comprehensive Testing Strategy
**Recommendation**: Implement multi-level testing before deployment.

```python
# Unit tests for parameter handling
def test_bucket_parameter_handling():
    # Test with null bucket
    # Test with valid bucket
    # Test with invalid bucket

# Integration tests for Step Functions
def test_state_machine_execution():
    # Test complete workflow
    # Test individual lambda functions
    # Test error scenarios
```

**Testing Levels**:
- **Unit Tests**: Individual function testing
- **Integration Tests**: Lambda function testing with AWS services
- **End-to-End Tests**: Complete Step Functions workflow testing
- **Load Tests**: Performance testing under load

#### 3. Dependency Management Best Practices
**Recommendation**: Use comprehensive dependency management for lambda layers.

```bash
# In build scripts, use --no-deps false to include all transitive dependencies
pip install --no-deps false -r requirements-strands.txt -t python/

# Validate all imports during build
python -c "import strands; import pydantic; import opentelemetry" || exit 1
```

**Dependency Management**:
- Always include transitive dependencies
- Test imports during build process
- Use pinned versions for stability
- Maintain separate requirements files for different components

#### 4. File and Resource Packaging
**Recommendation**: Ensure all required files are properly included in lambda packages.

```python
# In lambda deployment
# Verify required files exist
required_files = ['outline.yaml', 'config.json']
for file in required_files:
    if not os.path.exists(file):
        raise FileNotFoundError(f"Required file {file} not found")

# Use absolute paths for file operations
yaml_path = os.path.join(os.getcwd(), 'outline.yaml')
if not os.path.exists(yaml_path):
    yaml_path = '/var/task/outline.yaml'  # Lambda environment path
```

**File Management**:
- Include all required files in deployment packages
- Use environment-agnostic file paths
- Validate file existence during initialization
- Document all required files in README

#### 5. Error Handling and Monitoring
**Recommendation**: Implement comprehensive error handling and monitoring.

```python
# In lambda handlers
try:
    # Main logic
    result = process_request(event)
    return result
except Exception as e:
    # Log detailed error information
    logger.error(f"Error processing request: {str(e)}", exc_info=True)

    # Return structured error response
    return {
        "statusCode": 500,
        "error": str(e),
        "error_type": type(e).__name__,
        "timestamp": datetime.now().isoformat()
    }
```

**Monitoring Improvements**:
- Implement CloudWatch alarms for Step Functions failures
- Add detailed logging for debugging
- Use structured error responses
- Implement retry logic for transient failures

#### 6. Configuration Management
**Recommendation**: Centralize configuration and use environment variables.

```python
# Use environment variables for configuration
DEFAULT_BUCKET = os.getenv('DEFAULT_COURSE_BUCKET', 'crewai-course-artifacts')
MAX_EXECUTION_TIME = int(os.getenv('MAX_EXECUTION_TIME', '900'))

# Validate configuration on startup
def validate_configuration():
    required_env_vars = ['DEFAULT_COURSE_BUCKET', 'STATE_MACHINE_ARN']
    for var in required_env_vars:
        if not os.getenv(var):
            raise ValueError(f"Required environment variable {var} not set")
```

**Configuration Best Practices**:
- Use environment variables for environment-specific settings
- Validate configuration on startup
- Document all required configuration
- Use sensible defaults where possible

#### 7. Deployment Automation
**Recommendation**: Automate deployment with validation checks.

```bash
# In deployment scripts
#!/bin/bash

# Build and validate lambda layer
echo "Building lambda layer..."
pip install -r requirements-strands.txt -t python/
python -c "import strands, pydantic, opentelemetry" || exit 1

# Package lambda functions
echo "Packaging lambda functions..."
zip -r strands_content_gen.zip . -x "*.git*"

# Deploy to AWS
echo "Deploying to AWS..."
aws lambda update-function-code --function-name StrandsContentGen --zip-file fileb://strands_content_gen.zip

# Run integration tests
echo "Running integration tests..."
npm test
```

**Deployment Automation**:
- Automate build and deployment processes
- Include validation steps in deployment pipeline
- Run tests before and after deployment
- Use infrastructure as code (CloudFormation/SAM)

#### 9. Lambda Package Structure Best Practices
**Recommendation**: Ensure correct Lambda deployment package structure for reliable imports.

```bash
# Correct packaging - files at root level
cd lambda/function_name
zip -r ../../function_name.zip .

# Verify structure
unzip -l function_name.zip
# Should show: function_name.py (at root), not lambda/function_name/function_name.py

# Incorrect packaging (causes import errors)
zip -r function_name.zip lambda/function_name/
# Results in: lambda/function_name/function_name.py (nested, won't import)
```

**Lambda Packaging Rules**:
- Handler file must be at root of zip
- Use relative paths when zipping from function directory
- Include all required files (outline.yaml, config files, etc.)
- Exclude unnecessary files (.git, __pycache__, etc.)
- Test imports after packaging

#### 10. Model Provider Configuration Management
**Recommendation**: Implement clear model provider selection with appropriate fallback policies.

```python
# Model provider configuration with explicit fallback control
model_provider = event.get('model_provider', 'bedrock').lower()
allow_fallback = event.get('allow_openai_fallback', model_provider != 'openai')

# Document model-specific requirements
MODEL_REQUIREMENTS = {
    'openai': {
        'requirements': ['Organization verification', 'API key', 'Project ID'],
        'fallback_policy': 'fail_cleanly',  # No automatic fallback
        'streaming_required': True
    },
    'bedrock': {
        'requirements': ['IAM permissions', 'Model access'],
        'fallback_policy': 'none_needed',
        'streaming_required': False
    }
}

# Validate model provider configuration
if model_provider not in MODEL_REQUIREMENTS:
    raise ValueError(f"Unsupported model provider: {model_provider}")
```

**Model Provider Best Practices**:
- Clearly document model-specific requirements and limitations
- Allow explicit fallback control per provider
- Validate model availability before processing
- Provide clear error messages for configuration issues
- Test each model provider independently

### Error Prevention Checklist

- [ ] Validate all parameters have defaults or are properly validated
- [ ] Include all required files in lambda packages
- [ ] Test all imports during build process
- [ ] Run integration tests for complete workflows
- [ ] Implement comprehensive error handling
- [ ] Set up monitoring and alerting
- [ ] Document all known error scenarios
- [ ] Maintain deployment automation with validation
- [ ] Ensure correct Lambda package structure (files at root level)
- [ ] Configure model provider fallback policies appropriately
- [ ] Test with proper AWS resources (buckets, permissions) in production

### Monitoring and Alerting Setup

**CloudWatch Alarms**:
- Step Functions execution failures
- Lambda function errors
- S3 operation failures
- High execution times

**Log Analysis**:
- Search for common error patterns
- Monitor error rates by function
- Track performance metrics
- Alert on unusual patterns

This comprehensive error documentation and prevention strategy will significantly reduce future incidents and improve system reliability.

### Recent Fixes and Updates

**October 8, 2025 - Lambda Import and Model Provider Issues**
- **Fixed**: Lambda package structure error causing `Runtime.ImportModuleError`
- **Fixed**: OpenAI automatic fallback behavior - now fails cleanly for GPT-5 by default
- **Resolved**: S3 access issues during testing (were due to incorrect test bucket names)
- **Verified**: System now works correctly with both Bedrock and OpenAI (when properly configured)
- **Added**: Best practices for Lambda packaging and model provider configuration