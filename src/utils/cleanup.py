"""
Cleanup utility for managing temporary and generated files.
Ensures secure, anonymous hosting by removing PDFs after generation.
"""
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def cleanup_old_files(directory: str, max_age_hours: int = 1) -> int:
    """
    Delete files older than max_age_hours from the specified directory.
    
    Args:
        directory: Path to directory to clean
        max_age_hours: Maximum age of files to keep (in hours)
    
    Returns:
        Number of files deleted
    """
    try:
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0
        
        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for file_path in dir_path.glob("*.pdf"):
            try:
                # Get file modification time
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                # Delete if older than cutoff
                if mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old PDF: {file_path.name}")
            except Exception as e:
                logger.warning(f"Could not delete {file_path}: {e}")
        
        return deleted_count
    
    except Exception as e:
        logger.error(f"Error during cleanup of {directory}: {e}")
        return 0


def clear_directory(directory: str) -> int:
    """
    Delete ALL PDF files from the specified directory.
    Use with caution!
    
    Args:
        directory: Path to directory to clear
    
    Returns:
        Number of files deleted
    """
    try:
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0
        
        deleted_count = 0
        
        for file_path in dir_path.glob("*.pdf"):
            try:
                file_path.unlink()
                deleted_count += 1
                logger.info(f"Cleared PDF: {file_path.name}")
            except Exception as e:
                logger.warning(f"Could not delete {file_path}: {e}")
        
        return deleted_count
    
    except Exception as e:
        logger.error(f"Error clearing {directory}: {e}")
        return 0


class AutoCleanupDaemon(threading.Thread):
    """
    Background daemon thread that periodically cleans up old generated files.
    Runs in daemon mode and will not prevent application shutdown.
    """
    
    def __init__(self, directory: str, check_interval_minutes: int = 5, max_age_hours: int = 1):
        """
        Initialize the cleanup daemon.
        
        Args:
            directory: Path to directory to monitor
            check_interval_minutes: How often to check for old files
            max_age_hours: Maximum age of files to keep
        """
        super().__init__(daemon=True)
        self.directory = directory
        self.check_interval = check_interval_minutes * 60  # Convert to seconds
        self.max_age_hours = max_age_hours
        self._stop_event = threading.Event()
    
    def run(self):
        """Run the cleanup daemon."""
        logger.info(f"AutoCleanup daemon started for {self.directory}")
        
        while not self._stop_event.is_set():
            try:
                deleted = cleanup_old_files(self.directory, self.max_age_hours)
                if deleted > 0:
                    logger.info(f"Cleanup daemon removed {deleted} old files")
            except Exception as e:
                logger.error(f"Error in cleanup daemon: {e}")
            
            # Wait for next check (use Event.wait for graceful shutdown)
            self._stop_event.wait(self.check_interval)
    
    def stop(self):
        """Signal the daemon to stop."""
        self._stop_event.set()


def start_cleanup_daemon(directory: str, check_interval_minutes: int = 5, max_age_hours: int = 1) -> AutoCleanupDaemon:
    """
    Start a background cleanup daemon for the specified directory.
    
    Args:
        directory: Path to directory to monitor
        check_interval_minutes: How often to check for old files (default: 5 minutes)
        max_age_hours: Maximum age of files to keep (default: 1 hour)
    
    Returns:
        The daemon thread (for potential management/stopping)
    """
    # Ensure directory exists
    Path(directory).mkdir(parents=True, exist_ok=True)
    
    daemon = AutoCleanupDaemon(directory, check_interval_minutes, max_age_hours)
    daemon.start()
    
    return daemon
