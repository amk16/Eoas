import api from './api';

export interface IounChatRequest {
  transcript: string;
  voice_id?: string;
  conversation_id?: string;
}

export interface CreationRequest {
  action_type: 'create_campaign' | 'create_session' | 'create_character';
  data: Record<string, any>;
  transcript_segment: string;
}

export interface IounChatResponse {
  response: string;
  narrative_response: string;
  audio_base64?: string;
  creation_requests?: CreationRequest[];
}

export interface CreatedItem {
  action_type: string;
  item: Record<string, any>;
  status: 'success' | 'error';
  error?: string;
}

export interface ExecuteCreationsResponse {
  created_items: CreatedItem[];
  success_count: number;
  error_count: number;
}

/**
 * Chat with Ioun voice assistant.
 * Sends transcript to backend, receives both display response and narrative response for TTS.
 * 
 * @param transcript - User's transcript text
 * @param voiceId - Optional Eleven Labs voice ID
 * @returns Chat response with both responses and audio
 */
export async function chatWithIoun(
  transcript: string,
  voiceId?: string,
  conversationId?: string
): Promise<IounChatResponse> {
  try {
    const response = await api.post<IounChatResponse>('/ioun/chat', {
      transcript,
      voice_id: voiceId,
      conversation_id: conversationId,
    });

    return response.data;
  } catch (error: any) {
    console.error('Error chatting with Ioun:', error);
    throw new Error(error.response?.data?.detail || 'Failed to chat with Ioun');
  }
}

/**
 * Execute creation requests after user confirmation.
 * @param creationRequests - Array of creation requests to execute
 * @returns Execution result with created items and status
 */
export async function executeCreations(
  creationRequests: CreationRequest[]
): Promise<ExecuteCreationsResponse> {
  try {
    const response = await api.post<ExecuteCreationsResponse>('/ioun/execute-creations', {
      creation_requests: creationRequests,
    });

    return response.data;
  } catch (error: any) {
    console.error('Error executing creations:', error);
    throw new Error(error.response?.data?.detail || 'Failed to execute creations');
  }
}

