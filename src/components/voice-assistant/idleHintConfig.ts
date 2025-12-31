/**
 * Idle State Hint Configuration for Voice Assistant
 * 
 * This file contains the configuration for the idle state hint text.
 * Modify values here to easily adjust the hint message and styling.
 */

/**
 * Configuration for the idle state hint text displayed below the voice button
 */
export const IDLE_HINT_CONFIG = {
  /**
   * The hint message text to display
   */
  text: 'Click to start conversation',
  
  /**
   * Tailwind CSS classes for styling the hint text
   * Easy to customize: change this string to any Tailwind classes for a full aesthetic redo
   */
  className: 'text-sm text-neutral-400 mt-4 text-center',
} as const;


