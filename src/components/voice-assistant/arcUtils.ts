/**
 * Utility functions for generating SVG arc paths for the voice assistant button outer ring
 * 
 * The outer ring consists of 5 individual segments that animate their length:
 * - Idle: Segments are long and touching (form complete circle)
 * - Listening: Segments shrink to create evenly spaced gaps
 */

// Circle parameters matching the current implementation
export const CIRCLE_CONFIG = {
  centerX: 50,
  centerY: 50,
  radius: 46,
  segmentCount: 5,
} as const;

// Arc length configurations (in degrees)
export const SEGMENT_LENGTHS = {
  idle: 72,           // 360° / 5 = 72° per segment (touching, no gaps)
  listening: 40,      // Segments with gaps (gap size = 72 - 40 = 32°)
  ending: 72,         // Same as idle (grow back to touching)
} as const;

/**
 * Convert an angle in degrees to a point on a circle
 */
function angleToPoint(
  centerX: number,
  centerY: number,
  radius: number,
  angleDegrees: number
): [number, number] {
  const angleRadians = (angleDegrees * Math.PI) / 180;
  const x = centerX + radius * Math.cos(angleRadians);
  const y = centerY + radius * Math.sin(angleRadians);
  return [x, y];
}

/**
 * Generate an SVG arc path between two angles
 * 
 * @param centerX - X coordinate of circle center
 * @param centerY - Y coordinate of circle center
 * @param radius - Circle radius
 * @param startAngle - Starting angle in degrees (0° = right, increases clockwise)
 * @param endAngle - Ending angle in degrees
 * @returns SVG path string for the arc
 */
export function generateArcPath(
  centerX: number,
  centerY: number,
  radius: number,
  startAngle: number,
  endAngle: number
): string {
  const [startX, startY] = angleToPoint(centerX, centerY, radius, startAngle);
  const [endX, endY] = angleToPoint(centerX, centerY, radius, endAngle);
  
  // Calculate the sweep flag (1 for counterclockwise is typical for SVG)
  // We want clockwise, so we use sweep-flag = 0
  // large-arc-flag: 0 for arcs less than 180°, 1 for arcs greater than 180°
  const sweepDegrees = endAngle - startAngle;
  const normalizedSweep = ((sweepDegrees % 360) + 360) % 360;
  const largeArcFlag = normalizedSweep > 180 ? 1 : 0;
  
  // For clockwise direction, use sweep-flag = 1
  // SVG arcs: sweep-flag 0 = counter-clockwise, 1 = clockwise
  const sweepFlag = 1;
  
  return `M ${startX} ${startY} A ${radius} ${radius} 0 ${largeArcFlag} ${sweepFlag} ${endX} ${endY}`;
}

/**
 * Generate all 5 segment paths for the outer ring
 * 
 * @param segmentLength - Length of each segment in degrees
 * @param startOffset - Optional offset angle in degrees (for rotation)
 * @returns Array of SVG path strings, one for each segment
 */
export function generateSegmentPaths(
  segmentLength: number = SEGMENT_LENGTHS.idle,
  startOffset: number = 0
): string[] {
  const { centerX, centerY, radius, segmentCount } = CIRCLE_CONFIG;
  const paths: string[] = [];
  
  // Each segment occupies 72° (360° / 5)
  // If segmentLength is less than 72°, there will be gaps
  const segmentSpacing = 360 / segmentCount; // 72°
  
  for (let i = 0; i < segmentCount; i++) {
    // Calculate start and end angles for this segment
    // Start from top (-90° in SVG coordinates where 0° = right, +90° = bottom)
    // Adjust for offset (rotation) and segment position
    const baseAngle = -90 + (i * segmentSpacing) + startOffset;
    const startAngle = baseAngle;
    const endAngle = baseAngle + segmentLength;
    
    const path = generateArcPath(centerX, centerY, radius, startAngle, endAngle);
    paths.push(path);
  }
  
  return paths;
}

/**
 * Generate segment paths for idle state (touching, full length)
 */
export function generateIdleSegments(): string[] {
  return generateSegmentPaths(SEGMENT_LENGTHS.idle);
}

/**
 * Generate segment paths for listening state (with gaps)
 */
export function generateListeningSegments(rotationOffset: number = 0): string[] {
  return generateSegmentPaths(SEGMENT_LENGTHS.listening, rotationOffset);
}

/**
 * Generate segment paths for ending state (growing back to full)
 */
export function generateEndingSegments(): string[] {
  return generateSegmentPaths(SEGMENT_LENGTHS.ending);
}

/**
 * Calculate the arc length in SVG units for a given angle in degrees
 * 
 * @param radius - Circle radius
 * @param angleDegrees - Angle in degrees
 * @returns Arc length in SVG units
 */
export function calculateArcLength(radius: number, angleDegrees: number): number {
  return radius * (angleDegrees * Math.PI) / 180;
}

/**
 * Get stroke-dasharray values for a segment based on desired visible length
 * 
 * @param radius - Circle radius
 * @param visibleAngleDegrees - Desired visible arc length in degrees
 * @param totalAngleDegrees - Total angle allocated to this segment (72° for 5 segments)
 * @returns [dash-length, gap-length] for stroke-dasharray
 */
export function getStrokeDashArray(
  radius: number,
  visibleAngleDegrees: number,
  totalAngleDegrees: number = 72
): string {
  const visibleLength = calculateArcLength(radius, visibleAngleDegrees);
  const gapLength = calculateArcLength(radius, totalAngleDegrees - visibleAngleDegrees);
  return `${visibleLength} ${gapLength}`;
}

