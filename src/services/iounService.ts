import api from './api';

export interface IounChatRequest {
  transcript: string;
  voice_id?: string;
  conversation_id?: string;
}

export interface IounChatResponse {
  response: string;
  narrative_response: string;
  audio_base64?: string;
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

