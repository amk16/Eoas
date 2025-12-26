import api from './api';

export type AnalyzeEvent = {
  character_id: number;
  character_name: string;
  amount: number;
  type: 'damage' | 'healing';
  transcript_segment: string;
};

export type AnalyzeResponse = {
  events: AnalyzeEvent[];
  count: number;
  previous_chunk_for_next_analysis?: string;
};

/**
 * Analyze a transcript for damage/healing events using Gemini
 * @param transcript - The transcript text to analyze
 * @param sessionId - The session ID to analyze for
 * @returns Analysis result with extracted events
 */
export async function analyzeTranscript(
  transcript: string,
  sessionId: number
): Promise<AnalyzeResponse> {
  try {
    const response = await api.post<AnalyzeResponse>('/analyze', {
      transcript,
      session_id: sessionId,
    });

    return response.data;
  } catch (error: any) {
    console.error('Error analyzing transcript:', error);
    throw new Error(
      error.response?.data?.detail || 'Failed to analyze transcript'
    );
  }
}

