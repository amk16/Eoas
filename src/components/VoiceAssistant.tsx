import { useState, useEffect } from 'react';
import { useConversation } from '@elevenlabs/react';
import { EnhancedResponse } from './voice-assistant/EnhancedResponse';
import { getConversationToken, submitAction, confirmAction, getPendingActions } from '../services/voiceAssistantService';
import { useAuth } from '../context/AuthContext';

// Phase 1: Message structure for investigation
interface MessageLog {
  id: string;
  type: string;
  fullMessage: any;
  timestamp: Date;
}

// Phase 2: Enhanced message structure for streaming support
// Phase 1: Only assistant messages - user messages removed
interface ChatMessage {
  id: string;
  type: 'assistant';
  text: string;
  timestamp: Date;
  isStreaming: boolean;
  source?: string;
  role?: string;
}

export default function VoiceAssistant() {
  const { user } = useAuth();
  const [error, setError] = useState<string>('');
  // Phase 2: Updated to use enhanced message structure
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingActions, setPendingActions] = useState<any[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  // Phase 1: Track all messages for investigation
  const [messageLog, setMessageLog] = useState<MessageLog[]>([]);
  // Phase 2: Track the ID of the currently streaming message
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);

  const conversation = useConversation({
    onConnect: () => {
      console.log('[VoiceAssistant] Connected');
      setError('');
    },
    onDisconnect: () => {
      console.log('[VoiceAssistant] Disconnected');
    },
    onMessage: (message: any) => {
      // Phase 1: Comprehensive logging to understand message structure
      const messageId = message.id || message.message_id || `msg-${Date.now()}-${Math.random()}`;
      
      console.group(`[VoiceAssistant] Message Received (ID: ${messageId})`);
      console.log('Full message object:', JSON.stringify(message, null, 2));
      console.log('Message type:', message.type);
      console.log('Message keys:', Object.keys(message));
      console.log('Text property:', message.text);
      console.log('Message property:', message.message);
      
      // Check for streaming-related properties
      const streamingProps = {
        type: message.type,
        text: message.text,
        message: message.message,
        id: message.id,
        message_id: message.message_id,
        conversation_id: message.conversation_id,
        timestamp: message.timestamp,
        is_final: message.is_final,
        is_tentative: message.is_tentative,
        is_streaming: message.is_streaming,
        is_complete: message.is_complete,
        chunk_index: message.chunk_index,
        chunk_id: message.chunk_id,
        sequence: message.sequence,
        sequence_number: message.sequence_number,
        role: message.role,
        status: message.status,
        delta: message.delta,
        content: message.content,
      };
      console.log('Streaming-related properties:', streamingProps);
      console.groupEnd();
      
      // Phase 1: Store message in log for analysis
      setMessageLog(prev => [...prev, {
        id: messageId,
        type: message.type || 'unknown',
        fullMessage: message,
        timestamp: new Date()
      }]);
      
      // Phase 2: Enhanced message handling with streaming support
      // Phase 1: Only handle assistant messages - user messages are ignored
      const messageContent = message.text || message.message || '';
      
      const isAssistantMessage = 
        message.type === 'assistant_message' || 
        message.type === 'agent_message' ||
        (message.role === 'agent' && message.source === 'ai') ||
        message.role === 'agent' ||
        message.source === 'ai';

      if (isAssistantMessage && messageContent) {
        // Phase 2: Handle assistant messages - check if this is an update to existing message
        const isStreaming = message.is_streaming || message.is_tentative || 
                          message.status === 'streaming' || 
                          (message.delta !== undefined && message.delta !== null);
        
        // Check if we have a streaming message in progress
        if (isStreaming && streamingMessageId) {
          // Update existing streaming message
          setMessages(prev => prev.map(msg => {
            if (msg.id === streamingMessageId) {
              // If delta exists, append it; otherwise replace with new content
              const updatedText = message.delta 
                ? msg.text + message.delta 
                : messageContent;
              return {
                ...msg,
                text: updatedText,
                isStreaming: true
              };
            }
            return msg;
          }));
        } else if (isStreaming) {
          // Start new streaming message
          const assistantMessageId = `assistant-${Date.now()}-${Math.random()}`;
          setStreamingMessageId(assistantMessageId);
          setMessages(prev => [...prev, {
            id: assistantMessageId,
            type: 'assistant',
            text: messageContent,
            timestamp: new Date(),
            isStreaming: true,
            source: message.source,
            role: message.role
          }]);
        } else {
          // Complete message (not streaming)
          // If we were streaming, mark it as complete
          if (streamingMessageId) {
            setMessages(prev => prev.map(msg => {
              if (msg.id === streamingMessageId) {
                return {
                  ...msg,
                  text: messageContent,
                  isStreaming: false
                };
              }
              return msg;
            }));
            setStreamingMessageId(null);
          } else {
            // New complete message
            const assistantMessageId = `assistant-${Date.now()}-${Math.random()}`;
            setMessages(prev => [...prev, {
              id: assistantMessageId,
              type: 'assistant',
              text: messageContent,
              timestamp: new Date(),
              isStreaming: false,
              source: message.source,
              role: message.role
            }]);
          }
        }
      } else if (message.type === 'function_call' || message.type === 'tool_call') {
        // Handle tool calls - these need to be sent to backend for confirmation
        handleToolCall(message);
      } else {
        // Log unhandled message types for investigation
        console.warn('[VoiceAssistant] Unhandled message type:', message.type, message);
      }
    },
    onAgentChatResponsePart: (part: any) => {
      // Phase 1 & 2: Investigate and handle streaming response parts
      console.group('[VoiceAssistant] Agent Chat Response Part');
      console.log('Response part:', JSON.stringify(part, null, 2));
      console.log('Part keys:', Object.keys(part));
      console.log('Part content:', part.content || part.text || part.message);
      console.log('Part delta:', part.delta);
      console.log('Part index:', part.index);
      console.log('Part is_final:', part.is_final);
      console.log('Part is_complete:', part.is_complete);
      console.groupEnd();

      // Phase 2: Handle streaming response parts
      const partContent = part.content || part.text || part.message || '';
      const isComplete = part.is_final || part.is_complete || part.status === 'complete';
      
      if (partContent) {
        if (streamingMessageId) {
          // Update existing streaming message
          setMessages(prev => prev.map(msg => {
            if (msg.id === streamingMessageId) {
              // If delta exists, append it; otherwise use the full content
              const updatedText = part.delta 
                ? msg.text + part.delta 
                : partContent;
              return {
                ...msg,
                text: updatedText,
                isStreaming: !isComplete
              };
            }
            return msg;
          }));

          // If this part is complete, clear the streaming message ID
          if (isComplete) {
            setStreamingMessageId(null);
          }
        } else if (!isComplete) {
          // Start new streaming message
          const assistantMessageId = `assistant-${Date.now()}-${Math.random()}`;
          setStreamingMessageId(assistantMessageId);
          setMessages(prev => [...prev, {
            id: assistantMessageId,
            type: 'assistant',
            text: partContent,
            timestamp: new Date(),
            isStreaming: true
          }]);
        } else {
          // Complete message from response part
          const assistantMessageId = `assistant-${Date.now()}-${Math.random()}`;
          setMessages(prev => [...prev, {
            id: assistantMessageId,
            type: 'assistant',
            text: partContent,
            timestamp: new Date(),
            isStreaming: false
          }]);
        }
      }
    },
    onDebug: (debugInfo: any) => {
      // Phase 1: Log debug information which may contain streaming details
      console.log('[VoiceAssistant] Debug:', debugInfo);
    },
    onError: (error: any) => {
      console.error('[VoiceAssistant] Error:', error);
      setError(error.message || 'An error occurred');
    },
    onModeChange: (prop: { mode: any }) => {
      console.log('[VoiceAssistant] Mode changed:', prop.mode);
    },
    onStatusChange: (prop: { status: any }) => {
      console.log('[VoiceAssistant] Status changed:', prop.status);
    },
    onUnhandledClientToolCall: (toolCall: any) => {
      console.log('[VoiceAssistant] Unhandled tool call:', toolCall);
      // Handle client-side tool calls if needed
      handleToolCall(toolCall);
    }
  });

  // Load pending actions on mount and when conversation connects
  useEffect(() => {
    if (conversation.status === 'connected') {
      loadPendingActions();
    }
  }, [conversation.status]);

  const loadPendingActions = async () => {
    try {
      const actions = await getPendingActions();
      setPendingActions(actions);
    } catch (err: any) {
      console.error('Failed to load pending actions:', err);
    }
  };

  const handleToolCall = async (toolCall: any) => {
    try {
      // Extract tool name and parameters
      const toolName = toolCall.function?.name || toolCall.name || toolCall.tool_name;
      const parameters = toolCall.function?.arguments 
        ? (typeof toolCall.function.arguments === 'string' 
            ? JSON.parse(toolCall.function.arguments) 
            : toolCall.function.arguments)
        : toolCall.parameters || {};

      if (!toolName) {
        console.warn('Tool call missing name:', toolCall);
        return;
      }

      // Submit to backend for confirmation
      const action = await submitAction(toolName, parameters);
      setPendingActions(prev => [...prev, action]);
    } catch (err: any) {
      console.error('Failed to handle tool call:', err);
      setError(err.message || 'Failed to process tool call');
    }
  };

  const handleConfirmAction = async (actionId: string, confirmed: boolean) => {
    try {
      await confirmAction(actionId, confirmed);
      setPendingActions(prev => prev.filter(a => a.action_id !== actionId));
      
      if (confirmed) {
        // Reload pending actions to get updated list
        await loadPendingActions();
      }
    } catch (err: any) {
      console.error('Failed to confirm action:', err);
      setError(err.message || 'Failed to confirm action');
    }
  };

  const handleStart = async () => {
    try {
      setError('');
      setIsStarting(true);

      // Request microphone permission first
      await navigator.mediaDevices.getUserMedia({ audio: true });

      // Get conversation token from backend
      const tokenData = await getConversationToken();

      // Start session with signed URL or conversation token
      let conversationId: string | undefined;
      
      if (tokenData.signedUrl) {
        conversationId = await conversation.startSession({
          signedUrl: tokenData.signedUrl,
          connectionType: 'websocket',
          userId: user?.id?.toString() || undefined,
        });
      } else if (tokenData.conversationToken) {
        conversationId = await conversation.startSession({
          conversationToken: tokenData.conversationToken,
          connectionType: 'webrtc',
          userId: user?.id?.toString() || undefined,
        });
      } else if (tokenData.agentId || tokenData.agent_id) {
        const agentId = tokenData.agentId || tokenData.agent_id;
        if (!agentId) {
          throw new Error('Agent ID is required but was not provided');
        }
        conversationId = await conversation.startSession({
          agentId: agentId,
          connectionType: 'websocket', // Default to websocket
          userId: user?.id?.toString() || undefined,
        });
      } else {
        throw new Error('No valid connection credentials received from server');
      }

      console.log('[VoiceAssistant] Conversation started:', conversationId);
    } catch (err: any) {
      console.error('Failed to start conversation:', err);
      setError(err.message || 'Failed to start conversation');
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    try {
      await conversation.endSession();
      setMessages([]);
      setPendingActions([]);
      // Phase 2: Clear streaming state
      setStreamingMessageId(null);
    } catch (err: any) {
      console.error('Failed to stop conversation:', err);
      setError(err.message || 'Failed to stop conversation');
    }
  };

  const isConnected = conversation.status === 'connected';
  const isConnecting = conversation.status === 'connecting' || isStarting;

  return (
    <div className="p-4 bg-black rounded-xl text-white">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-semibold text-lg">Voice Assistant</h3>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500' : isConnecting ? 'bg-yellow-500' : 'bg-gray-500'
          }`} />
          <span className="text-sm text-gray-400">
            {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/50 border border-red-500 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      {conversation.isSpeaking && (
        <div className="mb-4 p-2 bg-neutral-800/50 border border-neutral-700 rounded text-neutral-300 text-sm">
          🎤 Assistant is speaking...
        </div>
      )}

      {/* Messages - Phase 1: Direct rendering on black background, no containers */}
      {messages.length > 0 && (
        <div className="space-y-8">
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

      {/* Phase 1: Message Log for Investigation */}
      {messageLog.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-300">
            🔍 Phase 1: Message Log ({messageLog.length} messages) - Click to expand
          </summary>
          <div className="mt-2 space-y-2 max-h-96 overflow-y-auto bg-neutral-800 rounded p-2 text-xs">
            {messageLog.map((log, idx) => (
              <div key={log.id} className="border-b border-neutral-700 pb-2 last:border-0">
                <div className="font-mono text-gray-300">
                  <div className="font-semibold text-yellow-400">
                    [{idx + 1}] Type: {log.type} | ID: {log.id}
                  </div>
                  <div className="text-gray-400 mt-1">
                    Time: {log.timestamp.toLocaleTimeString()}
                  </div>
                  <pre className="mt-2 text-gray-300 whitespace-pre-wrap break-words">
                    {JSON.stringify(log.fullMessage, null, 2)}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Pending Actions */}
      {pendingActions.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-semibold text-sm">Pending Actions:</h4>
          {pendingActions.map((action) => (
            <div key={action.action_id} className="p-3 bg-yellow-900/30 border border-yellow-500 rounded">
              <p className="text-sm mb-2">{action.description}</p>
              <div className="flex gap-2">
                <button
                  onClick={() => handleConfirmAction(action.action_id, true)}
                  className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleConfirmAction(action.action_id, false)}
                  className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2">
        {!isConnected && !isConnecting ? (
          <button
            onClick={handleStart}
            disabled={isStarting}
            className="px-4 py-2 bg-white text-black rounded hover:bg-gray-200 disabled:opacity-50"
          >
            {isStarting ? 'Starting...' : 'Start Conversation'}
          </button>
        ) : (
          <button
            onClick={handleStop}
            className="px-4 py-2 bg-red-500 hover:bg-red-600 rounded"
          >
            End Conversation
          </button>
        )}

        {isConnected && conversation.canSendFeedback && (
          <div className="flex gap-2">
            <button
              onClick={() => conversation.sendFeedback(true)}
              className="px-3 py-2 bg-green-600 hover:bg-green-700 rounded text-sm"
              title="Positive feedback"
            >
              👍
            </button>
            <button
              onClick={() => conversation.sendFeedback(false)}
              className="px-3 py-2 bg-red-600 hover:bg-red-700 rounded text-sm"
              title="Negative feedback"
            >
              👎
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
