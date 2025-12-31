import { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { EnhancedResponse } from './voice-assistant/EnhancedResponse';
import { chatWithIoun, executeCreations, type CreationRequest } from '../services/iounService';
import { getGlowIntensity, getSpinDuration, LISTENING_ANIMATION_TIMING, END_CONVERSATION_ANIMATION_TIMING, GLOW_CONFIG, RIPPLE_CONFIG } from './voice-assistant/buttonAnimations';
import { generateIdleSegments } from './voice-assistant/arcUtils';
import { IDLE_HINT_CONFIG } from './voice-assistant/idleHintConfig';
import LiveScribeSilence from './LiveScribeSilence';
import ConversationsDrawer from './conversations/ConversationsDrawer';
import { createConversation, getConversation } from '../services/conversationService';
import type { Conversation } from '../types';
import { logger } from '../lib/logger';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  isStreaming: boolean;
}

export default function VoiceAssistant() {
  const { conversationId: urlConversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([]);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [isButtonPressed, setIsButtonPressed] = useState(false);
  const [isEndingConversation, setIsEndingConversation] = useState(false);
  
  // Conversation management
  // Always start with null on mount - will be set by URL param effect if needed (but not on refresh)
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const currentConversationIdRef = useRef<string | null>(null); // Ref for synchronous access
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  
  // LiveScribeSilence state
  const [scribeStatus, setScribeStatus] = useState<'idle' | 'getting-token' | 'connecting' | 'connected' | 'error'>('idle');
  const [isScribeActive, setIsScribeActive] = useState(false);
  
  // Transcript accumulation
  const processedSilenceTranscriptRef = useRef<string>('');
  const isProcessingRef = useRef(false);

  const accumulatedTranscriptRef = useRef<string>('');
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // NEW: Track if silence was detected but we are waiting for the text commit
  const pendingSilenceTriggerRef = useRef<boolean>(false);

  // Silence detection - track last 5 transcripts (kept for backward compatibility, but LiveScribeSilence handles pattern detection)
  const recentTranscriptsRef = useRef<string[]>([]);
  const lastCommittedTranscriptRef = useRef<string>('');
  
  // TTS audio
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  
  // Creation requests
  const [pendingCreationRequests, setPendingCreationRequests] = useState<CreationRequest[]>([]);
  const [isExecutingCreations, setIsExecutingCreations] = useState(false);
  
  // Conversation history (kept for backward compatibility, but now managed via Firestore)
  const conversationHistoryRef = useRef<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  
  // Track if this is the initial mount (page refresh) - use state to prevent rendering
  const [isInitializing, setIsInitializing] = useState(true);
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  
  // On page refresh/mount: check for URL conversation ID, load if exists, otherwise clear state
  useEffect(() => {
    // If URL has a conversation ID, load it instead of clearing
    if (urlConversationId) {
      logger.debug('Initial mount with conversation ID in URL, loading conversation', { conversationId: urlConversationId });
      loadConversation(urlConversationId).finally(() => {
        setIsInitializing(false);
      });
      return;
    }
    
    // No conversation ID in URL - clear state and prepare for auto-creation
    setMessages([]);
    setError('');
    setCurrentConversationId(null);
    currentConversationIdRef.current = null; // Clear ref
    setCurrentConversation(null);
    setIsScribeActive(false);
    setIsProcessing(false);
    
      // Clear refs
      conversationHistoryRef.current = [];
      accumulatedTranscriptRef.current = '';
      lastCommittedTranscriptRef.current = '';
      recentTranscriptsRef.current = [];
      logger.debug('[mount effect] Clearing processedSilenceTranscriptRef', {
        previousValue: processedSilenceTranscriptRef.current,
      });
      processedSilenceTranscriptRef.current = '';
      isProcessingRef.current = false;
      pendingSilenceTriggerRef.current = false;
    
    // Navigate to base URL immediately
    navigate('/ioun-silence', { replace: true });
    
    // Mark initialization complete after navigation settles
    // This prevents any flash by ensuring we don't render messages during init
    setTimeout(() => {
      setIsInitializing(false);
    }, 50);
  }, []); // Empty dependency array - runs only on mount
  
  // Load conversation from URL param when it changes
  useEffect(() => {
    // Only load if URL has a conversation ID that's different from current
    if (urlConversationId && urlConversationId !== currentConversationId) {
      // URL has a conversation ID that's different from current - load it
      loadConversation(urlConversationId);
    }
    // Note: We don't include currentConversationId in deps to avoid triggering on mount state changes
  }, [urlConversationId]); // Only depend on URL param, not currentConversationId
  
  // Auto-create conversation after initialization if none exists
  useEffect(() => {
    // Skip if still initializing, loading a conversation, or already creating one
    if (isInitializing || isLoadingConversation || isCreatingConversation) {
      return;
    }
    
    // Skip if we already have a conversation ID
    if (currentConversationId) {
      return;
    }
    
    // Skip if URL has a conversation ID (it will be loaded by the URL param effect)
    if (urlConversationId) {
      return;
    }
    
    // Auto-create conversation when on base route without a conversation
    const createInitialConversation = async () => {
      try {
        setIsCreatingConversation(true);
        const newConversation = await createConversation();
        setCurrentConversationId(newConversation.id);
        currentConversationIdRef.current = newConversation.id; // Update ref synchronously
        setCurrentConversation(newConversation);
        // Navigate to conversation URL
        navigate(`/ioun-silence/${newConversation.id}`, { replace: true });
        logger.info('Auto-created initial conversation', { conversationId: newConversation.id });
      } catch (err: any) {
        logger.error('Error auto-creating conversation', err);
        setError(err.message || 'Failed to create conversation');
      } finally {
        setIsCreatingConversation(false);
      }
    };
    
    createInitialConversation();
  }, [isInitializing, isLoadingConversation, isCreatingConversation, currentConversationId, urlConversationId, navigate]);
  
  const loadConversation = async (conversationId: string) => {
    try {
      setIsLoadingConversation(true);
      setError(''); // Clear any previous errors
      const conversation = await getConversation(conversationId);
      setCurrentConversationId(conversationId);
      currentConversationIdRef.current = conversationId; // Update ref synchronously
      setCurrentConversation(conversation);
      
      // Load messages from conversation (both user and assistant for display)
      const loadedMessages: ChatMessage[] = conversation.messages.map(msg => ({
        id: msg.id,
        type: msg.role as 'user' | 'assistant',
        text: msg.content,
        timestamp: new Date(msg.timestamp),
        isStreaming: false,
      }));
      
      setMessages(loadedMessages);
      
      // Update conversation history ref for backend context
      conversationHistoryRef.current = conversation.messages.map(msg => ({
        role: msg.role,
        content: msg.content,
      }));
      
      logger.info('Loaded conversation', { conversationId, messageCount: conversation.messages.length });
    } catch (err: any) {
      logger.error('Error loading conversation', err);
      const errorMessage = err.message || 'Failed to load conversation';
      setError(errorMessage);
      // Navigate back to base route if conversation doesn't exist
      if (err.response?.status === 404) {
        navigate('/ioun-silence');
      }
    } finally {
      setIsLoadingConversation(false);
    }
  };
  
  const startNewConversation = async () => {
    try {
      setError(''); // Clear any previous errors
      
      // Clear current state
      setMessages([]);
      conversationHistoryRef.current = [];
      accumulatedTranscriptRef.current = '';
      lastCommittedTranscriptRef.current = '';
      recentTranscriptsRef.current = [];
      logger.debug('[startNewConversation] Clearing processedSilenceTranscriptRef', {
        previousValue: processedSilenceTranscriptRef.current,
      });
      processedSilenceTranscriptRef.current = '';
      setPendingCreationRequests([]);
      clearSilenceTimer();
      stopTTSAudio();
      
      // Create new conversation when user clicks "New Chat"
      const newConversation = await createConversation();
      setCurrentConversationId(newConversation.id);
      currentConversationIdRef.current = newConversation.id; // Update ref synchronously
      setCurrentConversation(newConversation);
      // Navigate to conversation URL instead of base URL
      navigate(`/ioun-silence/${newConversation.id}`);
      logger.info('Created new conversation', { conversationId: newConversation.id });
    } catch (err: any) {
      logger.error('Error creating new conversation', err);
      const errorMessage = err.message || 'Failed to create new conversation';
      setError(errorMessage);
    }
  };

  // Clear silence timer
  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      logger.debug('[clearSilenceTimer] Clearing existing timer');
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  // Reset silence timer (3 seconds after last committed transcript)
  const resetSilenceTimer = () => {
    clearSilenceTimer();
    
    // Don't set timer if already processing
    if (isProcessingRef.current) return;

    const currentTranscript = accumulatedTranscriptRef.current.trim();
    if (!currentTranscript || currentTranscript === processedSilenceTranscriptRef.current) {
        return;
    }

    silenceTimerRef.current = setTimeout(() => {
        // Double check lock inside the callback
        if (isProcessingRef.current) return;
        
        // Double check transcript status
        const transcriptAtExpiry = accumulatedTranscriptRef.current.trim();
        if (transcriptAtExpiry && transcriptAtExpiry !== processedSilenceTranscriptRef.current) {
            logger.info('[resetSilenceTimer] Timer expired - calling handleSilence()');
            handleSilence();
        }
    }, 3000);
  };

  // Handle silence - send accumulated transcript to backend
  const handleSilence = async () => {
    // 1. ATOMIC LOCK & VALIDATION
    // Check lock synchronously first
    if (isProcessingRef.current) {
      logger.warn('[handleSilence] Blocked: Already processing');
      return;
    }

    const transcript = accumulatedTranscriptRef.current.trim();
    
    // Check if empty
    if (!transcript) {
      logger.debug('[handleSilence] Blocked: Empty transcript');
      return;
    }

    // Check if already processed (Deduplication)
    if (transcript === processedSilenceTranscriptRef.current) {
      logger.warn('[handleSilence] Blocked: Transcript matches last processed text', {
        transcript,
        processed: processedSilenceTranscriptRef.current
      });
      // Clear accumulated to prevent timer loops on old text
      accumulatedTranscriptRef.current = '';
      return;
    }

    // 2. ACQUIRE LOCK & UPDATE STATE IMMEDIATELY
    // Set lock
    isProcessingRef.current = true;
    setIsProcessing(true);
    
    // Clear timer immediately
    clearSilenceTimer();
    
    // Stop any currently playing audio when sending request
    stopTTSAudio();

    // COMMIT STATE NOW - Before any async operation
    // This prevents handleTranscript or resetSilenceTimer from acting on this text again
    const currentTranscriptToProcess = transcript;
    processedSilenceTranscriptRef.current = currentTranscriptToProcess;
    
    // Clear accumulator immediately
    accumulatedTranscriptRef.current = '';
    lastCommittedTranscriptRef.current = ''; // Clear committed to allow new distinctive text
    recentTranscriptsRef.current = [];
    
    // Reset pending flag since we are handling it now
    pendingSilenceTriggerRef.current = false;
    
    const timestamp = Date.now();
    
    logger.debug('[handleSilence] State committed before async operation', {
      transcript: currentTranscriptToProcess,
      timestamp,
    });

    try {
      logger.info('[handleSilence] SENDING REQUEST TO BACKEND', {
        transcript: currentTranscriptToProcess,
        conversationId: currentConversationIdRef.current,
        timestamp,
      });
      
      const conversationId = currentConversationIdRef.current;
      if (!conversationId) {
        throw new Error('No active conversation. Please click "New Chat" to start a conversation.');
      }
      
      // 3. ASYNC OPERATION
      const response = await chatWithIoun(currentTranscriptToProcess, undefined, conversationId);
      
      // ... Handle Response (UI updates) ...
      const userMessageId = `user-${Date.now()}-${Math.random()}`;
      setMessages(prev => [...prev, {
        id: userMessageId,
        type: 'user',
        text: currentTranscriptToProcess,
        timestamp: new Date(),
        isStreaming: false
      }]);
      
      const assistantMessageId = `assistant-${Date.now()}-${Math.random()}`;
      setMessages(prev => [...prev, {
        id: assistantMessageId,
        type: 'assistant',
        text: response.response,
        timestamp: new Date(),
        isStreaming: false
      }]);

      conversationHistoryRef.current.push({ role: 'user', content: currentTranscriptToProcess });
      conversationHistoryRef.current.push({ role: 'assistant', content: response.response });

      if (response.audio_base64) {
        playTTSAudio(response.audio_base64);
      }
      
      if (response.creation_requests && response.creation_requests.length > 0) {
        setPendingCreationRequests(response.creation_requests);
      }

    } catch (err: any) {
      logger.error('[handleSilence] Error processing silence', err);
      setError(err.message || 'Failed to process transcript');
      
      // Optional: If it failed, do we want to allow retrying this specific text?
      // If yes, clear processedSilenceTranscriptRef.current here. 
      // generally safer to leave it set to prevent error loops.
    } finally {
      // 4. RELEASE LOCK
      isProcessingRef.current = false;
      setIsProcessing(false);
      
      // Start a cleanup timer for the deduplication ref if needed, 
      // but usually better to keep it until new text arrives.
      // We do NOT clear accumulatedTranscriptRef here, as the user might 
      // have started talking again during the API call.
    }
  };
  
  // Execute creation requests after user confirmation
  const handleExecuteCreations = async () => {
    if (pendingCreationRequests.length === 0) {
      return;
    }
    
    try {
      setIsExecutingCreations(true);
      setError('');
      logger.info('Executing creation requests', { count: pendingCreationRequests.length });
      
      const result = await executeCreations(pendingCreationRequests);
      
      logger.info('Creation execution complete', { successCount: result.success_count, errorCount: result.error_count });
      
      // Show success/error messages
      if (result.success_count > 0) {
        const successMessages = result.created_items
          .filter(item => item.status === 'success')
          .map(item => {
            const itemName = item.item.name || 'Item';
            const itemType = item.action_type.replace('create_', '');
            return `Created ${itemType}: ${itemName}`;
          });
        
        // Add confirmation message to chat
        const confirmationMessageId = `creation-confirm-${Date.now()}`;
        setMessages(prev => [...prev, {
          id: confirmationMessageId,
          type: 'assistant',
          text: `✓ ${successMessages.join(', ')}`,
          timestamp: new Date(),
          isStreaming: false
        }]);
      }
      
      if (result.error_count > 0) {
        const errorMessages = result.created_items
          .filter(item => item.status === 'error')
          .map(item => item.error || 'Unknown error');
        setError(`Some creations failed: ${errorMessages.join(', ')}`);
      }
      
      // Clear pending requests
      setPendingCreationRequests([]);
      
      // Refresh the page or reload context to show new items
      // For now, just clear - user can refresh manually or we could trigger a reload
      
    } catch (err: any) {
      logger.error('Error executing creations', err);
      setError(err.message || 'Failed to execute creations');
    } finally {
      setIsExecutingCreations(false);
    }
  };
  
  // Cancel creation requests
  const handleCancelCreations = () => {
    setPendingCreationRequests([]);
  };

  // Play TTS audio
  const playTTSAudio = (audioBase64: string) => {
    try {
      stopTTSAudio();
      const dataUrl = `data:audio/mpeg;base64,${audioBase64}`;
      const audio = new Audio(dataUrl);
      audioRef.current = audio;
      
      audio.onplay = () => setIsPlayingAudio(true);
      audio.onended = () => {
        setIsPlayingAudio(false);
        audioRef.current = null;
      };
      audio.onerror = () => {
        setIsPlayingAudio(false);
        audioRef.current = null;
      };
      
      audio.play().catch((err) => logger.error('Error playing TTS audio', err));
    } catch (err) {
      logger.error('Error setting up TTS audio', err);
    }
  };

  const stopTTSAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
      setIsPlayingAudio(false);
    }
  };

  // Handle transcript from LiveScribeSilence (committed transcripts)
  const handleTranscript = (transcript: string) => {
    logger.debug('[handleTranscript] Entry', {
      transcript: transcript,
      transcriptLength: transcript?.length || 0,
      transcriptTrimmed: transcript?.trim() || '',
      transcriptTrimmedLength: transcript?.trim().length || 0,
    });

    if (!transcript || !transcript.trim()) {
      logger.debug('[handleTranscript] Empty transcript, returning early');
      return;
    }

    const processedSilenceTranscript = processedSilenceTranscriptRef.current;
    const stringMatch = processedSilenceTranscript === transcript;
    const stringMatchTrimmed = processedSilenceTranscript.trim() === transcript.trim();
    
    logger.debug('[handleTranscript] String comparison check', {
      processedSilenceTranscript: processedSilenceTranscript,
      processedSilenceTranscriptLength: processedSilenceTranscript.length,
      processedSilenceTranscriptTrimmed: processedSilenceTranscript.trim(),
      transcript: transcript,
      transcriptLength: transcript.length,
      transcriptTrimmed: transcript.trim(),
      exactMatch: stringMatch,
      trimmedMatch: stringMatchTrimmed,
      willSkip: stringMatch,
    });

    if (stringMatch) {
      logger.warn('[handleTranscript] SKIPPING - transcript matches processedSilenceTranscriptRef', {
        transcript: transcript,
        processedSilenceTranscript: processedSilenceTranscript,
        reason: 'Already processed via silence detection',
      });
      return;
    }
    
    if (isPlayingAudio) {
      logger.debug('[handleTranscript] Stopping audio playback');
      stopTTSAudio();
    }
    
    const isNewTranscript = transcript !== lastCommittedTranscriptRef.current;
    
    logger.debug('[handleTranscript] Transcript processing', {
      isNewTranscript: isNewTranscript,
      lastCommittedTranscript: lastCommittedTranscriptRef.current,
      currentAccumulatedBefore: accumulatedTranscriptRef.current,
      isProcessing: isProcessingRef.current,
    });
    
    if (isNewTranscript) {
      // 1. Accumulate the text
      const previousAccumulated = accumulatedTranscriptRef.current;
      if (accumulatedTranscriptRef.current) {
        accumulatedTranscriptRef.current += ' ' + transcript;
        logger.debug('[handleTranscript] Appended to accumulated transcript', {
          previous: previousAccumulated,
          added: transcript,
          new: accumulatedTranscriptRef.current,
        });
      } else {
        accumulatedTranscriptRef.current = transcript;
        logger.debug('[handleTranscript] Set accumulated transcript (was empty)', {
          new: transcript,
        });
      }
      lastCommittedTranscriptRef.current = transcript;

      // Standard flow: User might still be talking, reset timer
      // BUT: Don't reset timer if we're already processing a request
      if (isProcessingRef.current) {
        logger.debug('[handleTranscript] Skipping resetSilenceTimer() - already processing a request');
      } else {
        logger.debug('[handleTranscript] Calling resetSilenceTimer()');
        resetSilenceTimer();
      }
    } else {
      logger.debug('[handleTranscript] Duplicate transcript (same as lastCommittedTranscript), skipping accumulation', {
        transcript: transcript,
        lastCommittedTranscript: lastCommittedTranscriptRef.current,
      });
    }
  };

  // Handle silence detection from LiveScribeSilence
  const handleSilenceDetected = (partialText: string) => {
    // Basic validation
    if (!partialText || !partialText.trim()) return;

    // 1. Check Lock
    if (isProcessingRef.current) {
      logger.debug('[handleSilenceDetected] Ignored: Already processing');
      return;
    }

    const textToProcess = partialText.trim();

    // 2. Check Deduplication
    if (textToProcess === processedSilenceTranscriptRef.current) {
      logger.debug('[handleSilenceDetected] Ignored: Already processed');
      return;
    }

    logger.debug('[handleSilenceDetected] Triggering processing', { text: textToProcess });
    
    // 3. Prepare State
    clearSilenceTimer();
    accumulatedTranscriptRef.current = textToProcess;
    
    // 4. Execute
    handleSilence();
  };

  // Handle LiveScribeSilence status change
  const handleScribeStatusChange = (status: 'idle' | 'getting-token' | 'connecting' | 'connected' | 'error') => {
    setScribeStatus(status);
    if (status !== 'connected') {
      recentTranscriptsRef.current = [];
      clearSilenceTimer();
      pendingSilenceTriggerRef.current = false;
    }
  };

  // Handle start
  const handleStart = async () => {
    try {
      setError('');
      setIsStarting(true);
      await navigator.mediaDevices.getUserMedia({ audio: true });
      setIsScribeActive(true);
      setIsStarting(false);
    } catch (err: any) {
      setError(err.message || 'Failed to start');
      setIsStarting(false);
    }
  };

  // Handle stop
  const handleStop = async () => {
    try {
      setIsEndingConversation(true);
      setIsButtonPressed(false);
      setIsScribeActive(false);
      clearSilenceTimer();
      stopTTSAudio();
      accumulatedTranscriptRef.current = '';
      pendingSilenceTriggerRef.current = false;
      
      const totalEndAnimationTime = END_CONVERSATION_ANIMATION_TIMING.step1_dashesFade;
      setTimeout(() => {
        // Keep messages and conversation history visible - don't clear state
        // Only clear the accumulated transcript buffer for the next session
        accumulatedTranscriptRef.current = '';
        setIsEndingConversation(false);
        setIsStarting(false);
        // Don't clear conversation or messages - user might want to continue it later
      }, totalEndAnimationTime * 1000);
    } catch (err: any) {
      setError(err.message || 'Failed to stop');
      setIsEndingConversation(false);
    }
  };

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

  const glowIntensity = getGlowIntensity(buttonState === 'listening' ? 'connected' : buttonState);
  const segmentPaths = useMemo(() => generateIdleSegments(), []);

  const outerRingClass = useMemo(() => {
    if (isEndingConversation) return 'ending-conversation-outer';
    if (showDashedSpinning) return 'listening-state-outer';
    return 'idle-state-outer';
  }, [isEndingConversation, showDashedSpinning]);

  const handleButtonClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      setRipples(prev => [...prev, { id: Date.now(), x, y }]);
      setTimeout(() => setRipples(prev => prev.slice(1)), RIPPLE_CONFIG.duration * 1000);
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
      {/* Hidden LiveScribeSilence component */}
      <div style={{ display: 'none' }}>
        <LiveScribeSilence
          active={isScribeActive}
          hidden={true}
          onTranscript={handleTranscript}
          onStatusChange={handleScribeStatusChange}
          onErrorChange={setError}
          onSilenceDetected={handleSilenceDetected}
        />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-lg">Voice Assistant</h3>
          {currentConversation && (
            <span className="text-sm text-neutral-400 truncate max-w-xs">
              {currentConversation.title}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsDrawerOpen(true)}
            className="px-3 py-1.5 text-sm bg-white/5 text-white border border-white/10 rounded-lg hover:bg-white/10 transition-colors"
          >
            Conversations
          </button>
          <button
            onClick={startNewConversation}
            className="px-3 py-1.5 text-sm bg-white text-black rounded-lg hover:bg-neutral-200 transition-colors font-medium"
          >
            New Chat
          </button>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : isConnecting ? 'bg-yellow-500' : 'bg-gray-500'}`} />
            <span className="text-sm text-gray-400">{isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}</span>
          </div>
          {isConnected && (
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${!isPlayingAudio ? 'bg-blue-500' : 'bg-gray-500'}`} />
              <span className={`text-sm ${!isPlayingAudio ? 'text-blue-400' : 'text-gray-500'}`}>Listening</span>
            </div>
          )}
          {isConnected && (
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isPlayingAudio ? 'bg-green-500' : 'bg-gray-500'}`} />
              <span className={`text-sm ${isPlayingAudio ? 'text-green-400' : 'text-gray-500'}`}>Speaking</span>
            </div>
          )}
        </div>
      </div>

      {error && <div className="mb-4 p-3 bg-red-900/50 border border-red-500 rounded text-red-200 text-sm">{error}</div>}
      {isProcessing && <div className="mb-4 p-2 bg-neutral-800/50 border border-neutral-700 rounded text-neutral-300 text-sm">Processing...</div>}
      {isPlayingAudio && <div className="mb-4 p-2 bg-neutral-800/50 border border-neutral-700 rounded text-neutral-300 text-sm">🎤 Assistant is speaking...</div>}
      
      {/* Pending Creation Requests */}
      {pendingCreationRequests.length > 0 && (
        <div className="mb-4 p-4 bg-blue-900/30 border border-blue-500/50 rounded-lg">
          <div className="mb-3">
            <h4 className="text-sm font-semibold text-blue-200 mb-2">
              Creation Requests Detected ({pendingCreationRequests.length})
            </h4>
            <div className="space-y-2">
              {pendingCreationRequests.map((req, index) => (
                <div key={index} className="text-sm text-neutral-200 bg-neutral-800/50 p-2 rounded">
                  <div className="font-medium text-blue-300">
                    {req.action_type.replace('create_', 'Create ').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </div>
                  <div className="text-neutral-400 mt-1">
                    {req.action_type === 'create_campaign' && (
                      <>Campaign: <span className="text-white">{req.data.name}</span>{req.data.description && ` - ${req.data.description}`}</>
                    )}
                    {req.action_type === 'create_session' && (
                      <>Session: <span className="text-white">{req.data.name}</span></>
                    )}
                    {req.action_type === 'create_character' && (
                      <>Character: <span className="text-white">{req.data.name}</span> - {req.data.max_hp} HP{req.data.race && `, ${req.data.race}`}{req.data.class_name && ` ${req.data.class_name}`}</>
                    )}
                  </div>
                  {req.transcript_segment && (
                    <div className="text-xs text-neutral-500 mt-1 italic">
                      "{req.transcript_segment}"
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleExecuteCreations}
              disabled={isExecutingCreations}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-600/50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            >
              {isExecutingCreations ? 'Creating...' : 'Confirm & Create'}
            </button>
            <button
              onClick={handleCancelCreations}
              disabled={isExecutingCreations}
              className="px-4 py-2 bg-neutral-700 hover:bg-neutral-600 disabled:bg-neutral-700/50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            >
              Cancel
            </button>
          </div>
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
            style={{ filter: `drop-shadow(0 0 ${GLOW_CONFIG.blur * glowIntensity}px ${GLOW_CONFIG.color})` }}
          >
            {ripples.map((ripple) => (
              <div
                key={ripple.id}
                className="absolute rounded-full pointer-events-none"
                style={{
                  left: '50%', top: '50%', width: '100%', height: '100%',
                  border: `2px solid ${RIPPLE_CONFIG.color}`,
                  transform: 'translate(-50%, -50%)',
                  animation: `voiceButtonRipple ${RIPPLE_CONFIG.duration}s ease-out forwards`,
                  '--ripple-max-scale': RIPPLE_CONFIG.maxScale.toString(),
                } as React.CSSProperties}
              />
            ))}
            <div className="absolute inset-[12px] rounded-full border-2 border-white/80" />
          </button>
          <svg
            className={`absolute inset-0 pointer-events-none ${outerRingClass}`}
            style={{
              width: '100%', height: '100%', border: 'none',
              '--shrink-duration': `${LISTENING_ANIMATION_TIMING.step1_dashTransition}s`,
              '--spin-duration': `${getSpinDuration()}s`,
              '--grow-duration': `${END_CONVERSATION_ANIMATION_TIMING.step1_dashesFade}s`,
            } as React.CSSProperties}
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            <g>
              {segmentPaths.map((path, index) => (
                <path key={index} d={path} fill="none" stroke="white" strokeWidth="4" strokeLinecap="round" />
              ))}
            </g>
          </svg>
        </div>
      </div>

      {/* Idle State Hint */}
      {!isInitializing && messages.length === 0 && !isConnected && !isConnecting && !isProcessing && !isScribeActive && (
        <div className={IDLE_HINT_CONFIG.className}>
          {IDLE_HINT_CONFIG.text}
        </div>
      )}

      {/* Messages */}
      {!isInitializing && messages.length > 0 && (
        <div className="mt-8 space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`relative ${
                msg.type === 'user' ? 'ml-auto max-w-[80%]' : 'mr-auto max-w-full'
              }`}
            >
              {msg.isStreaming && (
                <span className="absolute -left-4 top-0 text-xs text-neutral-500 animate-pulse">●</span>
              )}
              {msg.type === 'user' ? (
                <div className="bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-sm text-white">
                  {msg.text}
                </div>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none text-neutral-200">
                  <EnhancedResponse isAnimating={msg.isStreaming}>{msg.text}</EnhancedResponse>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      
      {/* Conversations Drawer */}
      <ConversationsDrawer
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onSelectConversation={(id) => {
          navigate(`/ioun-silence/${id}`);
        }}
      />
    </div>
  );
}
