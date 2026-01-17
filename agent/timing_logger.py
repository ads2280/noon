"""
Timing logger utility for agent performance debugging.
Writes timing information to a file instead of console.
Only logs when ENABLE_TIMING_LOGGER environment variable is set to "true" or "1".
"""

import time
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading

# Thread-safe file writing
_lock = threading.Lock()

# Log file path - in project root
_log_file_path = Path(__file__).parent.parent / "agent_timing.log"


def _is_enabled() -> bool:
    """Check if timing logging is enabled via environment variable."""
    return os.getenv("ENABLE_TIMING_LOGGER", "").lower() in ("true", "1")


class TimingLogger:
    """Thread-safe timing logger that writes to a file."""
    
    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file or _log_file_path
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Ensure log file exists and write header if new."""
        if not _is_enabled():
            return
        with _lock:
            if not self.log_file.exists():
                with open(self.log_file, "w") as f:
                    f.write(f"=== Agent Timing Log - Started {datetime.now().isoformat()} ===\n\n")
    
    def log(self, step: str, duration: Optional[float] = None, details: Optional[str] = None):
        """
        Log a timing step.
        
        Args:
            step: Name of the step
            duration: Duration in seconds (if None, marks start of step)
            details: Optional additional details
        """
        if not _is_enabled():
            return
        
        timestamp = datetime.now().isoformat()
        with _lock:
            try:
                with open(self.log_file, "a") as f:
                    if duration is not None:
                        f.write(f"[{timestamp}] {step}: {duration:.3f}s")
                    else:
                        f.write(f"[{timestamp}] {step}: START")
                    
                    if details:
                        f.write(f" | {details}")
                    f.write("\n")
            except Exception as e:
                # Fallback to regular logger if file write fails
                logging.getLogger(__name__).error(f"Failed to write timing log: {e}")
    
    def log_step(self, step: str, duration: float, details: Optional[str] = None):
        """Log a completed step with duration."""
        self.log(step, duration=duration, details=details)
    
    def log_start(self, step: str, details: Optional[str] = None):
        """Log the start of a step."""
        self.log(step, duration=None, details=details)


# Global timing logger instance
_timing_logger = TimingLogger()


def log_timing(step: str, duration: Optional[float] = None, details: Optional[str] = None):
    """Convenience function to log timing."""
    _timing_logger.log(step, duration=duration, details=details)


def log_step(step: str, duration: float, details: Optional[str] = None):
    """Log a completed step."""
    _timing_logger.log_step(step, duration, details)


def log_start(step: str, details: Optional[str] = None):
    """Log the start of a step."""
    _timing_logger.log_start(step, details)
