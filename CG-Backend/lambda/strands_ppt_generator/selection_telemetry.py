"""
Image Selection Telemetry Module
=================================
Opt-in CSV logging for image selection decisions to enable data-driven weight tuning.

Environment variables:
- AURORA_SELECTION_LOG: path to CSV file (default: disabled)
- AURORA_SELECTION_LOG_APPEND: if '1', append to existing file (default: overwrite)

Usage:
    from selection_telemetry import SelectionTelemetry
    
    telemetry = SelectionTelemetry()  # auto-detects env vars
    
    if telemetry.is_enabled():
        telemetry.log_selection(
            timestamp="2025-10-30T12:00:00Z",
            lesson_id="01-01",
            requested_text="Network topology diagram",
            image_index=2,
            tfidf_score=0.75,
            legacy_score=0.60,
            combined_score=0.69,
            selected=True
        )
    
    telemetry.close()  # flush and close file
"""
import os
import csv
import threading
from typing import Optional
from datetime import datetime


class SelectionTelemetry:
    """
    Thread-safe CSV logger for image selection decisions.
    """
    
    # CSV columns
    COLUMNS = [
        'timestamp',
        'lesson_id',
        'requested_text',
        'image_index',
        'tfidf_score',
        'legacy_score',
        'combined_score',
        'selected'
    ]
    
    def __init__(self, log_path: Optional[str] = None, append: bool = None):
        """
        Initialize telemetry logger.
        
        Args:
            log_path: Path to CSV file. If None, reads from AURORA_SELECTION_LOG env var.
            append: If True, append to existing file. If None, reads from AURORA_SELECTION_LOG_APPEND.
        """
        self.log_path = log_path or os.environ.get('AURORA_SELECTION_LOG', '')
        
        if append is None:
            append_env = os.environ.get('AURORA_SELECTION_LOG_APPEND', '0')
            self.append = str(append_env).lower() in ('1', 'true', 'yes', 'on')
        else:
            self.append = append
        
        self.file_handle = None
        self.csv_writer = None
        self.lock = threading.Lock()
        self._initialized = False
        
        if self.log_path:
            self._initialize_file()
    
    def _initialize_file(self):
        """Initialize CSV file with headers if needed."""
        try:
            file_exists = os.path.exists(self.log_path)
            
            # Determine mode
            mode = 'a' if (self.append and file_exists) else 'w'
            
            self.file_handle = open(self.log_path, mode, newline='', encoding='utf-8')
            self.csv_writer = csv.DictWriter(self.file_handle, fieldnames=self.COLUMNS)
            
            # Write header if creating new file or overwriting
            if mode == 'w' or (mode == 'a' and not file_exists):
                self.csv_writer.writeheader()
                self.file_handle.flush()
            
            self._initialized = True
            print(f"✅ Selection telemetry initialized: {self.log_path} (mode: {mode})")
        
        except Exception as e:
            print(f"⚠️ Failed to initialize selection telemetry: {e}")
            self.file_handle = None
            self.csv_writer = None
            self._initialized = False
    
    def is_enabled(self) -> bool:
        """Check if telemetry is enabled and ready to log."""
        return self._initialized and self.csv_writer is not None
    
    def log_selection(
        self,
        timestamp: Optional[str] = None,
        lesson_id: str = '',
        requested_text: str = '',
        image_index: int = -1,
        tfidf_score: float = 0.0,
        legacy_score: float = 0.0,
        combined_score: float = 0.0,
        selected: bool = False
    ):
        """
        Log a single image selection decision.
        
        Args:
            timestamp: ISO timestamp (default: current time)
            lesson_id: Lesson identifier (e.g., "01-01" for module 1, lesson 1)
            requested_text: Text describing requested image
            image_index: Index of the candidate image
            tfidf_score: TF-IDF similarity score (0.0-1.0)
            legacy_score: Legacy heuristic score (0.0-1.0)
            combined_score: Weighted combined score (0.0-1.0)
            selected: Whether this image was selected
        """
        if not self.is_enabled():
            return
        
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat() + 'Z'
        
        row = {
            'timestamp': timestamp,
            'lesson_id': lesson_id,
            'requested_text': requested_text[:100],  # truncate long text
            'image_index': image_index,
            'tfidf_score': f"{tfidf_score:.4f}",
            'legacy_score': f"{legacy_score:.4f}",
            'combined_score': f"{combined_score:.4f}",
            'selected': '1' if selected else '0'
        }
        
        try:
            with self.lock:
                self.csv_writer.writerow(row)
                self.file_handle.flush()  # ensure data is written
        except Exception as e:
            print(f"⚠️ Failed to log selection: {e}")
    
    def log_candidates(
        self,
        timestamp: Optional[str] = None,
        lesson_id: str = '',
        requested_text: str = '',
        candidates: list = None,
        selected_index: int = -1
    ):
        """
        Log all candidates for a single selection decision.
        
        Args:
            timestamp: ISO timestamp
            lesson_id: Lesson identifier
            requested_text: Text describing requested image
            candidates: List of dicts with keys: image_index, tfidf_score, legacy_score, combined_score
            selected_index: Index of the selected candidate (matches image_index in candidates)
        """
        if not candidates:
            return
        
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat() + 'Z'
        
        for candidate in candidates:
            self.log_selection(
                timestamp=timestamp,
                lesson_id=lesson_id,
                requested_text=requested_text,
                image_index=candidate.get('image_index', -1),
                tfidf_score=candidate.get('tfidf_score', 0.0),
                legacy_score=candidate.get('legacy_score', 0.0),
                combined_score=candidate.get('combined_score', 0.0),
                selected=(candidate.get('image_index') == selected_index)
            )
    
    def close(self):
        """Close the telemetry file handle."""
        if self.file_handle:
            try:
                self.file_handle.close()
                print(f"✅ Selection telemetry closed: {self.log_path}")
            except Exception as e:
                print(f"⚠️ Error closing telemetry: {e}")
            finally:
                self.file_handle = None
                self.csv_writer = None
                self._initialized = False
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
        return False


# Module-level instance for convenience
_global_telemetry = None


def get_global_telemetry() -> SelectionTelemetry:
    """Get or create the global telemetry instance."""
    global _global_telemetry
    if _global_telemetry is None:
        _global_telemetry = SelectionTelemetry()
    return _global_telemetry


def close_global_telemetry():
    """Close and reset the global telemetry instance."""
    global _global_telemetry
    if _global_telemetry is not None:
        _global_telemetry.close()
        _global_telemetry = None
