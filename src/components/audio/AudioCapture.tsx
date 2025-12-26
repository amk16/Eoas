import { useState, useRef, useEffect } from 'react';
import { transcribeAudioChunk } from '../../services/audioService';

interface AudioCaptureProps {
  onAudioChunk?: (chunk: Blob) => void;
  onRecordingStateChange?: (isRecording: boolean) => void;
  onTranscript?: (transcript: string) => void;
}

export default function AudioCapture({ onAudioChunk, onRecordingStateChange, onTranscript }: AudioCaptureProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [error, setError] = useState<string>('');
  const [audioLevel, setAudioLevel] = useState(0);
  const [transcript, setTranscript] = useState<string>('');
  const [isTranscribing, setIsTranscribing] = useState(false);
  const transcriptHistoryRef = useRef<string[]>([]);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    // Check for microphone permission on mount
    checkMicrophonePermission();

    return () => {
      // Cleanup on unmount
      stopRecording();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  const checkMicrophonePermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // If we get here, permission was granted
      stream.getTracks().forEach(track => track.stop());
      setHasPermission(true);
      setError('');
    } catch (err: any) {
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

  const requestMicrophoneAccess = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      setHasPermission(true);
      setError('');
    } catch (err: any) {
      setHasPermission(false);
      setError('Failed to access microphone: ' + err.message);
    }
  };

  const startAudioLevelMonitoring = (stream: MediaStream) => {
    try {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      const microphone = audioContext.createMediaStreamSource(stream);
      
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;
      microphone.connect(analyser);
      
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const updateAudioLevel = () => {
        if (!analyserRef.current) return;

        analyserRef.current.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;
        setAudioLevel(Math.min(100, (average / 255) * 100));

        if (isRecording) {
          animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
        }
      };

      updateAudioLevel();
    } catch (err) {
      console.error('Error setting up audio level monitoring:', err);
    }
  };

  const startRecording = async () => {
    try {
      setError('');
      
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });

      streamRef.current = stream;
      setHasPermission(true);

      // Set up MediaRecorder
      const options = {
        mimeType: 'audio/webm;codecs=opus',
      };

      let mimeType = options.mimeType;
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = 'audio/ogg';
          if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = ''; // Use default
          }
        }
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      const chunks: Blob[] = [];

      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
          // Call callback if provided
          if (onAudioChunk) {
            onAudioChunk(event.data);
          }

          // Transcribe the chunk
          try {
            setIsTranscribing(true);
            const result = await transcribeAudioChunk(event.data);
            if (result.transcript) {
              transcriptHistoryRef.current.push(result.transcript);
              const fullTranscript = transcriptHistoryRef.current.join(' ');
              setTranscript(fullTranscript);
              if (onTranscript) {
                onTranscript(result.transcript);
              }
            }
          } catch (err: any) {
            console.error('Transcription error:', err);
            // Don't show error to user for each chunk, just log it
          } finally {
            setIsTranscribing(false);
          }
        }
      };

      mediaRecorder.onstop = () => {
        // Create final blob from all chunks
        const blob = new Blob(chunks, { type: mimeType || 'audio/webm' });
        console.log('Recording stopped. Total size:', blob.size, 'bytes');
      };

      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event);
        setError('Recording error occurred');
      };

      // Start recording with 1 second intervals
      mediaRecorder.start(1000);
      setIsRecording(true);
      onRecordingStateChange?.(true);

      // Start audio level monitoring
      startAudioLevelMonitoring(stream);
    } catch (err: any) {
      console.error('Error starting recording:', err);
      setHasPermission(false);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError('Microphone permission denied. Please allow microphone access.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone found. Please connect a microphone.');
      } else {
        setError('Error starting recording: ' + err.message);
      }
      setIsRecording(false);
      onRecordingStateChange?.(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      onRecordingStateChange?.(false);
      setAudioLevel(0);
      // Keep transcript history for now, user can clear manually
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  };

  if (hasPermission === false && error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
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
          <h3 className="text-lg font-medium text-gray-900 mb-2">Microphone Access Required</h3>
          <p className="text-sm text-gray-600 mb-4">{error}</p>
          <button
            onClick={requestMicrophoneAccess}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Request Access
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Audio Recording</h3>
        <div className="flex items-center gap-2">
          {isRecording && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-red-600 font-medium">Recording</span>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {/* Audio Level Indicator */}
      {isRecording && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm text-gray-600">Audio Level:</span>
            <div className="flex-1 bg-gray-200 rounded-full h-2">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-100"
                style={{ width: `${audioLevel}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 w-12 text-right">{Math.round(audioLevel)}%</span>
          </div>
        </div>
      )}

      {/* Recording Controls */}
      <div className="flex gap-4">
        {!isRecording ? (
          <button
            onClick={startRecording}
            disabled={hasPermission === false}
            className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
            Start Recording
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 flex items-center justify-center gap-2"
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
            Stop Recording
          </button>
        )}
      </div>

      {/* Transcription Display */}
      {(transcript || isTranscribing) && (
        <div className="mt-6 border-t pt-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-700">Live Transcript</h4>
            {isTranscribing && (
              <span className="text-xs text-indigo-600 animate-pulse">Transcribing...</span>
            )}
          </div>
          <div className="bg-gray-50 rounded-lg p-4 max-h-48 overflow-y-auto">
            {transcript ? (
              <p className="text-sm text-gray-800 whitespace-pre-wrap">{transcript}</p>
            ) : (
              <p className="text-sm text-gray-400 italic">Waiting for audio...</p>
            )}
          </div>
          {transcript && (
            <button
              onClick={() => {
                setTranscript('');
                transcriptHistoryRef.current = [];
              }}
              className="mt-2 text-xs text-gray-500 hover:text-gray-700"
            >
              Clear transcript
            </button>
          )}
        </div>
      )}
    </div>
  );
}

