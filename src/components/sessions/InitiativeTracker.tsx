import { useState, useEffect } from 'react';
import api from '../../services/api';
import Stepper, { type StepperStep } from '../ui/Stepper';

type ViewMode = 'list' | 'stepper';

interface InitiativeCharacter {
  character_id: number;
  character_name: string;
  initiative_value: number;
  turn_order: number;
}

interface CombatState {
  is_active: boolean;
  current_round: number;
  current_turn_character_id: number | null;
  current_turn_character_name: string | null;
  initiative_order: InitiativeCharacter[];
}

interface InitiativeTrackerProps {
  sessionId: number;
  onUpdate?: () => void;
}

export default function InitiativeTracker({ sessionId, onUpdate }: InitiativeTrackerProps) {
  const [combatState, setCombatState] = useState<CombatState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [viewMode, setViewMode] = useState<ViewMode>('list');

  const fetchCombatState = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await api.get(`/sessions/${sessionId}/combat-state`);
      setCombatState(response.data);
    } catch (err: any) {
      console.error('Failed to fetch combat state:', err);
      setError(err.response?.data?.detail || 'Failed to load combat state');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (sessionId) {
      fetchCombatState();
      
      // Poll for updates every 2 seconds
      const interval = setInterval(fetchCombatState, 2000);
      return () => clearInterval(interval);
    }
  }, [sessionId]);

  const handleAdvanceTurn = async () => {
    try {
      setLoading(true);
      setError('');
      await api.post(`/sessions/${sessionId}/initiative/advance`, {});
      await fetchCombatState();
      if (onUpdate) onUpdate();
    } catch (err: any) {
      console.error('Failed to advance turn:', err);
      setError(err.response?.data?.detail || 'Failed to advance turn');
    } finally {
      setLoading(false);
    }
  };

  if (!combatState) {
    if (loading) {
      return (
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
          <div className="text-sm text-neutral-400">Loading combat state...</div>
        </div>
      );
    }
    
    return (
      <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Initiative Tracker</h2>
        <p className="text-sm text-neutral-300">No combat active. Roll initiative to begin tracking turns.</p>
      </div>
    );
  }

  if (!combatState.is_active || combatState.initiative_order.length === 0) {
    return (
      <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Initiative Tracker</h2>
        <p className="text-sm text-neutral-300">No combat active. Roll initiative to begin tracking turns.</p>
      </div>
    );
  }

  // Find current turn index for stepper
  const currentTurnIndex = combatState.initiative_order.findIndex(
    (char) => char.character_id === combatState.current_turn_character_id
  );

  // Convert initiative order to stepper steps
  const stepperSteps: StepperStep[] = combatState.initiative_order.map((char) => ({
    id: `char-${char.character_id}`,
    title: char.character_name,
    description: `Initiative: ${char.initiative_value}`,
  }));

  return (
    <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-white">Initiative Tracker</h2>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-neutral-400">Round</div>
            <div className="text-2xl font-bold text-white">{combatState.current_round}</div>
          </div>
        </div>
      </div>

      {/* View Mode Toggle */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-1 bg-neutral-950 border border-neutral-800 rounded-xl p-1">
          {(['list', 'stepper'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              className={[
                'px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors',
                viewMode === mode ? 'bg-white/10 text-white' : 'text-neutral-300 hover:text-white',
              ].join(' ')}
            >
              {mode === 'list' ? 'List' : 'Stepper'}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-950/40 border border-red-900 text-red-200 text-sm rounded-xl">
          {error}
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <div className="space-y-2 mb-4 max-h-96 overflow-y-auto">
          {combatState.initiative_order.map((char) => {
            const isCurrentTurn = char.character_id === combatState.current_turn_character_id;
            
            return (
              <div
                key={char.character_id}
                className={`border rounded-2xl p-4 transition-colors ${
                  isCurrentTurn
                    ? 'bg-emerald-500/15 border-emerald-500/30'
                    : 'bg-neutral-950/40 border-white/10'
                }`}
              >
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-neutral-400 w-8">#{char.turn_order}</span>
                      <span className={`font-medium ${isCurrentTurn ? 'text-emerald-200' : 'text-white'}`}>
                        {char.character_name}
                      </span>
                      {isCurrentTurn && (
                        <span className="px-2 py-1 text-xs rounded-full bg-emerald-500/15 text-emerald-200 border border-emerald-500/30">
                          Current Turn
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-sm text-neutral-300">
                    Initiative: <span className="font-semibold">{char.initiative_value}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Stepper View */}
      {viewMode === 'stepper' && (
        <div className="mb-4">
          <Stepper 
            steps={stepperSteps} 
            activeIndex={currentTurnIndex >= 0 ? currentTurnIndex : 0}
          />
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleAdvanceTurn}
          disabled={loading}
          className="px-3 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Advancing...' : 'Advance Turn'}
        </button>
      </div>
    </div>
  );
}

