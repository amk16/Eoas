import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import LiveScribe from '../LiveScribe';
import { analyzeTranscript } from '../../services/analyzeService';
import InitiativeTracker from './InitiativeTracker';
import CharacterDetailSidebar from './CharacterDetailSidebar';

interface SessionCharacter {
  session_id: number;
  character_id: number;
  character_name: string;
  starting_hp: number;
  current_hp: number;
  max_hp: number;
}

interface DamageEvent {
  id: number;
  session_id: number;
  character_id: number;
  character_name: string;
  amount?: number;
  type: 'damage' | 'healing' | 'spell_cast';
  spell_name?: string;
  spell_level?: number;
  timestamp: string;
  transcript_segment: string | null;
}

interface TranscriptSegment {
  id: number;
  session_id: number;
  client_chunk_id: string;
  client_timestamp_ms: number | null;
  text: string;
  speaker: string | null;
  created_at: string;
}

type TranscriptMode = 'lines' | 'full' | 'annotated';

interface SessionDetails {
  id: number;
  user_id: number;
  name: string;
  started_at: string;
  ended_at: string | null;
  status: 'active' | 'ended';
  characters: SessionCharacter[];
  events: DamageEvent[];
}

export default function SessionView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<SessionDetails | null>(null);
  // Important: `loading` should only block the very first load (when `session` is null).
  // If we block-render during background refreshes, `LiveScribe` unmounts and its cleanup
  // will stop the active recording.
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [refreshError, setRefreshError] = useState('');
  const [recording, setRecording] = useState(false);
  const [recorderMounted, setRecorderMounted] = useState(false);
  const [scribeStatus, setScribeStatus] = useState<'idle' | 'getting-token' | 'connecting' | 'connected' | 'error'>(
    'idle'
  );
  const [scribeError, setScribeError] = useState<string>('');
  const [scribePermission, setScribePermission] = useState<boolean | null>(null);
  const [transcriptMode, setTranscriptMode] = useState<TranscriptMode>('lines');
  const [transcriptSegments, setTranscriptSegments] = useState<TranscriptSegment[]>([]);
  const persistQueueRef = useRef<Promise<void>>(Promise.resolve());
  const [analyzing, setAnalyzing] = useState(false);
  
  // Phase 2: Character detail sidebar state
  const [selectedCharacterId, setSelectedCharacterId] = useState<number | null>(null);
  const [selectedCharacterName, setSelectedCharacterName] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  
  // Phase 1: Buffer for accumulating transcript with time-based analysis
  const transcriptBufferRef = useRef<string>('');
  const previousChunkRef = useRef<string>(''); // Track previous analyzed chunk for context
  const analysisTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastAnalysisTimeRef = useRef<number>(0);
  const [lastAnalysisTime, setLastAnalysisTime] = useState<number>(0);
  const [bufferLength, setBufferLength] = useState<number>(0);
  const ANALYSIS_INTERVAL_MS = 25000; // 25 seconds

  useEffect(() => {
    if (id) {
      fetchSession({ mode: 'initial' });
      fetchTranscripts();
    }
  }, [id]);

  // Phase 1: Time-based analysis timer
  useEffect(() => {
    if (!session || session.status !== 'active' || !id) {
      // Clear timer if session is not active
      if (analysisTimerRef.current) {
        clearInterval(analysisTimerRef.current);
        analysisTimerRef.current = null;
      }
      return;
    }

    // Start the analysis timer
    const startAnalysisTimer = () => {
      // Clear any existing timer
      if (analysisTimerRef.current) {
        clearInterval(analysisTimerRef.current);
      }

      // Set up interval to analyze every 25 seconds
      analysisTimerRef.current = setInterval(() => {
        if (transcriptBufferRef.current.trim().length > 0) {
          console.log('⏰ 25-second interval reached, analyzing buffered transcript');
          triggerAnalysis();
        }
      }, ANALYSIS_INTERVAL_MS);

      const now = Date.now();
      lastAnalysisTimeRef.current = now;
      setLastAnalysisTime(now);
    };

    startAnalysisTimer();

    // Cleanup on unmount or when session becomes inactive
    return () => {
      if (analysisTimerRef.current) {
        clearInterval(analysisTimerRef.current);
        analysisTimerRef.current = null;
      }
    };
  }, [id, session?.status]);

  // Phase 1: Analyze remaining buffer when session ends or component unmounts
  useEffect(() => {
    // When session ends, analyze any remaining buffer
    if (session && session.status === 'ended' && transcriptBufferRef.current.trim().length > 0) {
      console.log('Session ended, analyzing remaining transcript in buffer');
      const remainingTranscript = transcriptBufferRef.current;
      transcriptBufferRef.current = '';
      
      // Include previous chunk for context if available
      const transcriptToAnalyze = previousChunkRef.current 
        ? `${previousChunkRef.current} ${remainingTranscript}`.trim()
        : remainingTranscript;
      
      analyzeBufferedTranscript(transcriptToAnalyze).catch(err => {
        console.error('Error analyzing remaining transcript on session end:', err);
      });
    }
    
    // Cleanup on unmount
    return () => {
      // Clear timer
      if (analysisTimerRef.current) {
        clearInterval(analysisTimerRef.current);
        analysisTimerRef.current = null;
      }

      // Analyze remaining buffer if session is active
      if (transcriptBufferRef.current.trim().length > 0 && id && session?.status === 'active') {
        console.log('Component unmounting, analyzing remaining transcript in buffer');
        const remainingTranscript = transcriptBufferRef.current;
        transcriptBufferRef.current = '';
        
        // Include previous chunk for context if available
        const transcriptToAnalyze = previousChunkRef.current 
          ? `${previousChunkRef.current} ${remainingTranscript}`.trim()
          : remainingTranscript;
        
        analyzeBufferedTranscript(transcriptToAnalyze).catch(err => {
          console.error('Error analyzing remaining transcript on unmount:', err);
        });
      }
    };
  }, [id, session?.status]);

  const fetchSession = async (opts?: { mode?: 'initial' | 'refresh' }) => {
    const mode = opts?.mode ?? (session ? 'refresh' : 'initial');
    try {
      if (mode === 'initial') {
        setLoading(true);
        setError('');
      } else {
        setRefreshing(true);
        setRefreshError('');
      }
      const response = await api.get(`/sessions/${id}`);
      setSession(response.data);
    } catch (err: any) {
      if (mode === 'initial') {
        setError(err.response?.data?.error || 'Failed to load session');
      } else {
        setRefreshError(err.response?.data?.error || 'Failed to refresh session');
        console.error('Failed to refresh session', err);
      }
    } finally {
      if (mode === 'initial') {
        setLoading(false);
      } else {
        setRefreshing(false);
      }
    }
  };

  const fetchTranscripts = async () => {
    try {
      const response = await api.get<TranscriptSegment[]>(`/sessions/${id}/transcripts`, {
        params: { limit: 1000 },
      });
      setTranscriptSegments(response.data || []);
    } catch (err) {
      // Don't block the whole screen if transcripts fail to load
      console.error('Failed to load transcripts', err);
    }
  };

  const generateClientChunkId = () => {
    try {
      return crypto.randomUUID();
    } catch {
      return `chunk_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    }
  };

  const persistTranscriptSegment = (text: string) => {
    if (!id) return;
    const client_chunk_id = generateClientChunkId();
    const client_timestamp_ms = Date.now();

    // Optimistic UI entry (no server id yet)
    setTranscriptSegments((prev) => [
      ...prev,
      {
        id: -1,
        session_id: parseInt(id),
        client_chunk_id,
        client_timestamp_ms,
        text,
        speaker: null,
        created_at: new Date().toISOString(),
      },
    ]);

    // Serialize writes to preserve order
    persistQueueRef.current = persistQueueRef.current.then(async () => {
      try {
        const res = await api.post<TranscriptSegment>(`/sessions/${id}/transcripts`, {
          client_chunk_id,
          client_timestamp_ms,
          text,
          speaker: null,
        });
        const saved = res.data;
        setTranscriptSegments((prev) => {
          const idx = prev.findIndex((s) => s.client_chunk_id === client_chunk_id);
          if (idx === -1) return [...prev, saved];
          const next = [...prev];
          next[idx] = saved;
          return next;
        });
      } catch (err) {
        console.error('Failed to persist transcript segment', err);
      }
    });
  };

  const clearTranscripts = async () => {
    if (!id) return;
    try {
      await api.delete(`/sessions/${id}/transcripts`);
    } catch (err) {
      console.error('Failed to clear transcripts', err);
    } finally {
      setTranscriptSegments([]);
    }
  };

  const updateTranscriptSegment = async (segmentId: number, patch: { speaker?: string | null; text?: string }) => {
    if (!id) return;
    if (segmentId <= 0) return; // ignore optimistic entries
    try {
      const res = await api.put<TranscriptSegment>(`/sessions/${id}/transcripts/${segmentId}`, patch);
      const updated = res.data;
      setTranscriptSegments((prev) => prev.map((s) => (s.id === segmentId ? updated : s)));
    } catch (err) {
      console.error('Failed to update transcript segment', err);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatTime = (msOrIso: number | string | null | undefined) => {
    if (!msOrIso) return '';
    const d = typeof msOrIso === 'number' ? new Date(msOrIso) : new Date(msOrIso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  // Component to display time-based analysis status
  const TimeBasedAnalysisStatus = () => {
    const [timeSinceLastAnalysis, setTimeSinceLastAnalysis] = useState<number>(0);

    useEffect(() => {
      const updateStatus = () => {
        if (lastAnalysisTime > 0) {
          setTimeSinceLastAnalysis(Math.floor((Date.now() - lastAnalysisTime) / 1000));
        }
      };

      updateStatus();
      const interval = setInterval(updateStatus, 1000); // Update every second
      return () => clearInterval(interval);
    }, [lastAnalysisTime]);

    return (
      <div className="mt-4 bg-neutral-900/60 border border-neutral-800 rounded-2xl p-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-neutral-200">
            Analysis interval: Every <span className="font-semibold">{ANALYSIS_INTERVAL_MS / 1000}</span> seconds
            {bufferLength > 0 && (
              <span className="ml-2 text-neutral-400">
                ({bufferLength} chars buffered)
              </span>
            )}
          </span>
          {lastAnalysisTime > 0 && (
            <span className="text-xs text-neutral-400">
              Last analysis: {timeSinceLastAnalysis}s ago
            </span>
          )}
        </div>
      </div>
    );
  };

  /**
   * Trigger analysis of the current buffer
   * Includes previous chunk for context
   */
  const triggerAnalysis = () => {
    if (!transcriptBufferRef.current.trim()) {
      return;
    }

    const currentChunk = transcriptBufferRef.current.trim();
    
    // Include previous chunk for context to avoid cutting off character names
    const transcriptToAnalyze = previousChunkRef.current 
      ? `${previousChunkRef.current} ${currentChunk}`.trim()
      : currentChunk;
    
    // Clear buffer for next accumulation cycle
    transcriptBufferRef.current = '';
    setBufferLength(0);
    
    // Update last analysis time
    const now = Date.now();
    lastAnalysisTimeRef.current = now;
    setLastAnalysisTime(now);
    
    console.log(`📊 Analyzing transcript (time-based, ${transcriptToAnalyze.length} chars)`);
    console.log(`📄 Full context: "${transcriptToAnalyze}"`);
    
    // Trigger analysis (don't await to avoid blocking, but handle errors)
    // Pass currentChunk as fallback in case backend doesn't return previous_chunk_for_next_analysis
    analyzeBufferedTranscript(transcriptToAnalyze, currentChunk).catch(err => {
      console.error('Error in buffered transcript analysis:', err);
    });
  };

  /**
   * Analyze the buffered transcript and process events
   */
  const analyzeBufferedTranscript = async (transcriptToAnalyze: string, fallbackChunk?: string) => {
    if (!session || !id) return;

    // Only analyze if transcript has meaningful content
    if (transcriptToAnalyze.trim().length < 10) {
      console.log('Transcript too short, skipping analysis');
      return;
    }

    try {
      setAnalyzing(true);
      console.log(`🔍 Analyzing transcript:`, transcriptToAnalyze);
      
      const result = await analyzeTranscript(transcriptToAnalyze, parseInt(id));
      
      console.log('✅ Analysis complete:', result);

      // Phase 4: Store previous_chunk_for_next_analysis if returned from backend
      // Check if property exists (even if empty string) to distinguish from undefined
      if (result.previous_chunk_for_next_analysis !== undefined) {
        previousChunkRef.current = result.previous_chunk_for_next_analysis;
        if (result.previous_chunk_for_next_analysis) {
          console.log(`📦 Stored previous_chunk_for_next_analysis (${result.previous_chunk_for_next_analysis.length} chars)`);
        } else {
          console.log(`📦 Stored empty previous_chunk_for_next_analysis (last event was at end of transcript)`);
        }
      } else if (fallbackChunk) {
        // Fallback: use current chunk if backend doesn't return previous_chunk_for_next_analysis
        previousChunkRef.current = fallbackChunk;
        console.log(`📦 Stored fallback chunk (${fallbackChunk.length} chars)`);
      } else {
        // No previous chunk and no fallback - clear it
        previousChunkRef.current = '';
        console.log(`📦 Cleared previous chunk (no data from backend)`);
      }

      // Phase 8: Save detected events to the database
      // Events are now saved directly by the backend in the /analyze endpoint
      // Just refresh the session data to show updated state
      if (result.events.length > 0) {
        console.log(`✅ Backend saved ${result.events.length} event(s) directly`);
        // Refresh session data to show updated HP, events, and other state
        await fetchSession({ mode: 'refresh' });
      }
    } catch (err: any) {
      console.error('❌ Error analyzing transcript:', err);
      // Don't show error to user for every failed analysis, just log it
      // Analysis failures shouldn't break the transcription flow
    } finally {
      setAnalyzing(false);
    }
  };

  /**
   * Phase 1: Handle transcript with time-based analysis (every 25 seconds)
   * Accumulates transcript chunks in a buffer
   * Analysis is triggered automatically by the timer every 25 seconds
   * Includes previous chunk for context to avoid cutting off character names
   */
  const handleTranscript = useCallback((transcript: string) => {
    // Use refs to avoid recreating callback when session changes
    // Only check if we have an id (session should exist if LiveScribe is rendered)
    if (!id) return;

    // Add new transcript to buffer
    if (transcriptBufferRef.current) {
      transcriptBufferRef.current += ' ' + transcript;
    } else {
      transcriptBufferRef.current = transcript;
    }

    const currentBufferLength = transcriptBufferRef.current.trim().length;
    setBufferLength(currentBufferLength);
    console.log(`📝 Transcript buffer: ${currentBufferLength} characters (analysis every ${ANALYSIS_INTERVAL_MS / 1000} seconds)`);

    // Persist committed segments to backend (maintained transcription)
    if (transcript && transcript.trim()) {
      persistTranscriptSegment(transcript.trim());
    }
    
    // Analysis will be triggered by the timer, just accumulate here
  }, [id]);

  // Only show the blocking loader when we don't have any session data yet.
  if (loading && !session) {
    return (
      <div className="text-center py-8">
        <div className="text-neutral-300">Loading session...</div>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl">
          {error || 'Session not found'}
        </div>
        <button
          onClick={() => navigate('/sessions')}
          className="mt-4 px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium"
        >
          Back to Sessions
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/sessions')}
          className="text-white/70 hover:text-white mb-4 transition-colors text-sm"
        >
          ← Back to Sessions
        </button>
        <div className="flex justify-between items-center">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-white">{session.name}</h1>
              {refreshing ? (
                <span className="text-xs text-neutral-400" title="Refreshing session data…">
                  Refreshing…
                </span>
              ) : null}
              {session.status === 'active' && (
                <button
                  type="button"
                  onClick={() => {
                    setRecorderMounted(true);
                    setRecording((v) => !v);
                  }}
                  className={[
                    'shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-xl transition-colors text-sm font-medium border',
                    recording
                      ? 'bg-red-500/15 text-red-200 border-red-500/30 hover:bg-red-500/20'
                      : 'bg-white/5 text-white border-white/10 hover:bg-white/10',
                  ].join(' ')}
                  title={recording ? 'Stop recording' : 'Start recording'}
                >
                  <span
                    className={[
                      'inline-block h-2 w-2 rounded-full',
                      recording ? 'bg-red-400 animate-pulse' : 'bg-white/30',
                    ].join(' ')}
                    aria-hidden="true"
                  />
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      d="M12 14a3 3 0 0 0 3-3V7a3 3 0 1 0-6 0v4a3 3 0 0 0 3 3Z"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M19 11a7 7 0 0 1-14 0"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M12 18v3"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M8 21h8"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span className="hidden sm:inline">{recording ? 'Recording' : 'Record'}</span>
                </button>
              )}
            </div>
            <p className="text-neutral-300 mt-2">
              Started: {formatDate(session.started_at)}
            </p>
            {refreshError ? <p className="text-xs text-amber-200/90 mt-1">{refreshError}</p> : null}
            {session.status === 'active' && recording && (
              <p className="text-xs text-neutral-400 mt-1">
                {scribeStatus === 'connected'
                  ? 'Listening…'
                  : scribeStatus === 'connecting' || scribeStatus === 'getting-token'
                    ? 'Starting…'
                    : scribeStatus === 'error'
                      ? scribeError || 'Recording error'
                      : scribePermission === false
                        ? 'Microphone permission required'
                        : 'Starting…'}
                {analyzing ? <span className="ml-2 text-sky-200/80">Analyzing…</span> : null}
              </p>
            )}
            {session.ended_at && (
              <p className="text-neutral-300">Ended: {formatDate(session.ended_at)}</p>
            )}
          </div>
          <span
            className={`px-3 py-1 text-sm rounded-full border ${
              session.status === 'active'
                ? 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30'
                : 'bg-white/10 text-white/70 border-white/15'
            }`}
          >
            {session.status}
          </span>
        </div>
      </div>

      {(recording || transcriptSegments.length > 0) && (
        <div className="mb-6">
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-white">Transcript</div>
                <div className="text-xs text-neutral-400">
                  {recording ? 'Live transcription is running (and being saved).' : 'Transcript from this session.'}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 bg-neutral-950 border border-neutral-800 rounded-xl p-1">
                  {(['lines', 'full', 'annotated'] as TranscriptMode[]).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setTranscriptMode(mode)}
                      className={[
                        'px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors',
                        transcriptMode === mode ? 'bg-white/10 text-white' : 'text-neutral-300 hover:text-white',
                      ].join(' ')}
                    >
                      {mode === 'lines' ? 'Lines' : mode === 'full' ? 'Full' : 'Annotated'}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={clearTranscripts}
                  className="px-3 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-xs font-medium"
                  title="Deletes the saved transcript for this session"
                >
                  Clear
                </button>
              </div>
            </div>

            {session.status === 'active' ? <TimeBasedAnalysisStatus /> : null}

            <div className="mt-3 bg-neutral-950 border border-neutral-800 rounded-2xl p-3 max-h-44 overflow-y-auto">
              {transcriptSegments.length === 0 ? (
                <div className="text-sm text-neutral-400 italic">No transcript yet.</div>
              ) : (
                <>
                  {transcriptMode === 'full' ? (
                    <div className="text-sm text-neutral-100 whitespace-pre-wrap">
                      {transcriptSegments.map((s) => s.text).join('\n')}
                    </div>
                  ) : transcriptMode === 'annotated' ? (
                    <div className="space-y-2">
                      {transcriptSegments.map((s) => (
                        <div key={s.client_chunk_id} className="grid grid-cols-1 sm:grid-cols-[120px_1fr] gap-2">
                          <div className="flex items-center gap-2">
                            <div className="text-[11px] text-neutral-500 w-16 shrink-0">
                              {formatTime(s.client_timestamp_ms || s.created_at)}
                            </div>
                            <input
                              value={s.speaker || ''}
                              onChange={(e) => {
                                const v = e.target.value;
                                setTranscriptSegments((prev) =>
                                  prev.map((x) => (x.client_chunk_id === s.client_chunk_id ? { ...x, speaker: v } : x))
                                );
                              }}
                              onBlur={(e) => updateTranscriptSegment(s.id, { speaker: e.target.value || null })}
                              placeholder="Speaker"
                              className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-2 py-1 text-xs text-neutral-100 placeholder:text-neutral-500"
                              disabled={s.id <= 0}
                            />
                          </div>
                          <textarea
                            value={s.text}
                            onChange={(e) => {
                              const v = e.target.value;
                              setTranscriptSegments((prev) =>
                                prev.map((x) => (x.client_chunk_id === s.client_chunk_id ? { ...x, text: v } : x))
                              );
                            }}
                            onBlur={(e) => updateTranscriptSegment(s.id, { text: e.target.value })}
                            className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-2 py-1 text-sm text-neutral-100 min-h-[36px]"
                            disabled={s.id <= 0}
                          />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {transcriptSegments.map((s) => (
                        <div key={s.client_chunk_id} className="text-sm text-neutral-100">
                          <span className="text-[11px] text-neutral-500 mr-2">
                            {formatTime(s.client_timestamp_ms || s.created_at)}
                          </span>
                          {s.text}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {session.status === 'active' && recorderMounted && (
        <LiveScribe
          key={session.id}
          hidden
          active={recording}
          onTranscript={handleTranscript}
          onStatusChange={setScribeStatus}
          onErrorChange={setScribeError}
          onPermissionChange={setScribePermission}
        />
      )}

      {/* Phase 1: Initiative Tracker */}
      {session.status === 'active' && id && (
        <div className="mb-6">
          <InitiativeTracker 
            sessionId={parseInt(id)} 
            onUpdate={() => fetchSession({ mode: 'refresh' })}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Characters */}
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Characters</h2>
          {session.characters.length === 0 ? (
            <p className="text-neutral-300">No characters in this session</p>
          ) : (
            <div className="space-y-4">
              {session.characters.map((char) => {
                const hpPercentage = (char.current_hp / char.max_hp) * 100;
                return (
                  <div
                    key={char.character_id}
                    onClick={() => {
                      setSelectedCharacterId(char.character_id);
                      setSelectedCharacterName(char.character_name);
                      setIsSidebarOpen(true);
                    }}
                    className="border border-white/10 rounded-2xl p-4 bg-neutral-950/40 cursor-pointer hover:bg-neutral-950/60 transition-colors"
                  >
                    <div className="flex justify-between items-center mb-2">
                      <h3 className="font-medium text-white">{char.character_name}</h3>
                      <span className="text-sm text-neutral-300">
                        {char.current_hp} / {char.max_hp} HP
                      </span>
                    </div>
                    <div className="w-full bg-white/10 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          hpPercentage > 50
                            ? 'bg-emerald-400'
                            : hpPercentage > 25
                            ? 'bg-amber-400'
                            : 'bg-red-400'
                        }`}
                        style={{ width: `${hpPercentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Events */}
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Event History</h2>
          {session.events.length === 0 ? (
            <p className="text-neutral-300">No events yet</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {session.events.map((event) => (
                <div
                  key={event.id}
                  className={`p-3 rounded border-l-4 ${
                    event.type === 'damage'
                      ? 'bg-red-500/10 border-red-500/70'
                      : event.type === 'healing'
                      ? 'bg-emerald-500/10 border-emerald-500/70'
                      : event.type === 'spell_cast'
                      ? 'bg-purple-500/10 border-purple-500/70'
                      : 'bg-neutral-500/10 border-neutral-500/70'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="font-medium text-white">
                        {event.character_name}
                      </span>
                      {event.type === 'spell_cast' ? (
                        <span className="ml-2 font-semibold text-purple-200">
                          cast {event.spell_name}
                          {event.spell_level !== undefined && event.spell_level > 0 && (
                            <span className="text-purple-300"> (level {event.spell_level})</span>
                          )}
                        </span>
                      ) : (
                        <span
                          className={`ml-2 font-semibold ${
                            event.type === 'damage' ? 'text-red-200' : 'text-emerald-200'
                          }`}
                        >
                          {event.type === 'damage' ? '-' : '+'}
                          {event.amount} HP
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-neutral-400">
                      {formatDate(event.timestamp)}
                    </span>
                  </div>
                  {event.transcript_segment && (
                    <p className="text-sm text-neutral-300 mt-1 italic">
                      "{event.transcript_segment}"
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Phase 2: Character Detail Sidebar */}
      {session.status === 'active' && id && (
        <CharacterDetailSidebar
          sessionId={parseInt(id)}
          characterId={selectedCharacterId}
          characterName={selectedCharacterName}
          isOpen={isSidebarOpen}
          onClose={() => {
            setIsSidebarOpen(false);
            setSelectedCharacterId(null);
            setSelectedCharacterName(null);
          }}
          onUpdate={() => fetchSession({ mode: 'refresh' })}
        />
      )}
    </div>
  );
}

