import api from './api';

export interface TranscriptionResponse {
  transcript: string;
  language?: string;
}

/**
 * Send audio chunk to backend for transcription
 * @param audioBlob - Audio blob/chunk to transcribe
 * @returns Transcription result
 */
export async function transcribeAudioChunk(audioBlob: Blob): Promise<TranscriptionResponse> {
  try {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'audio.webm');

    const response = await api.post<TranscriptionResponse>('/audio/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  } catch (error: any) {
    console.error('Error transcribing audio:', error);
    throw new Error(error.response?.data?.error || 'Failed to transcribe audio');
  }
}

