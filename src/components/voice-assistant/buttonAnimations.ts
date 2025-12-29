/**
 * Animation Configuration for Voice Assistant Button
 * 
 * This file contains all animation parameters for the circular voice assistant button.
 * Modify values here to easily adjust animations without touching component code.
 */

// ============================================================================
// BASE ANIMATION PARAMETERS
// ============================================================================

// Pulse Animation - Controls the continuous pulsing effect
export const PULSE_CONFIG = {
  duration: 4.0, // Duration in seconds for one complete pulse cycle
  scale: {
    min: 1.0,    // Minimum scale (normal size)
    max: 1.05,   // Maximum scale (5% larger - keeps ring visible)
  },
  opacity: {
    min: 1.0,    // Minimum opacity (ring never fades)
    max: 1.0,    // Maximum opacity
  },
} as const;

// Glow Effect - Controls the glowing/shadow effect
export const GLOW_CONFIG = {
  intensity: 0.8,           // Glow intensity (0-1)
  color: 'rgba(255, 255, 255, 0.5)', // Glow color (white with transparency)
  blur: 20,                 // Blur radius in pixels
} as const;

// Ripple Effect - Controls the ripple animation on click
export const RIPPLE_CONFIG = {
  duration: 0.6,    // Total duration in seconds
  maxScale: 2.0,    // Maximum scale the ripple expands to
  fadeOut: 0.4,     // When to start fading out (in seconds)
  color: 'rgba(255, 255, 255, 0.3)', // Ripple color
} as const;

// ============================================================================
// STATE-SPECIFIC MULTIPLIERS
// ============================================================================

// These multipliers adjust base animations for different states
export const STATE_MULTIPLIERS = {
  idle: {
    pulseSpeed: 1.0,      // Normal speed
    glowIntensity: 1.0,   // Normal intensity
  },
  connecting: {
    pulseSpeed: 2.0,      // 2x faster pulse
    glowIntensity: 1.3,   // 30% more intense glow
  },
  connected: {
    pulseSpeed: 0.5,      // Slower pulse (half speed)
    glowIntensity: 0.7,   // Reduced glow
  },
  listening: {
    pulseSpeed: 0.5,      // Not used for listening (uses spin instead)
    glowIntensity: 0.7,   // Reduced glow
    spinSpeed: 2.0,       // Rotation speed in seconds (faster = lower number)
  },
} as const;

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

export interface PulseConfig {
  duration: number;
  scale: { min: number; max: number };
  opacity: { min: number; max: number };
}

export interface GlowConfig {
  intensity: number;
  color: string;
  blur: number;
}

export interface RippleConfig {
  duration: number;
  maxScale: number;
  fadeOut: number;
  color: string;
}

export interface StateMultipliers {
  pulseSpeed: number;
  glowIntensity: number;
}

export interface AnimationConfig {
  pulse: PulseConfig;
  glow: GlowConfig;
  ripple: RippleConfig;
  states: {
    idle: StateMultipliers;
    connecting: StateMultipliers;
    connected: StateMultipliers;
  };
}

// ============================================================================
// DEFAULT CONFIGURATION
// ============================================================================

export const defaultAnimationConfig: AnimationConfig = {
  pulse: PULSE_CONFIG,
  glow: GLOW_CONFIG,
  ripple: RIPPLE_CONFIG,
  states: STATE_MULTIPLIERS,
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get pulse duration for a specific state
 */
export function getPulseDuration(state: 'idle' | 'connecting' | 'connected' | 'listening'): number {
  const multiplier = STATE_MULTIPLIERS[state === 'listening' ? 'listening' : state].pulseSpeed;
  return PULSE_CONFIG.duration / multiplier;
}

/**
 * Get glow intensity for a specific state
 */
export function getGlowIntensity(state: 'idle' | 'connecting' | 'connected' | 'listening'): number {
  const multiplier = STATE_MULTIPLIERS[state === 'listening' ? 'listening' : state].glowIntensity;
  return GLOW_CONFIG.intensity * multiplier;
}

/**
 * Get CSS animation string for pulse
 */
export function getPulseAnimation(state: 'idle' | 'connecting' | 'connected' | 'listening'): string {
  const duration = getPulseDuration(state);
  return `pulse ${duration}s ease-in-out infinite`;
}

/**
 * Get spin duration for listening state
 */
export function getSpinDuration(): number {
  return STATE_MULTIPLIERS.listening.spinSpeed || 2.0;
}

/**
 * State colors for inner ring
 */
export const STATE_COLORS = {
  idle: 'rgba(255, 255, 255, 0.8)',  // White (default)
  listening: '#0000ff',  // Blue (when connected/listening)
  speaking: '#00ff00',  // Green (when speaking)
  outerRing: '#ffffff',  // White (for dashed border)
} as const;

/**
 * Listening state animation timing (in seconds)
 * Steps happen sequentially:
 * 1. Outer ring segments shrink to create gaps
 * 2. Spinning starts
 * 3. Inner ring becomes green
 */
export const LISTENING_ANIMATION_TIMING = {
  step1_dashTransition: 0.5,  // Time for outer ring segments to shrink (Phase 5: segment shrink duration)
  step2_spinStart: 0.3,       // Delay before spinning starts (after step 1)
  step3_innerGreen: 0.3,      // Delay before inner ring turns green (after step 2)
} as const;

/**
 * End conversation animation timing (in seconds)
 * Segments grow in length until they touch each other (form complete circle)
 */
export const END_CONVERSATION_ANIMATION_TIMING = {
  step1_dashesFade: 0.6,      // Time for segments to grow and form complete circle (Phase 5: segment grow duration)
} as const;

/**
 * Phase 5: Segment Animation Configuration
 * Controls the 5-segment outer ring animation system
 */
export const SEGMENT_ANIMATION_CONFIG = {
  // Segment length in degrees
  idle: {
    length: 72,           // Full segment length (360° / 5 = 72° per segment, touching)
    arcLength: 57.8,      // Approximate SVG arc length in units (radius 46 * 72° in radians)
  },
  listening: {
    length: 40,           // Reduced segment length (creates gaps)
    arcLength: 32.1,      // Approximate SVG arc length in units (radius 46 * 40° in radians)
    gapLength: 25.7,      // Gap length in SVG units (for stroke-dasharray)
  },
  // Animation durations (in seconds)
  shrinkDuration: 0.5,     // Time for segments to shrink when starting conversation
  growDuration: 0.6,       // Time for segments to grow when ending conversation
} as const;

