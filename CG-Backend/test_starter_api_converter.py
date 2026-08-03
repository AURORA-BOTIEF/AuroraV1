import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure the lambda directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lambda'))

import starter_api


def test_extract_text_from_pdf():
    # Mock pypdf.PdfReader
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page 1 Content"
    
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page, mock_page]
    
    with patch('pypdf.PdfReader', return_value=mock_reader):
        text = starter_api.extract_text_from_pdf(b"fake pdf bytes")
        assert text == "Page 1 Content\nPage 1 Content"
        mock_page.extract_text.assert_called()


@patch('starter_api.call_bedrock_ai')
def test_convert_non_yaml_to_yaml(mock_call_bedrock):
    mock_call_bedrock.return_value = """
```yaml
course:
  title: "Docker Course"
  description: "A course about Docker"
  language: "en"
  level: "beginner"
  modules:
    - title: "Introduction"
      lessons: []
```
"""
    yaml_str = starter_api.convert_non_yaml_to_yaml("Some raw course description text", "outline.txt")
    assert "course:" in yaml_str
    assert "Docker Course" in yaml_str
    mock_call_bedrock.assert_called_once()


@patch('starter_api.normalize_outline_yaml')
@patch('starter_api.convert_non_yaml_to_yaml')
@patch('starter_api.extract_text_from_pdf')
def test_process_and_normalize_outline_s3_pdf(mock_extract_pdf, mock_convert, mock_normalize):
    mock_s3 = MagicMock()
    # Mock s3 get_object response
    mock_response = {
        'Body': MagicMock(read=MagicMock(return_value=b"pdf binary data"))
    }
    mock_s3.get_object.return_value = mock_response
    
    mock_extract_pdf.return_value = "Extracted Text from PDF"
    mock_convert.return_value = """
course:
  title: "Test Course"
  modules: []
"""
    
    new_key = starter_api.process_and_normalize_outline_s3(mock_s3, "my-bucket", "folder/course.pdf")
    
    assert new_key == "folder/course.yaml"
    mock_s3.get_object.assert_called_with(Bucket="my-bucket", Key="folder/course.pdf")
    mock_extract_pdf.assert_called_with(b"pdf binary data")
    mock_convert.assert_called_with("Extracted Text from PDF", "course.pdf")
    mock_s3.put_object.assert_called_once()
    mock_normalize.assert_called_with(mock_s3, "my-bucket", "folder/course.yaml")


@patch('starter_api.normalize_outline_yaml')
def test_process_and_normalize_outline_s3_yaml_direct(mock_normalize):
    mock_s3 = MagicMock()
    new_key = starter_api.process_and_normalize_outline_s3(mock_s3, "my-bucket", "folder/course.yaml")
    
    assert new_key == "folder/course.yaml"
    mock_normalize.assert_called_once_with(mock_s3, "my-bucket", "folder/course.yaml")
    mock_s3.get_object.assert_not_called()


@patch('starter_api.extract_text_from_pdf')
def test_process_manual_pdfs(mock_extract_pdf):
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=b"fake manual pdf content"))
    }
    mock_extract_pdf.return_value = "Manual PDF Text Content"
    
    manual_text_key, combined_text = starter_api.process_manual_pdfs(
        mock_s3, "my-bucket", ["folder/manuals/manual1.pdf"], "test-project"
    )
    
    assert manual_text_key == "test-project/manuals/extracted_manual_text.txt"
    assert "=== MANUAL: manual1.pdf ===" in combined_text
    assert "Manual PDF Text Content" in combined_text
    mock_s3.put_object.assert_called_once()

