"""
Session Manager for Call Analysis Service
Handles in-memory storage of analysis results with automatic cleanup
"""

import uuid
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List


class SessionManager:
    """
    Manages analysis sessions with automatic cleanup
    
    Features:
    - In-memory storage (no database persistence)
    - Session expiration after 30 minutes idle
    - Thread-safe operations
    - Automatic cleanup of expired sessions
    """
    
    def __init__(self, session_timeout_minutes=30):
        self.sessions: Dict[str, dict] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.lock = threading.Lock()
        self.cleanup_thread = None
        self.running = False
        
    def start_cleanup_thread(self):
        """Start background thread for automatic session cleanup"""
        if not self.running:
            self.running = True
            self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self.cleanup_thread.start()
            
    def stop_cleanup_thread(self):
        """Stop the cleanup thread"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
    
    def create_session(self) -> str:
        """
        Create a new session
        
        Returns:
            session_id: Unique session identifier
        """
        session_id = str(uuid.uuid4())
        
        with self.lock:
            self.sessions[session_id] = {
                'created_at': datetime.utcnow(),
                'last_accessed': datetime.utcnow(),
                'analyses': []
            }
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """
        Get session data and update last_accessed timestamp
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data or None if not found/expired
        """
        with self.lock:
            session = self.sessions.get(session_id)
            
            if session:
                # Update last accessed time
                session['last_accessed'] = datetime.utcnow()
                return session
            
            return None
    
    def add_analysis(self, session_id: str, analysis_result: dict) -> bool:
        """
        Add analysis result to session
        
        Args:
            session_id: Session identifier
            analysis_result: Complete analysis result dictionary
            
        Returns:
            True if successful, False if session not found
        """
        with self.lock:
            session = self.sessions.get(session_id)
            
            if session:
                session['analyses'].append(analysis_result)
                session['last_accessed'] = datetime.utcnow()
                return True
            
            return False
    
    def get_analyses(self, session_id: str) -> Optional[List[dict]]:
        """
        Get all analyses for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of analysis results or None if session not found
        """
        session = self.get_session(session_id)
        return session['analyses'] if session else None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session (on logout or manual cleanup)
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False
    
    def get_session_count(self) -> int:
        """Get total number of active sessions"""
        with self.lock:
            return len(self.sessions)
    
    def _cleanup_loop(self):
        """Background thread that removes expired sessions"""
        while self.running:
            time.sleep(60)  # Check every minute
            self._cleanup_expired_sessions()
    
    def _cleanup_expired_sessions(self):
        """Remove sessions that haven't been accessed within timeout period"""
        now = datetime.utcnow()
        expired_sessions = []
        
        with self.lock:
            for session_id, session in self.sessions.items():
                last_accessed = session['last_accessed']
                
                if now - last_accessed > self.session_timeout:
                    expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                del self.sessions[session_id]
        
        if expired_sessions:
            print(f"Cleaned up {len(expired_sessions)} expired sessions")


# Global session manager instance
session_manager = SessionManager(session_timeout_minutes=30)
