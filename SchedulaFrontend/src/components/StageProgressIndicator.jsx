/**
 * StageProgressIndicator Component
 * 
 * Displays the current LLM pipeline processing stage with animation.
 * Replaces the simple "..." typing dots with informative stage progress.
 */

import React from 'react';
import './StageProgressIndicator.css';

/**
 * @typedef {Object} StageInfo
 * @property {string} stage - Current stage name
 * @property {string} displayText - Human-readable stage description
 * @property {number} progress - Progress percentage (0-100)
 * @property {string} status - "in_progress" | "complete" | "error"
 */

/**
 * Stage icons for visual feedback
 */
const STAGE_ICONS = {
  connecting: '🔌',
  translating: '🌐',
  understanding: '🧠',
  processing: '⚙️',
  validating: '✅',
  extracting: '📊',
  finalizing: '🎯',
  complete: '✨',
  error: '❌',
};

/**
 * Get icon for a stage
 * @param {string} stage 
 * @returns {string}
 */
function getStageIcon(stage) {
  return STAGE_ICONS[stage] || '⏳';
}

/**
 * StageProgressIndicator component
 * 
 * @param {Object} props
 * @param {StageInfo|null} props.stageInfo - Current stage information
 * @param {boolean} props.isConnecting - Whether WebSocket is connecting
 * @param {boolean} props.fallback - Show fallback dots animation if no stage info
 */
function StageProgressIndicator({ stageInfo, isConnecting = false, fallback = false }) {
  // Show connecting state
  if (isConnecting && !stageInfo) {
    return (
      <div className="stage-progress-indicator connecting">
        <span className="stage-icon">{STAGE_ICONS.connecting}</span>
        <span className="stage-text">Connecting...</span>
        <div className="stage-dots">
          <span /><span /><span />
        </div>
      </div>
    );
  }

  // Show fallback dots if no stage info and fallback is enabled
  if (!stageInfo && fallback) {
    return (
      <div className="stage-progress-indicator fallback">
        <div className="typing-dots" aria-label="Processing">
          <span /><span /><span />
        </div>
      </div>
    );
  }

  // No stage info and no fallback - render nothing
  if (!stageInfo) {
    return null;
  }

  const { stage, displayText, progress, status } = stageInfo;
  const icon = getStageIcon(stage);
  const isComplete = status === 'complete';

  return (
    <div className={`stage-progress-indicator ${status}`}>
      <div className="stage-header">
        <span className="stage-icon" aria-hidden="true">{icon}</span>
        <span className="stage-text">{displayText}</span>
      </div>
    </div>
  );
}

export default StageProgressIndicator;
