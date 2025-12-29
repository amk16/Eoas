import { useState, useEffect, useRef, useMemo } from 'react';
import { EnhancedResponse } from './voice-assistant/EnhancedResponse';
import { chatWithIoun } from '../services/iounService';
import { useAuth } from '../context/AuthContext';
import { getPulseDuration, getGlowIntensity, getSpinDuration, STATE_COLORS, LISTENING_ANIMATION_TIMING, END_CONVERSATION_ANIMATION_TIMING, GLOW_CONFIG, RIPPLE_CONFIG } from './voice-assistant/buttonAnimations';
import { generateIdleSegments } from './voice-assistant/arcUtils';
import LiveScribe from './LiveScribe';

interface ChatMessage {
  id: string;
  type: 'assistant';
  text: string;
  timestamp: Date;
  isStreaming: boolean;
}

export default function VoiceAssistantV2() {
  const { user } = useAuth();
  const [error, setError] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([]);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [isButtonPressed, setIsButtonPressed] = useState(false);
  const [isEndingConversation, setIsEndingConversation] = useState(false);
  
  // LiveScribe state
  const [scribeStatus, setScribeStatus] = useState<'idle' | 'getting-token' | 'connecting' | 'connected' | 'error'>('idle');
  const [isScribeActive, setIsScribeActive] = useState(false);
  
  // Transcript accumulation
  const accumulatedTranscriptRef = useRef<string>('');
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Silence detection - track last 5 transcripts
  const recentTranscriptsRef = useRef<string[]>([]);
  const lastCommittedTranscriptRef = useRef<string>('');
  
  // TTS audio
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  
  // Conversation history
  const conversationHistoryRef = useRef<Array<{ role: 'user' | 'assistant'; content: string }>>([]);

  // Clear silence timer
  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  // Reset silence timer (3 seconds after last committed transcript)
  const resetSilenceTimer = () => {
    clearSilenceTimer();
    console.log('[VoiceAssistantV2] resetSilenceTimer called', {
      isScribeActive,
      isProcessing,
      hasAccumulated: !!accumulatedTranscriptRef.current.trim(),
      accumulatedLength: accumulatedTranscriptRef.current.length
    });
    
    if (isScribeActive && !isProcessing && accumulatedTranscriptRef.current.trim()) {
      console.log('[VoiceAssistantV2] Setting silence timer (3s), accumulated transcript:', accumulatedTranscriptRef.current.substring(0, 50));
      silenceTimerRef.current = setTimeout(() => {
        console.log('[VoiceAssistantV2] Silence timer expired!', {
          hasAccumulated: !!accumulatedTranscriptRef.current.trim(),
          accumulated: accumulatedTranscriptRef.current.substring(0, 50),
          isProcessing
        });
        if (accumulatedTranscriptRef.current.trim() && !isProcessing) {
          console.log('[VoiceAssistantV2] Calling handleSilence from timer');
          handleSilence();
        } else {
          console.log('[VoiceAssistantV2] Timer expired but not calling handleSilence - conditions not met');
        }
      }, 3000);
      console.log('[VoiceAssistantV2] Silence timer set, will fire in 3 seconds');
    } else {
      console.log('[VoiceAssistantV2] Not setting silence timer - conditions not met');
    }
  };

  // Check for silence - 5 identical consecutive partial transcripts
  const checkForSilence = (newTranscript: string) => {
    console.log('[VoiceAssistantV2] Checking for silence, recent transcripts:', recentTranscriptsRef.current.length);
    
    // Add to recent transcripts
    recentTranscriptsRef.current.push(newTranscript);
    
    // Keep only last 5
    if (recentTranscriptsRef.current.length > 5) {
      recentTranscriptsRef.current.shift();
    }
    
    // Check if all 5 are the same (silence detected)
    if (recentTranscriptsRef.current.length === 5) {
      const allSame = recentTranscriptsRef.current.every(t => t === recentTranscriptsRef.current[0]);
      console.log('[VoiceAssistantV2] All 5 transcripts same?', allSame, 'Transcripts:', recentTranscriptsRef.current);
      
      if (allSame && accumulatedTranscriptRef.current.trim()) {
        console.log('[VoiceAssistantV2] Silence detected - 5 identical transcripts, accumulated:', accumulatedTranscriptRef.current);
        handleSilence();
        // Clear recent transcripts after processing
        recentTranscriptsRef.current = [];
      }
    }
  };

  // Handle silence - send accumulated transcript to backend
  const handleSilence = async () => {
    const transcript = accumulatedTranscriptRef.current.trim();
    if (!transcript || isProcessing) {
      console.log('[VoiceAssistantV2] Skipping silence handler - transcript empty or already processing', {
        transcript: transcript.substring(0, 50),
        isProcessing
      });
      return;
    }

    console.log('[VoiceAssistantV2] Handling silence - sending transcript to backend');
    console.log('[VoiceAssistantV2] Transcript:', transcript);
    
    setIsProcessing(true);
    clearSilenceTimer();
    
    try {
      console.log('[VoiceAssistantV2] Calling chatWithIoun...');
      const response = await chatWithIoun(transcript);
      console.log('[VoiceAssistantV2] Received response from backend:', {
        responseLength: response.response?.length,
        narrativeLength: response.narrative_response?.length,
        hasAudio: !!response.audio_base64,
        audioLength: response.audio_base64?.length
      });
      
      // Add assistant message (new messages appear at bottom)
      const assistantMessageId = `assistant-${Date.now()}-${Math.random()}`;
      setMessages(prev => [...prev, {
        id: assistantMessageId,
        type: 'assistant',
        text: response.response,
        timestamp: new Date(),
        isStreaming: false
      }]);

      // Update conversation history
      conversationHistoryRef.current.push({ role: 'user', content: transcript });
      conversationHistoryRef.current.push({ role: 'assistant', content: response.response });
      
      // Clear accumulated transcript
      accumulatedTranscriptRef.current = '';
      lastCommittedTranscriptRef.current = '';
      recentTranscriptsRef.current = [];
      
      // Play TTS audio if available
      if (response.audio_base64) {
        console.log('[VoiceAssistantV2] Playing TTS audio, base64 length:', response.audio_base64.length);
        playTTSAudio(response.audio_base64);
      } else {
        console.warn('[VoiceAssistantV2] No audio_base64 in response');
      }
      
    } catch (err: any) {
      console.error('[VoiceAssistantV2] Failed to chat with Ioun:', err);
      setError(err.message || 'Failed to process transcript');
    } finally {
      setIsProcessing(false);
    }
  };

  // Play TTS audio
  const playTTSAudio = (audioBase64: string) => {
    try {
      console.log('[VoiceAssistantV2] playTTSAudio called, base64 length:', audioBase64.length);
      
      // Stop any existing audio
      stopTTSAudio();
      
      // Create audio element
      const dataUrl = `data:audio/mpeg;base64,${audioBase64}`;
      console.log('[VoiceAssistantV2] Creating audio element with data URL length:', dataUrl.length);
      
      const audio = new Audio(dataUrl);
      audioRef.current = audio;
      
      audio.onplay = () => {
        console.log('[VoiceAssistantV2] Audio started playing');
        setIsPlayingAudio(true);
      };
      
      audio.onended = () => {
        console.log('[VoiceAssistantV2] Audio playback ended');
        setIsPlayingAudio(false);
        audioRef.current = null;
      };
      
      audio.onerror = (e) => {
        console.error('[VoiceAssistantV2] Audio playback error:', e);
        console.error('[VoiceAssistantV2] Audio error details:', {
          error: audio.error,
          code: audio.error?.code,
          message: audio.error?.message
        });
        setIsPlayingAudio(false);
        audioRef.current = null;
      };
      
      audio.onloadstart = () => {
        console.log('[VoiceAssistantV2] Audio load started');
      };
      
      audio.onloadeddata = () => {
        console.log('[VoiceAssistantV2] Audio data loaded');
      };
      
      audio.oncanplay = () => {
        console.log('[VoiceAssistantV2] Audio can play');
      };
      
      console.log('[VoiceAssistantV2] Calling audio.play()...');
      audio.play().then(() => {
        console.log('[VoiceAssistantV2] audio.play() resolved successfully');
      }).catch(err => {
        console.error('[VoiceAssistantV2] Failed to play audio:', err);
        setIsPlayingAudio(false);
      });
      
    } catch (err) {
      console.error('[VoiceAssistantV2] Failed to create audio:', err);
    }
  };

  // Stop TTS audio
  const stopTTSAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
      setIsPlayingAudio(false);
    }
  };

  // Handle transcript from LiveScribe
  const handleTranscript = (transcript: string) => {
    // Handle undefined or empty transcripts
    if (!transcript || transcript === 'undefined' || !transcript.trim()) {
      console.log('[VoiceAssistantV2] Empty/undefined transcript received, ignoring');
      return;
    }
    
    console.log('[VoiceAssistantV2] Received transcript:', transcript);
    
    // Stop TTS if playing (user is speaking)
    if (isPlayingAudio) {
      console.log('[VoiceAssistantV2] User speaking, stopping TTS');
      stopTTSAudio();
    }
    
    // Check if this is a new committed transcript (different from last committed one)
    if (transcript !== lastCommittedTranscriptRef.current) {
      console.log('[VoiceAssistantV2] New committed transcript detected, adding to accumulation');
      // New committed transcript - add to accumulation
      if (accumulatedTranscriptRef.current) {
        accumulatedTranscriptRef.current += ' ' + transcript;
      } else {
        accumulatedTranscriptRef.current = transcript;
      }
      lastCommittedTranscriptRef.current = transcript;
      
      // Reset recent transcripts for silence detection
      recentTranscriptsRef.current = [];
      
      // Reset silence timer - wait 3 seconds after this committed transcript
      resetSilenceTimer();
    } else {
      // Same committed transcript repeated - check for silence (5 identical)
      console.log('[VoiceAssistantV2] Same committed transcript as last, checking for silence');
      checkForSilence(transcript);
    }
  };

  // Handle LiveScribe status change
  const handleScribeStatusChange = (status: 'idle' | 'getting-token' | 'connecting' | 'connected' | 'error') => {
    console.log('[VoiceAssistantV2] Scribe status changed:', status);
    setScribeStatus(status);
    
    // Note: TTS stopping is handled in handleTranscript() when actual transcripts are received
    // This prevents premature interruption when status changes to 'connected'
    
    // Clear recent transcripts when status changes
    if (status !== 'connected') {
      recentTranscriptsRef.current = [];
      clearSilenceTimer();
    }
  };

  // Handle start
  const handleStart = async () => {
    try {
      setError('');
      setIsStarting(true);
      
      // Request microphone permission
      await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Start LiveScribe
      setIsScribeActive(true);
      setIsStarting(false);
      
    } catch (err: any) {
      console.error('Failed to start:', err);
      setError(err.message || 'Failed to start voice assistant');
      setIsStarting(false);
    }
  };

  // Handle stop
  const handleStop = async () => {
    try {
      setIsEndingConversation(true);
      setIsButtonPressed(false);
      
      // Stop LiveScribe
      setIsScribeActive(false);
      
      // Clear silence timer
      clearSilenceTimer();
      
      // Stop TTS
      stopTTSAudio();
      
      // Clear accumulated transcript
      accumulatedTranscriptRef.current = '';
      
      // Wait for animation
      const totalEndAnimationTime = END_CONVERSATION_ANIMATION_TIMING.step1_dashesFade;
      setTimeout(() => {
        setMessages([]);
        conversationHistoryRef.current = [];
        accumulatedTranscriptRef.current = '';
        setIsEndingConversation(false);
        setIsStarting(false);
      }, totalEndAnimationTime * 1000);
      
    } catch (err: any) {
      console.error('Failed to stop:', err);
      setError(err.message || 'Failed to stop voice assistant');
      setIsEndingConversation(false);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearSilenceTimer();
      stopTTSAudio();
    };
  }, []);

  const isConnected = scribeStatus === 'connected';
  const isConnecting = scribeStatus === 'connecting' || scribeStatus === 'getting-token' || isStarting;

  const showDashedSpinning = (isButtonPressed || isConnected) && !isEndingConversation;
  
  const buttonState: 'idle' | 'connecting' | 'listening' = isConnected 
    ? 'listening' 
    : isConnecting 
    ? 'connecting' 
    : 'idle';

  const pulseDuration = getPulseDuration(buttonState === 'listening' ? 'connected' : buttonState);
  const glowIntensity = getGlowIntensity(buttonState === 'listening' ? 'connected' : buttonState);

  const segmentPaths = useMemo(() => {
    return generateIdleSegments();
  }, []);

  const outerRingClass = useMemo(() => {
    if (isEndingConversation) {
      return 'ending-conversation-outer';
    } else if (showDashedSpinning) {
      return 'listening-state-outer';
    } else {
      return 'idle-state-outer';
    }
  }, [isEndingConversation, showDashedSpinning]);

  const handleButtonClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      
      const rippleId = Date.now();
      setRipples(prev => [...prev, { id: rippleId, x, y }]);
      
      setTimeout(() => {
        setRipples(prev => prev.filter(r => r.id !== rippleId));
      }, RIPPLE_CONFIG.duration * 1000);
    }
    
    if (!isConnected) {
      setIsButtonPressed(true);
      handleStart();
    } else {
      handleStop();
      setIsButtonPressed(false);
    }
  };
  
  useEffect(() => {
    if (!isConnected && !isConnecting) {
      setIsButtonPressed(false);
    }
  }, [isConnected, isConnecting]);

  return (
    <div className="p-4 bg-black rounded-xl text-white">
      {/* Hidden LiveScribe component */}
      <div style={{ display: 'none' }}>
        <LiveScribe
          active={isScribeActive}
          hidden={true}
          onTranscript={handleTranscript}
          onStatusChange={handleScribeStatusChange}
          onErrorChange={setError}
        />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-semibold text-lg">Voice Assistant</h3>
        <div className="flex items-center gap-4">
          {/* Connection Status */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-green-500' : isConnecting ? 'bg-yellow-500' : 'bg-gray-500'
            }`} />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>
          {/* Listening Status */}
          {isConnected && (
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                !isPlayingAudio ? 'bg-blue-500' : 'bg-gray-500'
              }`} />
              <span className={`text-sm ${
                !isPlayingAudio ? 'text-blue-400' : 'text-gray-500'
              }`}>
                Listening
              </span>
            </div>
          )}
          {/* Speaking Status */}
          {isConnected && (
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                isPlayingAudio ? 'bg-green-500' : 'bg-gray-500'
              }`} />
              <span className={`text-sm ${
                isPlayingAudio ? 'text-green-400' : 'text-gray-500'
              }`}>
                Speaking
              </span>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-500 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      {isProcessing && (
        <div className="mb-4 p-2 bg-neutral-800/50 border border-neutral-700 rounded text-neutral-300 text-sm">
          Processing...
        </div>
      )}

      {isPlayingAudio && (
        <div className="mb-4 p-2 bg-neutral-800/50 border border-neutral-700 rounded text-neutral-300 text-sm">
          🎤 Assistant is speaking...
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2 items-center justify-center">
        <div className="relative w-24 h-24" style={{ padding: '2px' }}>
          <button
            ref={buttonRef}
            onClick={handleButtonClick}
            disabled={isStarting && !isConnected}
            className="relative w-full h-full rounded-full bg-transparent border-0 p-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none overflow-hidden"
            aria-label={
              isConnected 
                ? 'Stop conversation' 
                : isStarting 
                ? 'Starting conversation' 
                : 'Start conversation'
            }
            style={{
              filter: `drop-shadow(0 0 ${GLOW_CONFIG.blur * glowIntensity}px ${GLOW_CONFIG.color})`,
            }}
          >
            {/* Ripple effects */}
            {ripples.map((ripple) => (
              <div
                key={ripple.id}
                className="absolute rounded-full pointer-events-none"
                style={{
                  left: '50%',
                  top: '50%',
                  width: '100%',
                  height: '100%',
                  border: `2px solid ${RIPPLE_CONFIG.color}`,
                  transform: 'translate(-50%, -50%)',
                  transformOrigin: 'center',
                  animation: `voiceButtonRipple ${RIPPLE_CONFIG.duration}s ease-out forwards`,
                  '--ripple-max-scale': RIPPLE_CONFIG.maxScale.toString(),
                } as React.CSSProperties}
              />
            ))}
            
            {/* Inner ring */}
            <div className="absolute inset-[12px] rounded-full border-2 border-white/80" />
          </button>
          {/* Outer ring */}
          <svg
            className={`absolute inset-0 pointer-events-none ${outerRingClass}`}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              '--shrink-duration': `${LISTENING_ANIMATION_TIMING.step1_dashTransition}s`,
              '--spin-duration': `${getSpinDuration()}s`,
              '--grow-duration': `${END_CONVERSATION_ANIMATION_TIMING.step1_dashesFade}s`,
            } as React.CSSProperties}
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            <g>
              {segmentPaths.map((path, index) => (
                <path
                  key={index}
                  d={path}
                  fill="none"
                  stroke="white"
                  strokeWidth="4"
                  strokeLinecap="round"
                />
              ))}
            </g>
          </svg>
        </div>
      </div>

      {/* Messages - appear below the button */}
      {messages.length > 0 && (
        <div className="mt-8 space-y-8">
          {messages.map((msg) => (
            <div key={msg.id} className="relative">
              {msg.isStreaming && (
                <span className="absolute -left-4 top-0 text-xs text-neutral-500 animate-pulse">●</span>
              )}
              <div className="prose prose-invert prose-sm max-w-none text-neutral-200">
                <EnhancedResponse isAnimating={msg.isStreaming}>
                  {msg.text}
                </EnhancedResponse>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

