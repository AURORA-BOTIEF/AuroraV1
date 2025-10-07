#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for the new IAM-authorized Course Generator API functions.
This tests the starter_api and exec_status functions.
"""

import json
import os
import sys
import time
import datetime
from unittest.mock import Mock, patch

# Add the lambda directory to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda'))

def test_starter_api():
    """Test the starter API function"""
    print("=== Testing Starter API ===")

    # Mock event for testing
    mock_event = {
        "body": json.dumps({
            "course_topic": "Test Kubernetes Course",
            "course_duration_hours": 20,
            "module_to_generate": 1,
            "performance_mode": "fast",
            "model_provider": "bedrock",
            "max_images": 2
        }),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123",
                    "email": "test@example.com"
                }
            }
        }
    }

    # Mock context
    mock_context = Mock()
    mock_context.aws_request_id = "test-request-123"

    # Mock environment
    with patch.dict(os.environ, {
        'STATE_MACHINE_ARN': 'arn:aws:states:us-east-1:123456789012:stateMachine:TestStateMachine'
    }):
        # Mock boto3 Step Functions
        with patch('boto3.client') as mock_boto3:
            mock_sf = Mock()
            mock_boto3.return_value = mock_sf
            mock_sf.start_execution.return_value = {
                'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:TestStateMachine:test-execution-123'
            }

            # Import and test the function
            from starter_api import lambda_handler

            result = lambda_handler(mock_event, mock_context)

            # Verify the result
            assert result['statusCode'] == 200
            response_body = json.loads(result['body'])
            assert 'execution_arn' in response_body
            assert response_body['course_topic'] == 'Test Kubernetes Course'
            assert response_body['status'] == 'running'

            # Verify Step Functions was called correctly
            mock_sf.start_execution.assert_called_once()
            call_args = mock_sf.start_execution.call_args
            execution_input = json.loads(call_args[1]['input'])
            assert execution_input['course_topic'] == 'Test Kubernetes Course'
            assert execution_input['performance_mode'] == 'fast'

            print("✅ Starter API test passed")

def test_exec_status_api():
    """Test the execution status API function"""
    print("=== Testing Execution Status API ===")

    execution_arn = 'arn:aws:states:us-east-1:123456789012:execution:TestStateMachine:test-execution-123'

    # Mock event for testing
    mock_event = {
        "pathParameters": {
            "executionArn": execution_arn
        },
        "queryStringParameters": {
            "include_history": "true"
        },
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123",
                    "email": "test@example.com"
                }
            }
        }
    }

    # Mock context
    mock_context = Mock()
    mock_context.aws_request_id = "test-request-456"

    # Mock boto3 Step Functions
    with patch('boto3.client') as mock_boto3:
        mock_sf = Mock()
        mock_boto3.return_value = mock_sf

        # Mock successful execution
        mock_sf.describe_execution.return_value = {
            'executionArn': execution_arn,
            'status': 'SUCCEEDED',
            'startDate': datetime.datetime.now(),
            'stopDate': datetime.datetime.now(),
            'input': json.dumps({
                'course_topic': 'Test Course',
                'module_to_generate': 1
            }),
            'output': json.dumps({
                'content_statistics': {'total_words': 1500},
                'generated_lessons': [{'lesson_title': 'Test Lesson'}],
                'project_folder': 'test-project'
            })
        }

        mock_sf.get_execution_history.return_value = {
            'events': [
                {
                    'timestamp': datetime.datetime.now(),
                    'type': 'ExecutionStarted',
                    'executionStartedEventDetails': {'input': '{}'}
                }
            ]
        }

        # Import and test the function
        from exec_status import lambda_handler

        result = lambda_handler(mock_event, mock_context)

        # Verify the result
        assert result['statusCode'] == 200
        response_body = json.loads(result['body'])
        assert response_body['status'] == 'SUCCEEDED'
        assert response_body['execution_arn'] == execution_arn
        assert response_body['result']['content_statistics']['total_words'] == 1500
        assert len(response_body['execution_history']) == 1

        print("✅ Execution Status API test passed")

def test_error_handling():
    """Test error handling in the APIs"""
    print("=== Testing Error Handling ===")

    # Test starter API with missing course_topic
    mock_event = {
        "body": json.dumps({
            "course_duration_hours": 20
        }),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "test-user-123",
                    "email": "test@example.com"
                }
            }
        }
    }

    from starter_api import lambda_handler

    result = lambda_handler(mock_event, Mock())
    assert result['statusCode'] == 400
    response_body = json.loads(result['body'])
    assert 'course_topic is required' in response_body['error']

    print("✅ Error handling test passed")

if __name__ == '__main__':
    print("Testing Course Generator API Functions")
    print("=" * 50)

    try:
        test_starter_api()
        test_exec_status_api()
        test_error_handling()

        print("=" * 50)
        print("🎉 All tests passed! The API functions are working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)