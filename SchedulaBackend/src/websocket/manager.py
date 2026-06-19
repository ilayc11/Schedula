"""
WebSocket Connection Manager for real-time LLM pipeline progress updates.

Manages WebSocket connections by session ID and broadcasts stage updates
to connected clients during constraint processing.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """User-friendly pipeline stage names for display."""
    CONNECTING = "connecting"
    TRANSLATING = "translating"
    UNDERSTANDING = "understanding"
    PROCESSING = "processing"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


# Mapping from internal stage names to user-friendly phases
STAGE_MAPPING: Dict[str, PipelineStage] = {
    # Stage 0
    "stage_0": PipelineStage.TRANSLATING,
    "translation": PipelineStage.TRANSLATING,
    "clarification": PipelineStage.TRANSLATING,
    # Stage 0.5
    "text_combination": PipelineStage.UNDERSTANDING,
    # Stage 1
    "atomization": PipelineStage.UNDERSTANDING,
    # Stage 2
    "classification": PipelineStage.PROCESSING,
    # Stage 3
    "negation": PipelineStage.PROCESSING,
    # Stage 4
    "deduplication": PipelineStage.PROCESSING,
    # Stage 5
    "conflict_handler": PipelineStage.VALIDATING,
    "conflict_validation": PipelineStage.VALIDATING,
    # Stage 6
    "extraction": PipelineStage.EXTRACTING,
    # Stage 7
    "rule_validation": PipelineStage.VALIDATING,
    # Stage 8
    "conflict_detection": PipelineStage.VALIDATING,
    # Stage 9
    "final_deduplication": PipelineStage.FINALIZING,
    # Stage 10
    "logging": PipelineStage.FINALIZING,
    # WRAP stage
    "wrap": PipelineStage.VALIDATING,
}


# User-friendly display text for each stage
STAGE_DISPLAY_TEXT: Dict[PipelineStage, str] = {
    PipelineStage.CONNECTING: "Connecting...",
    PipelineStage.TRANSLATING: "Translating & validating input...",
    PipelineStage.UNDERSTANDING: "Understanding your constraints...",
    PipelineStage.PROCESSING: "Processing constraints...",
    PipelineStage.VALIDATING: "Validating constraints...",
    PipelineStage.EXTRACTING: "Extracting schedule data...",
    PipelineStage.FINALIZING: "Finalizing results...",
    PipelineStage.COMPLETE: "Complete!",
    PipelineStage.ERROR: "An error occurred",
}


@dataclass
class StageUpdate:
    """Represents a stage update message to send to clients."""
    stage: str
    display_text: str
    progress: int  # 0-100
    status: str  # "in_progress", "complete", "error"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "stage_update",
            "stage": self.stage,
            "display_text": self.display_text,
            "progress": self.progress,
            "status": self.status,
        }


class ConnectionManager:
    """
    Manages WebSocket connections for real-time pipeline progress updates.
    
    Each session_id corresponds to a single constraint processing request.
    Multiple clients can subscribe to the same session_id.
    """
    
    def __init__(self):
        # Map session_id -> list of connected WebSockets
        self._connections: Dict[str, list[WebSocket]] = {}
        # Map session_id -> current stage (for late joiners)
        self._current_stages: Dict[str, StageUpdate] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection for a session."""
        await websocket.accept()
        
        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = []
            self._connections[session_id].append(websocket)
        
        logger.info(f"WebSocket connected for session {session_id}")
        
        # Send current stage if processing is already in progress
        async with self._lock:
            current = self._current_stages.get(session_id)
        
        if current:
            try:
                await websocket.send_json(current.to_dict())
            except Exception as e:
                logger.warning(f"Failed to send current stage to new connection: {e}")
    
    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from a session."""
        async with self._lock:
            if session_id in self._connections:
                try:
                    self._connections[session_id].remove(websocket)
                except ValueError:
                    pass
                
                # Clean up empty sessions
                if not self._connections[session_id]:
                    del self._connections[session_id]
                    if session_id in self._current_stages:
                        del self._current_stages[session_id]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def broadcast_stage(
        self,
        session_id: str,
        internal_stage: str,
        progress: Optional[int] = None,
        status: str = "in_progress",
        custom_text: Optional[str] = None
    ) -> None:
        """
        Broadcast a stage update to all connected clients for a session.
        
        Args:
            session_id: The session to broadcast to
            internal_stage: Internal stage name (will be mapped to user-friendly phase)
            progress: Progress percentage (0-100). If None, auto-calculated.
            status: "in_progress", "complete", or "error"
            custom_text: Optional custom display text (overrides default)
        """
        # Map internal stage to user-friendly phase
        stage = STAGE_MAPPING.get(internal_stage, PipelineStage.PROCESSING)
        
        # Auto-calculate progress based on stage order if not provided
        if progress is None:
            stage_order = [
                PipelineStage.TRANSLATING,
                PipelineStage.UNDERSTANDING,
                PipelineStage.PROCESSING,
                PipelineStage.VALIDATING,
                PipelineStage.EXTRACTING,
                PipelineStage.FINALIZING,
                PipelineStage.COMPLETE,
            ]
            try:
                idx = stage_order.index(stage)
                progress = int((idx / (len(stage_order) - 1)) * 100)
            except ValueError:
                progress = 50
        
        display_text = custom_text or STAGE_DISPLAY_TEXT.get(stage, "Processing...")
        
        update = StageUpdate(
            stage=stage.value,
            display_text=display_text,
            progress=progress,
            status=status
        )
        
        # Store current stage for late joiners
        async with self._lock:
            self._current_stages[session_id] = update
            connections = self._connections.get(session_id, []).copy()
        
        if not connections:
            logger.debug(f"No WebSocket connections for session {session_id}")
            return
        
        # Broadcast to all connected clients
        message = update.to_dict()
        disconnected = []
        
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(ws)
        
        # Clean up disconnected WebSockets
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    try:
                        self._connections[session_id].remove(ws)
                    except (ValueError, KeyError):
                        pass
    
    async def broadcast_complete(self, session_id: str) -> None:
        """Broadcast completion and clean up session."""
        await self.broadcast_stage(
            session_id,
            "complete",
            progress=100,
            status="complete",
            custom_text="Complete!"
        )
        
        # Clean up session after a delay (allow message to be received)
        await asyncio.sleep(0.5)
        async with self._lock:
            self._current_stages.pop(session_id, None)
    
    async def broadcast_error(self, session_id: str, error_message: str) -> None:
        """Broadcast an error and clean up session."""
        await self.broadcast_stage(
            session_id,
            "error",
            progress=0,
            status="error",
            custom_text=f"Error: {error_message}"
        )
        
        # Clean up session
        async with self._lock:
            self._current_stages.pop(session_id, None)
    
    def has_connections(self, session_id: str) -> bool:
        """Check if a session has any active connections."""
        return session_id in self._connections and len(self._connections[session_id]) > 0
    
    def get_connection_count(self, session_id: str) -> int:
        """Get the number of connections for a session."""
        return len(self._connections.get(session_id, []))


# Global WebSocket manager instance
ws_manager = ConnectionManager()
