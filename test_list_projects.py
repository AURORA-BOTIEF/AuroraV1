import sys
import os
import json
from unittest.mock import MagicMock

# Mock boto3
sys.modules['boto3'] = MagicMock()

# Import the lambda handler
sys.path.append('/home/juan/AuroraV1/CG-Backend/lambda')
from list_projects import lambda_handler

def test_list_projects():
    # Mock S3 client and response
    mock_s3 = MagicMock()
    sys.modules['boto3'].client.return_value = mock_s3
    
    # Mock list_objects_v2 response with various folders
    mock_s3.list_objects_v2.return_value = {
        'CommonPrefixes': [
            {'Prefix': 'project-1/'},
            {'Prefix': 'project-2/'},
            {'Prefix': 'PPT_Templates/'}, # Should be excluded
            {'Prefix': 'logo/'},          # Should be excluded
            {'Prefix': 'uploads/'},       # Should be excluded
            {'Prefix': 'images/'},        # Should be excluded
            {'Prefix': 'book/'},          # Should be excluded
            {'Prefix': '.hidden/'},       # Should be excluded
            {'Prefix': 'project-3/'}
        ]
    }
    
    # Mock get_object for metadata (return different dates)
    def get_object_side_effect(**kwargs):
        key = kwargs.get('Key')
        if 'project-1' in key:
            return {'Body': MagicMock(read=lambda: json.dumps({'created': '2023-01-01'}).encode('utf-8'))}
        elif 'project-2' in key:
            return {'Body': MagicMock(read=lambda: json.dumps({'created': '2023-01-03'}).encode('utf-8'))} # Newest
        elif 'project-3' in key:
            return {'Body': MagicMock(read=lambda: json.dumps({'created': '2023-01-02'}).encode('utf-8'))}
        raise Exception("Not found")
        
    mock_s3.get_object.side_effect = get_object_side_effect
    
    # Test Case 1: Default pagination (page 1, limit 10)
    print("\n--- Test Case 1: Default pagination ---")
    event = {}
    response = lambda_handler(event, None)
    body = json.loads(response['body'])
    
    print(f"Total count: {body['total_count']}")
    print(f"Projects returned: {len(body['projects'])}")
    print(f"Excluded folders filtered: {'PPT_Templates' not in [p['folder'] for p in body['projects']]}")
    
    # Verify sorting (project-2 should be first)
    print(f"First project: {body['projects'][0]['folder']} (Expected: project-2)")
    print(f"Second project: {body['projects'][1]['folder']} (Expected: project-3)")
    print(f"Third project: {body['projects'][2]['folder']} (Expected: project-1)")
    
    # Test Case 2: Pagination (page 1, limit 1)
    print("\n--- Test Case 2: Pagination (page 1, limit 1) ---")
    event = {'queryStringParameters': {'page': '1', 'limit': '1'}}
    response = lambda_handler(event, None)
    body = json.loads(response['body'])
    
    print(f"Page: {body['page']}")
    print(f"Limit: {body['limit']}")
    print(f"Total pages: {body['total_pages']}")
    print(f"Projects returned: {len(body['projects'])}")
    print(f"Project: {body['projects'][0]['folder']}")
    
    # Test Case 3: Pagination (page 2, limit 1)
    print("\n--- Test Case 3: Pagination (page 2, limit 1) ---")
    event = {'queryStringParameters': {'page': '2', 'limit': '1'}}
    response = lambda_handler(event, None)
    body = json.loads(response['body'])
    
    print(f"Page: {body['page']}")
    print(f"Projects returned: {len(body['projects'])}")
    print(f"Project: {body['projects'][0]['folder']}")

if __name__ == "__main__":
    test_list_projects()
