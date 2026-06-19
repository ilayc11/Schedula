/**
 * useConstraintProgress Hook
 * 
 * Manages WebSocket connection for real-time LLM pipeline progress updates
 * during constraint processing.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

// Derive WebSocket URL from API base URL
// VITE_API_BASE_URL is typically "http://localhost:8000" or similar
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Convert HTTP URL to WebSocket URL
 * @param {string} httpUrl - HTTP/HTTPS URL
 * @returns {string} WebSocket URL
 */
function getWebSocketUrl(httpUrl) {
  if (!httpUrl) {
    // Fallback: use current host with ws protocol
    return (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host;
  }
  // Convert http:// to ws:// and https:// to wss://
  return httpUrl.replace(/^http/, 'ws');
}

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || getWebSocketUrl(API_BASE_URL);

/**
 * @typedef {Object} StageUpdate
 * @property {string} stage - Current stage name
 * @property {string} display_text - Human-readable stage description
 * @property {number} progress - Progress percentage (0-100)
 * @property {string} status - "in_progress" | "complete" | "error"
 */

/**
 * @typedef {Object} UseConstraintProgressReturn
 * @property {string|null} sessionId - Current session ID
 * @property {StageUpdate|null} currentStage - Current stage information
 * @property {boolean} isConnected - WebSocket connection status
 * @property {boolean} isProcessing - Whether processing is in progress
 * @property {function} startSession - Start a new progress tracking session
 * @property {function} endSession - End the current session
 * @property {string|null} error - Error message if any
 */

/**
 * Generate a UUID v4
 * @returns {string}
 */
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

/**
 * Hook for managing WebSocket-based constraint processing progress updates.
 * 
 * @returns {UseConstraintProgressReturn}
 */
export function useConstraintProgress() {
  const [sessionId, setSessionId] = useState(null);
  const [currentStage, setCurrentStage] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);

  /**
   * Clean up WebSocket connection and intervals
   */
  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  /**
   * Connect WebSocket for a given session ID
   */
  const connect = useCallback((sid) => {
    cleanup();
    
    const wsUrl = `${WS_BASE_URL}/ws/constraints/${sid}`;
    console.log(`[useConstraintProgress] Connecting to ${wsUrl}`);
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    
    ws.onopen = () => {
      console.log('[useConstraintProgress] WebSocket connected');
      setIsConnected(true);
      setError(null);
      
      // Start ping interval to keep connection alive
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000); // Ping every 30 seconds
    };
    
    ws.onmessage = (event) => {
      try {
        // Handle pong response
        if (event.data === 'pong') {
          return;
        }
        
        const data = JSON.parse(event.data);
        console.log('[useConstraintProgress] Received:', data);
        
        if (data.type === 'stage_update') {
          setCurrentStage({
            stage: data.stage,
            displayText: data.display_text,
            progress: data.progress,
            status: data.status,
          });
          
          // Check if processing is complete or errored
          if (data.status === 'complete' || data.status === 'error') {
            setIsProcessing(false);
            if (data.status === 'error') {
              setError(data.display_text);
            }
          }
        }
      } catch (e) {
        console.error('[useConstraintProgress] Error parsing message:', e);
      }
    };
    
    ws.onerror = (event) => {
      console.error('[useConstraintProgress] WebSocket error:', event);
      setError('Connection error');
    };
    
    ws.onclose = (event) => {
      console.log('[useConstraintProgress] WebSocket closed:', event.code, event.reason);
      setIsConnected(false);
      
      // Note: Reconnection is not attempted to avoid stale closure issues.
      // If the connection drops during processing, the user will see the fallback UI.
    };
  }, [cleanup]);

  /**
   * Start a new progress tracking session.
   * Returns the session ID to be passed to the preview API.
   * 
   * @returns {string} The session ID
   */
  const startSession = useCallback(() => {
    const newSessionId = generateUUID();
    setSessionId(newSessionId);
    setCurrentStage(null);
    setError(null);
    setIsProcessing(true);
    
    // Connect WebSocket
    connect(newSessionId);
    
    return newSessionId;
  }, [connect]);

  /**
   * End the current session and clean up.
   */
  const endSession = useCallback(() => {
    cleanup();
    setSessionId(null);
    setCurrentStage(null);
    setIsConnected(false);
    setIsProcessing(false);
    setError(null);
  }, [cleanup]);

  /**
   * Reset state without ending the session (for retry scenarios)
   */
  const reset = useCallback(() => {
    setCurrentStage(null);
    setError(null);
    setIsProcessing(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    sessionId,
    currentStage,
    isConnected,
    isProcessing,
    error,
    startSession,
    endSession,
    reset,
  };
}

export default useConstraintProgress;
