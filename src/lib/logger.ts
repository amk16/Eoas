/**
 * Logger utility with environment-based logging levels
 * 
 * Logging levels:
 * - debug: Detailed flow information (only in development)
 * - info: Important state changes (conversation created, session started, etc.)
 * - warn: Warning messages
 * - error: Error messages (always logged)
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  level: LogLevel;
  message: string;
  data?: unknown;
  timestamp: string;
}

class Logger {
  private isDevelopment: boolean;
  private minLevel: LogLevel;

  constructor() {
    this.isDevelopment = import.meta.env.DEV || import.meta.env.MODE === 'development';
    // In production, only show warn and error
    // In development, show all levels
    this.minLevel = this.isDevelopment ? 'debug' : 'warn';
  }

  private shouldLog(level: LogLevel): boolean {
    const levels: LogLevel[] = ['debug', 'info', 'warn', 'error'];
    const currentLevelIndex = levels.indexOf(level);
    const minLevelIndex = levels.indexOf(this.minLevel);
    return currentLevelIndex >= minLevelIndex;
  }

  private formatMessage(level: LogLevel, message: string, data?: unknown): LogEntry {
    return {
      level,
      message,
      data,
      timestamp: new Date().toISOString(),
    };
  }

  private log(level: LogLevel, message: string, data?: unknown): void {
    if (!this.shouldLog(level)) {
      return;
    }

    const logEntry = this.formatMessage(level, message, data);

    // Use appropriate console method based on level
    switch (level) {
      case 'debug':
        if (this.isDevelopment) {
          console.debug(`[DEBUG] ${message}`, data || '');
        }
        break;
      case 'info':
        console.info(`[INFO] ${message}`, data || '');
        break;
      case 'warn':
        console.warn(`[WARN] ${message}`, data || '');
        break;
      case 'error':
        console.error(`[ERROR] ${message}`, data || '');
        break;
    }

    // In development, also log structured entry for debugging
    if (this.isDevelopment && level === 'debug') {
      console.debug('Log entry:', logEntry);
    }
  }

  debug(message: string, data?: unknown): void {
    this.log('debug', message, data);
  }

  info(message: string, data?: unknown): void {
    this.log('info', message, data);
  }

  warn(message: string, data?: unknown): void {
    this.log('warn', message, data);
  }

  error(message: string, data?: unknown): void {
    this.log('error', message, data);
  }
}

// Export singleton instance
export const logger = new Logger();

// Export type for use in other files if needed
export type { LogLevel };

