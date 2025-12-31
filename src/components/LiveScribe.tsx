import { useState, useEffect, useRef, useCallback } from 'react';
import { logger } from '../lib/logger';

/**
 * LiveScribe Component
 * 
 * Provides realtime transcription using ElevenLabs Scribe Realtime API.
 * 
 * Implementation:
 * - Fetches secure single-use token from backend (/api/scribe-token)
 * - Uses WebSocket to stream audio to ElevenLabs
 * - Displays partial and committed transcripts in real-time
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

interface TranscriptSegment {
  text: string;
  isPartial: boolean;
  timestamp?: number;
}

interface LiveScribeProps {
  onTranscript?: (transcript: string) => void;
  autoStart?: boolean;
  hidden?: boolean;
  active?: boolean;
  onStatusChange?: (status: 'idle' | 'getting-token' | 'connecting' | 'connected' | 'error') => void;
  onErrorChange?: (error: string) => void;
  onPermissionChange?: (hasPermission: boolean | null) => void;
}

export default function LiveScribe({
  onTranscript,
  autoStart = false,
  hidden = false,
  active,
  onStatusChange,
  onErrorChange,
  onPermissionChange,
}: LiveScribeProps) {
  const [status, setStatus] = useState<'idle' | 'getting-token' | 'connecting' | 'connected' | 'error'>('idle');
  const [transcripts, setTranscripts] = useState<TranscriptSegment[]>([]);
  const [error, setError] = useState<string>('');
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  // Refs for WebSocket fallback
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null); // For fallback only
  const tokenRef = useRef<string | null>(null);
  const sessionReadyRef = useRef<boolean>(false); // Track if session is ready to receive audio
  const isIntentionallyStoppedRef = useRef<boolean>(false); // Track if user intentionally stopped
  const wsOpenTimeRef = useRef<number | null>(null); // Track when WebSocket opened to prevent premature cleanup

  // Note: SDK integration (@elevenlabs/react) can be added here if needed
  // Current implementation uses WebSocket for direct control and reliability

  // Cleanup function
  const cleanup = useCallback(() => {
    // Reset session ready flag
    sessionReadyRef.current = false;
    wsOpenTimeRef.current = null;
    
    // Cleanup WebSocket
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (e) {
        logger.error('Error closing WebSocket', e);
      }
      wsRef.current = null;
    }

    // Cleanup audio worklet
    if (workletNodeRef.current) {
      try {
        workletNodeRef.current.disconnect();
        workletNodeRef.current.port.close();
      } catch (e) {
        logger.error('Error disconnecting AudioWorkletNode', e);
      }
      workletNodeRef.current = null;
    }

    // Cleanup fallback processor (ScriptProcessorNode)
    if (processorRef.current) {
      try {
        processorRef.current.disconnect();
      } catch (e) {
        logger.error('Error disconnecting ScriptProcessorNode', e);
      }
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch (e) {
        logger.error('Error closing AudioContext', e);
      }
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop();
      });
      streamRef.current = null;
    }

    tokenRef.current = null;
  }, []);

  // Check microphone permission on mount
  useEffect(() => {
    checkMicrophonePermission();
    return () => {
      cleanup();
    };
  }, [cleanup]);

  useEffect(() => {
    onStatusChange?.(status);
  }, [onStatusChange, status]);

  useEffect(() => {
    onErrorChange?.(error);
  }, [onErrorChange, error]);

  useEffect(() => {
    onPermissionChange?.(hasPermission);
  }, [onPermissionChange, hasPermission]);

  // Optional external auto-start (e.g., when embedded as a hidden recorder)
  useEffect(() => {
    if (active !== undefined) return;
    if (!autoStart) return;
    if (hasPermission === false) return;
    if (status === 'idle' || status === 'error') {
      // fire and forget
      handleStart();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, hasPermission, status]);

  const checkMicrophonePermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      setHasPermission(true);
      setError('');
    } catch (err: any) {
      logger.error('Microphone permission check failed', {
        name: err.name,
        message: err.message,
        constraint: err.constraint
      });
      setHasPermission(false);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError('Microphone permission denied. Please allow microphone access.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone found. Please connect a microphone.');
      } else {
        setError('Error accessing microphone: ' + err.message);
      }
    }
  };

  const fetchToken = async (): Promise<string> => {
    try {
      const response = await fetch(`${API_URL}/api/scribe-token`);

      if (!response.ok) {
        const errorText = await response.text();
        logger.error('Token fetch failed', {
          status: response.status,
          statusText: response.statusText,
          errorText: errorText.substring(0, 200) // Limit error text length
        });
        if (response.status === 429) {
          throw new Error('Rate limit exceeded. Please wait a moment and try again.');
        }
        throw new Error(`Failed to get token: ${errorText || response.statusText}`);
      }
      const data = await response.json();
      
      // Handle different token response formats
      const token = data.token || data.signed_url || data.access_token || JSON.stringify(data);
      return token;
    } catch (err: any) {
      logger.error('Token fetch exception', err);
      throw new Error(`Token fetch failed: ${err.message}`);
    }
  };

  // WebSocket fallback implementation
  const startWebSocketStream = async (token: string) => {
    sessionReadyRef.current = false; // Reset session ready flag
    try {
      // Get microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });
      streamRef.current = stream;

      // Create audio context
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      });
      audioContextRef.current = audioContext;

      // Load AudioWorklet processor
      try {
        const workletUrl = new URL('../audio-processor.worklet.js', import.meta.url);
        await audioContext.audioWorklet.addModule(workletUrl);
      } catch (error) {
        logger.debug('Failed to load worklet from module URL, trying public directory', error);
        // Fallback: try loading from public directory if module import fails
        try {
          await audioContext.audioWorklet.addModule('/audio-processor.worklet.js');
        } catch (fallbackError) {
          logger.debug('AudioWorklet not supported, falling back to ScriptProcessorNode', fallbackError);
          // Fallback to ScriptProcessorNode if AudioWorklet fails
          return startWebSocketStreamFallback(token, stream, audioContext);
        }
      }

      // Create audio source from microphone
      const source = audioContext.createMediaStreamSource(stream);
      
      // Create AudioWorkletNode (modern, non-deprecated approach)
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      workletNodeRef.current = workletNode;

      // Set up message handler to receive processed audio data
      workletNode.port.onmessage = (event) => {
        if (event.data.type === 'audioData' && wsRef.current?.readyState === WebSocket.OPEN && sessionReadyRef.current) {
          // Convert ArrayBuffer to base64
          const int16Array = new Int16Array(event.data.data);
          const uint8Array = new Uint8Array(int16Array.buffer);
          
          // Convert to base64 (handle large arrays efficiently)
          let binaryString = '';
          for (let i = 0; i < uint8Array.length; i++) {
            binaryString += String.fromCharCode(uint8Array[i]);
          }
          const base64Audio = btoa(binaryString);
          
          // Send as JSON message (ElevenLabs API expects this format)
          const message = {
            message_type: 'input_audio_chunk',
            audio_base_64: base64Audio,
            sample_rate: 16000
          };
          wsRef.current.send(JSON.stringify(message));
        }
      };

      // Build WebSocket URL for ElevenLabs Realtime API
      const wsUrl = typeof token === 'string' && token.startsWith('wss://')
        ? token  // Token is already a signed URL
        : `wss://api.elevenlabs.io/v1/speech-to-text/realtime?token=${encodeURIComponent(token)}&model_id=scribe_v2_realtime&audio_format=pcm_16000`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // Connect audio nodes (after WebSocket is created so worklet can send data)
      source.connect(workletNode);

      ws.onopen = () => {
        wsOpenTimeRef.current = Date.now();
        logger.info('WebSocket connection opened');
        setStatus('connected');
        setError('');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const messageType = data.message_type || data.type;

          if (messageType === 'session_started') {
            logger.info('Session started - ready to receive audio', {
              session_id: data.session_id
            });
            sessionReadyRef.current = true; // Mark session as ready to receive audio
          } else if (messageType === 'partial_transcript' || messageType === 'partial_transcript_with_timestamps') {
            setTranscripts(prev => {
              // Update or add partial transcript
              const filtered = prev.filter(t => t.isPartial);
              return [...filtered, { text: data.text || data.transcript || '', isPartial: true, timestamp: Date.now() }];
            });
          } else if (messageType === 'committed_transcript' || messageType === 'committed_transcript_with_timestamps') {
            const transcriptText = data.text || data.transcript || '';
            setTranscripts(prev => {
              // Remove partials and add committed
              const filtered = prev.filter(t => !t.isPartial);
              return [...filtered, { text: transcriptText, isPartial: false, timestamp: Date.now() }];
            });
            // Call onTranscript callback if provided
            if (onTranscript && transcriptText) {
              onTranscript(transcriptText);
            }
          } else if (messageType === 'error' || messageType?.endsWith('Error')) {
            logger.error('WebSocket error message received', data);
            throw new Error(data.message || data.error || 'WebSocket error');
          }
        } catch (err: any) {
          logger.error('Error parsing WebSocket message', {
            error: err,
            rawData: typeof event.data === 'string' ? event.data.substring(0, 200) : 'binary data'
          });
        }
      };

      ws.onerror = (event) => {
        logger.error('WebSocket error event', event);
        setError('Connection error. Token may have expired. Please try again.');
        setStatus('error');
        cleanup();
      };

      ws.onclose = (event) => {
        const timeSinceOpen = wsOpenTimeRef.current ? Date.now() - wsOpenTimeRef.current : null;
        
        // Only cleanup if not intentionally stopped (user will call cleanup)
        if (!isIntentionallyStoppedRef.current) {
          // If WebSocket closed very quickly after opening (less than 500ms), it's likely a connection issue
          if (timeSinceOpen !== null && timeSinceOpen < 500) {
            logger.error('WebSocket closed immediately after opening (possible connection issue)', {
              code: event.code,
              timeSinceOpen,
              wasClean: event.wasClean
            });
            if (event.code === 1005) {
              setError('Connection failed immediately. The token may be invalid or the server rejected the connection. Please try again.');
            } else if (event.code === 1008) {
              setError('Token expired or invalid. Please try again.');
            } else {
              setError('Connection closed immediately. Please check your network connection and try again.');
            }
            setStatus('error');
            cleanup();
          } else if (event.code !== 1000) {
            // Not a normal closure - unexpected error
            if (event.code === 1008) {
              // Policy violation - likely expired token
              logger.error('WebSocket closed: Policy violation (likely expired token)', event);
              setError('Token expired. Please try again.');
            } else if (event.code === 1005) {
              logger.error('WebSocket closed without status code', event);
              setError('Connection lost unexpectedly. Please try again.');
            } else {
              logger.error('WebSocket closed unexpectedly', event);
              setError(`Connection closed unexpectedly (code: ${event.code}). Please try again.`);
            }
            setStatus('error');
            cleanup();
          } else {
            // Normal closure but unexpected - might be server-side
            logger.warn('WebSocket closed normally (unexpected)');
            setError('Connection closed by server. Please try again.');
            setStatus('error');
            cleanup();
          }
        } else {
          setStatus('idle');
        }
        wsOpenTimeRef.current = null;
      };

    } catch (err: any) {
      logger.error('WebSocket stream error', err);
      setError(err.message || 'Failed to start audio stream');
      setStatus('error');
      cleanup();
    }
  };

  // Fallback implementation using ScriptProcessorNode (deprecated but widely supported)
  const startWebSocketStreamFallback = async (
    token: string,
    stream: MediaStream,
    audioContext: AudioContext
  ) => {
    logger.debug('Using ScriptProcessorNode fallback (AudioWorklet not available)');
    try {
      // Create audio source from microphone
      const source = audioContext.createMediaStreamSource(stream);
      
      // Fallback: Use ScriptProcessorNode (deprecated but works everywhere)
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor as any;

      // Connect audio nodes
      source.connect(processor);
      processor.connect(audioContext.destination);

      // Build WebSocket URL
      const wsUrl = typeof token === 'string' && token.startsWith('wss://')
        ? token
        : `wss://api.elevenlabs.io/v1/speech-to-text/realtime?token=${encodeURIComponent(token)}&model_id=scribe_v2_realtime&audio_format=pcm_16000`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        wsOpenTimeRef.current = Date.now();
        logger.info('WebSocket opened successfully (fallback)');
        setStatus('connected');
        setError('');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const messageType = data.message_type || data.type;

          if (messageType === 'session_started') {
            logger.info('Session started - ready to receive audio (fallback)', {
              session_id: data.session_id
            });
            sessionReadyRef.current = true; // Mark session as ready to receive audio
          } else if (messageType === 'partial_transcript' || messageType === 'partial_transcript_with_timestamps') {
            setTranscripts(prev => {
              const filtered = prev.filter(t => t.isPartial);
              return [...filtered, { text: data.text || data.transcript || '', isPartial: true, timestamp: Date.now() }];
            });
          } else if (messageType === 'committed_transcript' || messageType === 'committed_transcript_with_timestamps') {
            const transcriptText = data.text || data.transcript || '';
            setTranscripts(prev => {
              const filtered = prev.filter(t => !t.isPartial);
              return [...filtered, { text: transcriptText, isPartial: false, timestamp: Date.now() }];
            });
            // Call onTranscript callback if provided
            if (onTranscript && transcriptText) {
              onTranscript(transcriptText);
            }
          } else if (messageType === 'error' || messageType?.endsWith('Error')) {
            logger.error('WebSocket error message received (fallback)', data);
            throw new Error(data.message || data.error || 'WebSocket error');
          }
        } catch (err: any) {
          logger.error('Error parsing WebSocket message (fallback)', err);
        }
      };

      ws.onerror = (event) => {
        logger.error('WebSocket error event (fallback)', event);
        setError('Connection error. Token may have expired. Please try again.');
        setStatus('error');
        cleanup();
      };

      ws.onclose = (event) => {
        const timeSinceOpen = wsOpenTimeRef.current ? Date.now() - wsOpenTimeRef.current : null;
        
        // Only cleanup if not intentionally stopped (user will call cleanup)
        if (!isIntentionallyStoppedRef.current) {
          // If WebSocket closed very quickly after opening (less than 500ms), it's likely a connection issue
          if (timeSinceOpen !== null && timeSinceOpen < 500) {
            logger.error('WebSocket closed immediately after opening (possible connection issue, fallback)', {
              code: event.code,
              timeSinceOpen,
              wasClean: event.wasClean
            });
            if (event.code === 1005) {
              setError('Connection failed immediately. The token may be invalid or the server rejected the connection. Please try again.');
            } else if (event.code === 1008) {
              setError('Token expired or invalid. Please try again.');
            } else {
              setError('Connection closed immediately. Please check your network connection and try again.');
            }
            setStatus('error');
            cleanup();
          } else if (event.code !== 1000) {
            // Not a normal closure - unexpected error
            if (event.code === 1008) {
              logger.error('WebSocket closed: Policy violation (fallback)', event);
              setError('Token expired. Please try again.');
            } else if (event.code === 1005) {
              logger.error('WebSocket closed without status code (fallback)', event);
              setError('Connection lost unexpectedly. Please try again.');
            } else {
              logger.error('WebSocket closed unexpectedly (fallback)', event);
              setError(`Connection closed unexpectedly (code: ${event.code}). Please try again.`);
            }
            setStatus('error');
            cleanup();
          } else {
            // Normal closure but unexpected - might be server-side
            logger.warn('WebSocket closed normally (unexpected, fallback)');
            setError('Connection closed by server. Please try again.');
            setStatus('error');
            cleanup();
          }
        } else {
          setStatus('idle');
        }
        wsOpenTimeRef.current = null;
      };

      // Process audio chunks (deprecated ScriptProcessorNode approach)
      processor.onaudioprocess = (e) => {
        if (ws.readyState === WebSocket.OPEN && sessionReadyRef.current) {
          const inputData = e.inputBuffer.getChannelData(0);
          // Convert Float32Array to Int16Array (s16le format)
          const int16Data = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            // Clamp and convert to int16
            const s = Math.max(-1, Math.min(1, inputData[i]));
            int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          
          // Convert to base64
          const uint8Array = new Uint8Array(int16Data.buffer);
          
          // Convert to base64 (handle large arrays efficiently)
          let binaryString = '';
          for (let i = 0; i < uint8Array.length; i++) {
            binaryString += String.fromCharCode(uint8Array[i]);
          }
          const base64Audio = btoa(binaryString);
          
          // Send as JSON message (ElevenLabs API expects this format)
          const message = {
            message_type: 'input_audio_chunk',
            audio_base_64: base64Audio,
            sample_rate: 16000
          };
          ws.send(JSON.stringify(message));
        }
      };

    } catch (err: any) {
      logger.error('WebSocket stream error (fallback)', err);
      setError(err.message || 'Failed to start audio stream');
      setStatus('error');
      cleanup();
    }
  };

  // Note: SDK-based implementation can be added here using @elevenlabs/react
  // Example:
  // const scribe = useScribe({ modelId: 'scribe_v2_realtime' });
  // await scribe.connect({ token, microphone: { echoCancellation: true } });
  // scribe.on('partial_transcript', ...);
  // scribe.on('committed_transcript', ...);

  const handleStart = async () => {
    isIntentionallyStoppedRef.current = false; // Reset intentional stop flag
    try {
      setError('');
      setStatus('getting-token');

      // Fetch token from server
      const token = await fetchToken();
      tokenRef.current = token;

      setStatus('connecting');

      // Use WebSocket implementation
      await startWebSocketStream(token);
      logger.info('Transcription started successfully');
    } catch (err: any) {
      logger.error('Start error', err);
      setError(err.message || 'Failed to start transcription');
      setStatus('error');
      cleanup();
    }
  };

  const handleStop = () => {
    isIntentionallyStoppedRef.current = true; // Mark as intentional stop
    cleanup();
    setStatus('idle');
  };

  // Controlled mode: start/stop based on `active` prop (used for subtle record buttons)
  useEffect(() => {
    if (active === undefined) return;
    if (active) {
      if (hasPermission === false) return;
      if (status === 'idle' || status === 'error') {
        handleStart();
      }
      return;
    }
    // active === false
    if (status !== 'idle') {
      handleStop();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, hasPermission, status]);

  const handleClear = () => {
    setTranscripts([]);
  };

  const requestMicrophoneAccess = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      setHasPermission(true);
      setError('');
    } catch (err: any) {
      logger.error('Failed to access microphone via user request', err);
      setHasPermission(false);
      setError('Failed to access microphone: ' + err.message);
    }
  };

  // Render permission denied UI
  if (hasPermission === false && error) {
    if (hidden) return null;
    return (
      <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
        <div className="text-center">
          <div className="mb-4">
            <svg
              className="mx-auto h-12 w-12 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-white mb-2">Microphone Access Required</h3>
          <p className="text-sm text-neutral-300 mb-4">{error}</p>
          <button
            onClick={requestMicrophoneAccess}
            className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium"
          >
            Request Access
          </button>
        </div>
      </div>
    );
  }

  if (hidden) {
    return null;
  }

  return (
    <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Live Scribe Transcription</h3>
        <div className="flex items-center gap-2">
          {status === 'connected' && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-emerald-200 font-medium">Connected</span>
            </div>
          )}
          {status === 'connecting' && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-amber-200 font-medium">Connecting...</span>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl mb-4">
          {error}
        </div>
      )}

      {/* Status info */}
      <div className="mb-4 text-sm text-neutral-300">
        Status: <span className="font-medium">{status}</span>
        <span className="ml-2 text-xs text-neutral-400">(WebSocket connection)</span>
      </div>

      {/* Controls */}
      <div className="flex gap-4 mb-6">
        {status === 'idle' || status === 'error' ? (
          <button
            onClick={handleStart}
            disabled={hasPermission === false}
            className="flex-1 px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors text-sm font-medium"
          >
            <svg
              className="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z"
                clipRule="evenodd"
              />
            </svg>
            Start Transcription
          </button>
        ) : (
          <button
            onClick={handleStop}
            className="flex-1 px-4 py-2 bg-red-500/20 text-red-200 border border-red-500/30 rounded-xl hover:bg-red-500/25 flex items-center justify-center gap-2 transition-colors text-sm font-medium"
          >
            <svg
              className="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z"
                clipRule="evenodd"
              />
            </svg>
            Stop Transcription
          </button>
        )}
      </div>

      {/* Transcript Display */}
      <div className="border-t border-white/10 pt-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-white/80">Transcript</h4>
          {transcripts.length > 0 && (
            <button
              onClick={handleClear}
              className="text-xs text-neutral-400 hover:text-neutral-200 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
        <div className="bg-neutral-950 border border-neutral-800 rounded-2xl p-4 max-h-96 overflow-y-auto">
          {transcripts.length === 0 ? (
            <p className="text-sm text-neutral-400 italic">No transcript yet. Click Start and speak into your microphone.</p>
          ) : (
            <div className="space-y-2">
              {transcripts.map((segment, index) => (
                <div
                  key={index}
                  className={`text-sm ${
                    segment.isPartial
                      ? 'text-neutral-400 italic'
                      : 'text-neutral-100 font-medium'
                  }`}
                >
                  {segment.isPartial && <span className="text-xs text-neutral-500">[partial] </span>}
                  {segment.text}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

