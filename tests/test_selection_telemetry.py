"""
Tests for selection_telemetry module
"""
import os
import sys
import csv
import tempfile
import pytest

# Add the generator directory to path
CG_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CG-Backend', 'lambda', 'strands_ppt_generator'))
if CG_BACKEND not in sys.path:
    sys.path.insert(0, CG_BACKEND)

from selection_telemetry import SelectionTelemetry


def test_telemetry_disabled_by_default():
    """Telemetry should be disabled when no log path is provided."""
    telemetry = SelectionTelemetry(log_path=None)
    assert not telemetry.is_enabled()
    
    # Logging should be no-op
    telemetry.log_selection(
        lesson_id='01-01',
        requested_text='test',
        image_index=0,
        tfidf_score=0.5,
        legacy_score=0.5,
        combined_score=0.5,
        selected=True
    )
    # No error should occur
    telemetry.close()


def test_telemetry_creates_new_file():
    """Telemetry should create a new CSV file with headers."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        temp_path = f.name
    
    try:
        # Remove the file so telemetry creates it
        os.unlink(temp_path)
        
        telemetry = SelectionTelemetry(log_path=temp_path, append=False)
        assert telemetry.is_enabled()
        
        # Log a sample entry
        telemetry.log_selection(
            timestamp='2025-10-30T12:00:00Z',
            lesson_id='01-01',
            requested_text='Network diagram',
            image_index=2,
            tfidf_score=0.75,
            legacy_score=0.60,
            combined_score=0.69,
            selected=True
        )
        
        telemetry.close()
        
        # Verify file contents
        with open(temp_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]['lesson_id'] == '01-01'
        assert rows[0]['requested_text'] == 'Network diagram'
        assert rows[0]['image_index'] == '2'
        assert float(rows[0]['tfidf_score']) == 0.75
        assert float(rows[0]['legacy_score']) == 0.60
        assert float(rows[0]['combined_score']) == 0.69
        assert rows[0]['selected'] == '1'
    
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_telemetry_append_mode():
    """Telemetry should append to existing file when append=True."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        temp_path = f.name
    
    try:
        os.unlink(temp_path)
        
        # First session: create file and log one entry
        telemetry1 = SelectionTelemetry(log_path=temp_path, append=False)
        telemetry1.log_selection(
            lesson_id='01-01',
            requested_text='First entry',
            image_index=1,
            tfidf_score=0.5,
            legacy_score=0.5,
            combined_score=0.5,
            selected=True
        )
        telemetry1.close()
        
        # Second session: append another entry
        telemetry2 = SelectionTelemetry(log_path=temp_path, append=True)
        telemetry2.log_selection(
            lesson_id='01-02',
            requested_text='Second entry',
            image_index=2,
            tfidf_score=0.6,
            legacy_score=0.6,
            combined_score=0.6,
            selected=False
        )
        telemetry2.close()
        
        # Verify both entries exist
        with open(temp_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 2
        assert rows[0]['requested_text'] == 'First entry'
        assert rows[1]['requested_text'] == 'Second entry'
    
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_telemetry_log_candidates():
    """Telemetry should log multiple candidates with one marked as selected."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        temp_path = f.name
    
    try:
        os.unlink(temp_path)
        
        telemetry = SelectionTelemetry(log_path=temp_path)
        
        candidates = [
            {'image_index': 0, 'tfidf_score': 0.3, 'legacy_score': 0.4, 'combined_score': 0.34},
            {'image_index': 1, 'tfidf_score': 0.7, 'legacy_score': 0.6, 'combined_score': 0.66},  # selected
            {'image_index': 2, 'tfidf_score': 0.5, 'legacy_score': 0.5, 'combined_score': 0.50},
        ]
        
        telemetry.log_candidates(
            timestamp='2025-10-30T12:00:00Z',
            lesson_id='02-03',
            requested_text='Cloud architecture',
            candidates=candidates,
            selected_index=1
        )
        
        telemetry.close()
        
        # Verify all candidates were logged
        with open(temp_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 3
        
        # Check that only index 1 is marked as selected
        assert rows[0]['selected'] == '0'
        assert rows[1]['selected'] == '1'  # selected
        assert rows[2]['selected'] == '0'
        
        # Verify all have same lesson_id and requested_text
        for row in rows:
            assert row['lesson_id'] == '02-03'
            assert row['requested_text'] == 'Cloud architecture'
    
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_telemetry_context_manager():
    """Telemetry should work as a context manager."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        temp_path = f.name
    
    try:
        os.unlink(temp_path)
        
        with SelectionTelemetry(log_path=temp_path) as telemetry:
            assert telemetry.is_enabled()
            telemetry.log_selection(
                lesson_id='03-01',
                requested_text='Test context manager',
                image_index=0,
                selected=True
            )
        
        # File should be closed and contain the entry
        with open(temp_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]['lesson_id'] == '03-01'
    
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_telemetry_truncates_long_text():
    """Telemetry should truncate very long requested_text."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        temp_path = f.name
    
    try:
        os.unlink(temp_path)
        
        long_text = 'A' * 200  # 200 characters
        
        with SelectionTelemetry(log_path=temp_path) as telemetry:
            telemetry.log_selection(
                lesson_id='04-01',
                requested_text=long_text,
                image_index=0,
                selected=True
            )
        
        # Verify text was truncated to 100 chars
        with open(temp_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows[0]['requested_text']) == 100
    
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
