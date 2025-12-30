import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * LiveScribeSilence Component
 * 
 * Enhanced version of LiveScribe with improved silence detection.
 * 
 * Features:
 * - Configures ElevenLabs VAD parameters to reduce silence threshold
 * - Tracks partial transcripts to detect speech completion faster
 * 
 * Implementation:
 * - Fetches secure single-use token from backend (/api/scribe-token)
 * - Uses WebSocket to stream audio to ElevenLabs
 * - Sends configuration message after session_started to reduce silence threshold
 * - Displays partial and committed transcripts in real-time
 * 
 * Note: @elevenlabs/react SDK integration can be added for enhanced features.
 * Current implementation uses direct WebSocket connection for reliability.
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

interface TranscriptSegment {
  text: string;
  isPartial: boolean;
  timestamp?: number;
}

interface LiveScribeSilenceProps {
  onTranscript?: (transcript: string) => void;
  autoStart?: boolean;
  hidden?: boolean;
  active?: boolean;
  onStatusChange?: (status: 'idle' | 'getting-token' | 'connecting' | 'connected' | 'error') => void;
  onErrorChange?: (error: string) => void;
  onPermissionChange?: (hasPermission: boolean | null) => void;
  onSilenceDetected?: (transcript: string) => void;
}

export default function LiveScribeSilence({
  onTranscript,
  autoStart = false,
  hidden = false,
  active,
  onStatusChange,
  onErrorChange,
  onPermissionChange,
  onSilenceDetected,
}: LiveScribeSilenceProps) {
  const [status, setStatus] = useState<'idle' | 'getting-token' | 'connecting' | 'connected' | 'error'>('idle');
  const [transcripts, setTranscripts] = useState<TranscriptSegment[]>([]);
  const [error, setError] = useState<string>('');
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  // Logging helper
  const log = (message: string, data?: any) => {
    console.log(`[LiveScribeSilence] ${message}`, data || '');
  };

  const logError = (message: string, error: any) => {
    console.error(`[LiveScribeSilence] ERROR: ${message}`, error);
  };

  const logState = (newStatus: typeof status) => {
    log(`Status changed: ${status} -> ${newStatus}`);
  };

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
  const configSentRef = useRef<boolean>(false); // Track if configuration has been sent
  const partialTranscriptsRef = useRef<string[]>([]); // Track last 3 partial transcripts for silence detection
  const lastTriggeredSilenceRef = useRef<string>(''); 

  // Note: SDK integration (@elevenlabs/react) can be added here if needed
  // Current implementation uses WebSocket for direct control and reliability

  // Check if 3 consecutive partial transcripts are identical (indicating silence/user finished speaking)
  const checkPartialTranscriptPattern = (newPartialTranscript: string) => {
    // 1. Reset lock if text has changed significantly
    if (newPartialTranscript !== lastTriggeredSilenceRef.current) {
      // FIX: Use Math.abs (Capital M)
      if (Math.abs(newPartialTranscript.length - lastTriggeredSilenceRef.current.length) > 5) {
        lastTriggeredSilenceRef.current = '';
      }
    }

    // Add to buffer
    partialTranscriptsRef.current.push(newPartialTranscript);
    
    // Keep buffer at 3
    if (partialTranscriptsRef.current.length > 3) {
      partialTranscriptsRef.current.shift();
    }
    
    // Check for pattern
    if (partialTranscriptsRef.current.length === 3) {
      const allSame = partialTranscriptsRef.current.every(t => t === partialTranscriptsRef.current[0]);
      
      if (allSame) {
        const detectedText = partialTranscriptsRef.current[0];
        
        // Check lock
        if (detectedText === lastTriggeredSilenceRef.current) {
          return;
        }
        
        log('Silence pattern detected: 3 identical partial transcripts', {
          transcript: detectedText,
          count: 3
        });

        // Set lock
        lastTriggeredSilenceRef.current = detectedText;
        
        // Reset tracking array
        partialTranscriptsRef.current = [];
        
        // Call callback
        if (onSilenceDetected) {
          log('Calling onSilenceDetected callback');
          onSilenceDetected(detectedText);
        }
      }
    }
  };

  // Cleanup function
  const cleanup = useCallback(() => {
    log('Starting cleanup...');
    
    // Reset session ready flag
    sessionReadyRef.current = false;
    wsOpenTimeRef.current = null;
    configSentRef.current = false;
    partialTranscriptsRef.current = []; // Reset partial transcript tracking
    
    // Cleanup WebSocket
    if (wsRef.current) {
      try {
        log(`Closing WebSocket (state: ${wsRef.current.readyState})`);
        wsRef.current.close();
      } catch (e) {
        logError('Error closing WebSocket', e);
      }
      wsRef.current = null;
    }

    // Cleanup audio worklet
    if (workletNodeRef.current) {
      try {
        log('Disconnecting AudioWorkletNode');
        workletNodeRef.current.disconnect();
        workletNodeRef.current.port.close();
      } catch (e) {
        logError('Error disconnecting AudioWorkletNode', e);
      }
      workletNodeRef.current = null;
    }

    // Cleanup fallback processor (ScriptProcessorNode)
    if (processorRef.current) {
      try {
        log('Disconnecting ScriptProcessorNode (fallback)');
        processorRef.current.disconnect();
      } catch (e) {
        logError('Error disconnecting ScriptProcessorNode', e);
      }
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      try {
        log(`Closing AudioContext (state: ${audioContextRef.current.state})`);
        audioContextRef.current.close();
      } catch (e) {
        logError('Error closing AudioContext', e);
      }
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      log(`Stopping ${streamRef.current.getTracks().length} media stream tracks`);
      streamRef.current.getTracks().forEach(track => {
        log(`Stopping track: ${track.kind} (id: ${track.id}, enabled: ${track.enabled})`);
        track.stop();
      });
      streamRef.current = null;
    }

    tokenRef.current = null;
    log('Cleanup completed');
  }, []);

  // Check microphone permission on mount
  useEffect(() => {
    log('Component mounted, checking microphone permission');
    checkMicrophonePermission();
    return () => {
      log('Component unmounting, running cleanup');
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
    log('Checking microphone permission...');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      log('Microphone permission granted', {
        tracks: stream.getTracks().map(t => ({ id: t.id, kind: t.kind, enabled: t.enabled }))
      });
      stream.getTracks().forEach(track => track.stop());
      setHasPermission(true);
      setError('');
    } catch (err: any) {
      logError('Microphone permission check failed', {
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
    log(`Fetching token from ${API_URL}/api/scribe-token`);
    try {
      const startTime = Date.now();
      const response = await fetch(`${API_URL}/api/scribe-token`);
      const fetchTime = Date.now() - startTime;
      
      log(`Token fetch response received (${fetchTime}ms)`, {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok
      });

      if (!response.ok) {
        const errorText = await response.text();
        logError('Token fetch failed', {
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
      log('Token response received', {
        hasToken: !!data.token,
        hasSignedUrl: !!data.signed_url,
        hasAccessToken: !!data.access_token,
        keys: Object.keys(data)
      });
      
      // Handle different token response formats
      const token = data.token || data.signed_url || data.access_token || JSON.stringify(data);
      const tokenPreview = typeof token === 'string' && token.length > 50 
        ? `${token.substring(0, 50)}...` 
        : token;
      log(`Token extracted (length: ${typeof token === 'string' ? token.length : 'N/A'}, preview: ${tokenPreview})`);
      return token;
    } catch (err: any) {
      logError('Token fetch exception', err);
      throw new Error(`Token fetch failed: ${err.message}`);
    }
  };

  // Send configuration message to ElevenLabs to reduce silence threshold
  const sendConfiguration = (ws: WebSocket) => {
    if (configSentRef.current) {
      log('Configuration already sent, skipping');
      return;
    }

    log('Sending configuration message to reduce silence threshold');
    try {
      // Configure VAD parameters to reduce silence threshold
      // Based on ElevenLabs API documentation, try different parameter formats
      const configMessage = {
        message_type: 'set_config',
        config: {
          vad_silence_threshold_secs: 0.5, // Reduced from default (try 0.5 seconds)
          commit_strategy: 'vad',
        }
      };

      log('Sending config message:', configMessage);
      ws.send(JSON.stringify(configMessage));
      configSentRef.current = true;
      log('Configuration message sent successfully');
    } catch (err: any) {
      logError('Failed to send configuration message', err);
      // Don't fail the connection if config fails - it's optional
    }
  };

  // WebSocket fallback implementation
  const startWebSocketStream = async (token: string) => {
    log('Starting WebSocket stream with AudioWorklet');
    sessionReadyRef.current = false; // Reset session ready flag
    configSentRef.current = false; // Reset config sent flag
    try {
      // Get microphone stream
      log('Requesting microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });
      log('Microphone stream obtained', {
        tracks: stream.getTracks().map(t => ({
          id: t.id,
          kind: t.kind,
          enabled: t.enabled,
          muted: t.muted,
          readyState: t.readyState
        }))
      });
      streamRef.current = stream;

      // Create audio context
      log('Creating AudioContext (sampleRate: 16000)');
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000,
      });
      log(`AudioContext created (state: ${audioContext.state}, sampleRate: ${audioContext.sampleRate})`);
      audioContextRef.current = audioContext;

      // Load AudioWorklet processor
      log('Loading AudioWorklet processor...');
      try {
        const workletUrl = new URL('../audio-processor.worklet.js', import.meta.url);
        log(`Attempting to load worklet from: ${workletUrl.href}`);
        await audioContext.audioWorklet.addModule(workletUrl);
        log('AudioWorklet module loaded successfully');
      } catch (error) {
        logError('Failed to load worklet from module URL, trying public directory', error);
        // Fallback: try loading from public directory if module import fails
        try {
          log('Attempting to load worklet from /audio-processor.worklet.js');
          await audioContext.audioWorklet.addModule('/audio-processor.worklet.js');
          log('AudioWorklet module loaded from public directory');
        } catch (fallbackError) {
          logError('AudioWorklet not supported, falling back to ScriptProcessorNode', fallbackError);
          // Fallback to ScriptProcessorNode if AudioWorklet fails
          return startWebSocketStreamFallback(token, stream, audioContext);
        }
      }

      // Create audio source from microphone
      log('Creating MediaStreamSource');
      const source = audioContext.createMediaStreamSource(stream);
      
      // Create AudioWorkletNode (modern, non-deprecated approach)
      log('Creating AudioWorkletNode');
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      workletNodeRef.current = workletNode;
      log('AudioWorkletNode created', {
        numberOfInputs: workletNode.numberOfInputs,
        numberOfOutputs: workletNode.numberOfOutputs,
        channelCount: workletNode.channelCount
      });

      // Set up message handler to receive processed audio data
      let audioChunkCount = 0;
      workletNode.port.onmessage = (event) => {
        if (event.data.type === 'audioData' && wsRef.current?.readyState === WebSocket.OPEN && sessionReadyRef.current) {
          audioChunkCount++;
          if (audioChunkCount % 100 === 0) {
            log(`Sent ${audioChunkCount} audio chunks to WebSocket`);
          }
          
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
        } else if (event.data.type === 'audioData') {
          if (!sessionReadyRef.current) {
            // Silently drop audio until session is ready
            if (audioChunkCount === 0) {
              log('Audio data received but session not ready yet');
            }
          } else {
            log(`Audio data received but WebSocket not ready (state: ${wsRef.current?.readyState})`);
          }
        }
      };

      // Build WebSocket URL for ElevenLabs Realtime API
      // Note: Adjust the URL format based on actual ElevenLabs API documentation
      // The token format may vary - it could be a signed URL or a token string
      // Common formats:
      // - wss://api.elevenlabs.io/v1/speech-to-text/realtime?token=...
      // - wss://api.elevenlabs.io/v1/realtime/... (check ElevenLabs docs)
      // If token is a signed URL, use it directly; otherwise construct the URL
      const wsUrl = typeof token === 'string' && token.startsWith('wss://')
        ? token  // Token is already a signed URL
        : `wss://api.elevenlabs.io/v1/speech-to-text/realtime?token=${encodeURIComponent(token)}&model_id=scribe_v2_realtime&audio_format=pcm_16000`;
      
      log('Connecting to WebSocket', {
        url: wsUrl.substring(0, 100) + '...', // Don't log full URL with token
        isSignedUrl: typeof token === 'string' && token.startsWith('wss://')
      });

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // Connect audio nodes (after WebSocket is created so worklet can send data)
      log('Connecting audio nodes');
      source.connect(workletNode);

      ws.onopen = () => {
        wsOpenTimeRef.current = Date.now();
        log('WebSocket opened successfully');
        setStatus('connected');
        setError('');
        // Note: ElevenLabs Realtime API should automatically send session_started message
        // Configuration will be sent after session_started is received
      };

      let messageCount = 0;
      ws.onmessage = (event) => {
        messageCount++;
        try {
          const data = JSON.parse(event.data);
          const messageType = data.message_type || data.type;
          
          if (messageCount === 1) {
            log('First WebSocket message received', data);
          }
          
          if (messageCount % 10 === 0) {
            log(`Received ${messageCount} WebSocket messages`);
          }

          if (messageType === 'session_started') {
            log('Session started - ready to receive audio', {
              session_id: data.session_id,
              config: data.config
            });
            sessionReadyRef.current = true; // Mark session as ready to receive audio
            
            // Send configuration message to reduce silence threshold
            sendConfiguration(ws);
          } else if (messageType === 'partial_transcript' || messageType === 'partial_transcript_with_timestamps') {
            const partialText = data.text || data.transcript || '';
            if(lastTriggeredSilenceRef.current){
                return;
            }
            log(`Partial transcript received: "${partialText}"`);
            
            // Update UI transcripts
            setTranscripts(prev => {
              // Update or add partial transcript
              const filtered = prev.filter(t => t.isPartial);
              return [...filtered, { text: partialText, isPartial: true, timestamp: Date.now() }];
            });
            
            // Check for silence pattern (3 identical partial transcripts)
            if (partialText.trim()) {
              checkPartialTranscriptPattern(partialText);
            }
          } else if (messageType === 'committed_transcript' || messageType === 'committed_transcript_with_timestamps') {
            lastTriggeredSilenceRef.current = '';
            // Reset partial transcript tracking when we get a committed transcript
            // (user has finished speaking, new speech will start)
            if (partialTranscriptsRef.current.length > 0) {
              log('Committed transcript received - resetting partial transcript tracking');
              partialTranscriptsRef.current = [];
            }
            lastTriggeredSilenceRef.current = ''; 
            log(`Committed transcript received: "${data.text || data.transcript}"`);
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
          } else if (messageType === 'config_updated' || messageType === 'config_set') {
            log('Configuration update received from server', data);
          } else if (messageType === 'error' || messageType?.endsWith('Error')) {
            logError('WebSocket error message received', data);
            throw new Error(data.message || data.error || 'WebSocket error');
          } else {
            log(`Unknown message type: ${messageType}`, data);
          }
        } catch (err: any) {
          logError('Error parsing WebSocket message', {
            error: err,
            rawData: typeof event.data === 'string' ? event.data.substring(0, 200) : 'binary data'
          });
        }
      };

      ws.onerror = (event) => {
        logError('WebSocket error event', event);
        setError('Connection error. Token may have expired. Please try again.');
        setStatus('error');
        cleanup();
      };

      ws.onclose = (event) => {
        const timeSinceOpen = wsOpenTimeRef.current ? Date.now() - wsOpenTimeRef.current : null;
        log('WebSocket closed', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          timeSinceOpen: timeSinceOpen ? `${timeSinceOpen}ms` : 'unknown'
        });
        
        // Only cleanup if not intentionally stopped (user will call cleanup)
        if (!isIntentionallyStoppedRef.current) {
          // If WebSocket closed very quickly after opening (less than 500ms), it's likely a connection issue
          if (timeSinceOpen !== null && timeSinceOpen < 500) {
            logError('WebSocket closed immediately after opening (possible connection issue)', {
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
              logError('WebSocket closed: Policy violation (likely expired token)', event);
              setError('Token expired. Please try again.');
            } else if (event.code === 1005) {
              logError('WebSocket closed without status code', event);
              setError('Connection lost unexpectedly. Please try again.');
            } else {
              logError('WebSocket closed unexpectedly', event);
              setError(`Connection closed unexpectedly (code: ${event.code}). Please try again.`);
            }
            setStatus('error');
            cleanup();
          } else {
            // Normal closure but unexpected - might be server-side
            log('WebSocket closed normally (unexpected)');
            setError('Connection closed by server. Please try again.');
            setStatus('error');
            cleanup();
          }
        } else {
          log('WebSocket closed (intentional stop)');
          setStatus('idle');
        }
        wsOpenTimeRef.current = null;
      };

    } catch (err: any) {
      console.error('WebSocket stream error:', err);
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
    log('Using ScriptProcessorNode fallback (AudioWorklet not available)');
    try {
      // Create audio source from microphone
      const source = audioContext.createMediaStreamSource(stream);
      
      // Fallback: Use ScriptProcessorNode (deprecated but works everywhere)
      log('Creating ScriptProcessorNode (bufferSize: 4096)');
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor as any;

      // Connect audio nodes
      log('Connecting audio nodes (fallback)');
      source.connect(processor);
      processor.connect(audioContext.destination);

      // Build WebSocket URL
      const wsUrl = typeof token === 'string' && token.startsWith('wss://')
        ? token
        : `wss://api.elevenlabs.io/v1/speech-to-text/realtime?token=${encodeURIComponent(token)}&model_id=scribe_v2_realtime&audio_format=pcm_16000`;

      log('Connecting to WebSocket (fallback)', {
        url: wsUrl.substring(0, 100) + '...'
      });

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        wsOpenTimeRef.current = Date.now();
        log('WebSocket opened successfully (fallback)');
        setStatus('connected');
        setError('');
        // Note: ElevenLabs Realtime API should automatically send session_started message
        // Configuration will be sent after session_started is received
      };

      let messageCount = 0;
      ws.onmessage = (event) => {
        messageCount++;
        try {
          const data = JSON.parse(event.data);
          const messageType = data.message_type || data.type;

          if (messageCount === 1) {
            log('First WebSocket message received (fallback)', data);
          }

          if (messageType === 'session_started') {
            log('Session started - ready to receive audio (fallback)', {
              session_id: data.session_id,
              config: data.config
            });
            sessionReadyRef.current = true; // Mark session as ready to receive audio
            
            // Send configuration message to reduce silence threshold
            sendConfiguration(ws);
          } else if (messageType === 'partial_transcript' || messageType === 'partial_transcript_with_timestamps') {
            const partialText = data.text || data.transcript || '';
            log(`Partial transcript received (fallback): "${partialText}"`);
            
            // Update UI transcripts
            setTranscripts(prev => {
              const filtered = prev.filter(t => t.isPartial);
              return [...filtered, { text: partialText, isPartial: true, timestamp: Date.now() }];
            });
            
            // Check for silence pattern (3 identical partial transcripts)
            if (partialText.trim()) {
              checkPartialTranscriptPattern(partialText);
            }
          } else if (messageType === 'committed_transcript' || messageType === 'committed_transcript_with_timestamps') {
            // Reset partial transcript tracking when we get a committed transcript
            // (user has finished speaking, new speech will start)
            if (partialTranscriptsRef.current.length > 0) {
              log('Committed transcript received (fallback) - resetting partial transcript tracking');
              partialTranscriptsRef.current = [];
            }
            log(`Committed transcript received (fallback): "${data.text || data.transcript}"`);
            const transcriptText = data.text || data.transcript || '';
            setTranscripts(prev => {
              const filtered = prev.filter(t => !t.isPartial);
              return [...filtered, { text: transcriptText, isPartial: false, timestamp: Date.now() }];
            });
            // Call onTranscript callback if provided
            if (onTranscript && transcriptText) {
              onTranscript(transcriptText);
            }
          } else if (messageType === 'config_updated' || messageType === 'config_set') {
            log('Configuration update received from server (fallback)', data);
          } else if (messageType === 'error' || messageType?.endsWith('Error')) {
            logError('WebSocket error message received (fallback)', data);
            throw new Error(data.message || data.error || 'WebSocket error');
          } else {
            log(`Unknown message type (fallback): ${messageType}`, data);
          }
        } catch (err: any) {
          logError('Error parsing WebSocket message (fallback)', err);
        }
      };

      ws.onerror = (event) => {
        logError('WebSocket error event (fallback)', event);
        setError('Connection error. Token may have expired. Please try again.');
        setStatus('error');
        cleanup();
      };

      ws.onclose = (event) => {
        const timeSinceOpen = wsOpenTimeRef.current ? Date.now() - wsOpenTimeRef.current : null;
        log('WebSocket closed (fallback)', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          timeSinceOpen: timeSinceOpen ? `${timeSinceOpen}ms` : 'unknown'
        });
        
        // Only cleanup if not intentionally stopped (user will call cleanup)
        if (!isIntentionallyStoppedRef.current) {
          // If WebSocket closed very quickly after opening (less than 500ms), it's likely a connection issue
          if (timeSinceOpen !== null && timeSinceOpen < 500) {
            logError('WebSocket closed immediately after opening (possible connection issue, fallback)', {
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
              logError('WebSocket closed: Policy violation (fallback)', event);
              setError('Token expired. Please try again.');
            } else if (event.code === 1005) {
              logError('WebSocket closed without status code (fallback)', event);
              setError('Connection lost unexpectedly. Please try again.');
            } else {
              logError('WebSocket closed unexpectedly (fallback)', event);
              setError(`Connection closed unexpectedly (code: ${event.code}). Please try again.`);
            }
            setStatus('error');
            cleanup();
          } else {
            // Normal closure but unexpected - might be server-side
            log('WebSocket closed normally (unexpected, fallback)');
            setError('Connection closed by server. Please try again.');
            setStatus('error');
            cleanup();
          }
        } else {
          log('WebSocket closed (intentional stop, fallback)');
          setStatus('idle');
        }
        wsOpenTimeRef.current = null;
      };

      // Process audio chunks (deprecated ScriptProcessorNode approach)
      let audioChunkCount = 0;
      processor.onaudioprocess = (e) => {
        if (ws.readyState === WebSocket.OPEN && sessionReadyRef.current) {
          audioChunkCount++;
          if (audioChunkCount % 100 === 0) {
            log(`Processed ${audioChunkCount} audio chunks (fallback)`);
          }
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
      logError('WebSocket stream error (fallback)', err);
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
    log('=== Starting transcription ===');
    isIntentionallyStoppedRef.current = false; // Reset intentional stop flag
    try {
      setError('');
      logState(status);
      setStatus('getting-token');

      // Fetch token from server
      const token = await fetchToken();
      tokenRef.current = token;

      logState('getting-token');
      setStatus('connecting');

      // Use WebSocket implementation
      // Note: To use @elevenlabs/react SDK instead, integrate useScribe hook properly
      await startWebSocketStream(token);
      log('=== Transcription started successfully ===');
    } catch (err: any) {
      logError('Start error', err);
      setError(err.message || 'Failed to start transcription');
      setStatus('error');
      cleanup();
    }
  };

  const handleStop = () => {
    log('=== Stopping transcription ===');
    isIntentionallyStoppedRef.current = true; // Mark as intentional stop
    cleanup();
    setStatus('idle');
    log('=== Transcription stopped ===');
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
    log(`Clearing ${transcripts.length} transcript segments`);
    setTranscripts([]);
  };

  const requestMicrophoneAccess = async () => {
    log('User requested microphone access');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      log('Microphone access granted via user request');
      stream.getTracks().forEach(track => track.stop());
      setHasPermission(true);
      setError('');
    } catch (err: any) {
      logError('Failed to access microphone via user request', err);
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
        <span className="ml-2 text-xs text-neutral-400">(WebSocket connection with silence detection)</span>
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

