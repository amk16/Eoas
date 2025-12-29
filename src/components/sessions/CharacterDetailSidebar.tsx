import { useState, useEffect } from 'react';
import api from '../../services/api';

interface StatusCondition {
  session_id: number;
  character_id: number;
  character_name: string;
  condition_name: string;
  applied_at: string;
  expires_at: string | null;
  duration_minutes: number | null;
}

interface BuffDebuff {
  session_id: number;
  character_id: number;
  character_name: string;
  effect_name: string;
  effect_type: 'buff' | 'debuff';
  stat_modifications: Record<string, number>; // e.g., {"ac": 2, "attack_rolls": 1}
  stacking_rule: string;
  applied_at: string;
  expires_at: string | null;
  duration_minutes: number | null;
  source: string | null;
}

interface SpellSlotUsage {
  character_id: number;
  character_name: string;
  slots_by_level: Record<string, number>; // e.g., {"1": 3, "2": 1, "3": 0}
}

interface CharacterDetailSidebarProps {
  sessionId: number;
  characterId: number | null;
  characterName: string | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdate?: () => void;
}

export default function CharacterDetailSidebar({
  sessionId,
  characterId,
  characterName,
  isOpen,
  onClose,
  onUpdate,
}: CharacterDetailSidebarProps) {
  const [conditions, setConditions] = useState<StatusCondition[]>([]);
  const [buffsDebuffs, setBuffsDebuffs] = useState<BuffDebuff[]>([]);
  const [spellSlots, setSpellSlots] = useState<SpellSlotUsage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (isOpen && characterId) {
      // Only fetch when sidebar opens/character is selected, not on constant polling
      fetchConditions();
      fetchBuffsDebuffs();
      fetchSpellSlots();
    } else {
      setConditions([]);
      setBuffsDebuffs([]);
      setSpellSlots(null);
    }
  }, [isOpen, characterId, sessionId]);

  const fetchConditions = async () => {
    if (!characterId) return;
    
    try {
      setLoading(true);
      setError('');
      const response = await api.get(`/sessions/${sessionId}/status-conditions`);
      // Filter conditions for this character
      const characterConditions = response.data.filter(
        (c: StatusCondition) => c.character_id === characterId
      );
      setConditions(characterConditions);
    } catch (err: any) {
      console.error('Failed to fetch status conditions:', err);
      setError(err.response?.data?.detail || 'Failed to load status conditions');
    } finally {
      setLoading(false);
    }
  };

  const fetchBuffsDebuffs = async () => {
    if (!characterId) return;
    
    try {
      setError('');
      const response = await api.get(`/sessions/${sessionId}/characters/${characterId}/buffs-debuffs`);
      setBuffsDebuffs(response.data);
    } catch (err: any) {
      console.error('Failed to fetch buffs/debuffs:', err);
      // Don't set error for buffs/debuffs, just log it
    }
  };

  const fetchSpellSlots = async () => {
    if (!characterId) return;
    
    try {
      setError('');
      const response = await api.get(`/sessions/${sessionId}/characters/${characterId}/spell-slots`);
      setSpellSlots(response.data);
    } catch (err: any) {
      console.error('Failed to fetch spell slots:', err);
      // Don't set error for spell slots, just log it
    }
  };

  const handleRemoveCondition = async (conditionName: string) => {
    if (!characterId) return;
    
    try {
      setLoading(true);
      setError('');
      await api.post(`/sessions/${sessionId}/status-conditions/remove`, {
        character_id: characterId,
        condition_name: conditionName,
      });
      await fetchConditions();
      if (onUpdate) onUpdate();
    } catch (err: any) {
      console.error('Failed to remove condition:', err);
      setError(err.response?.data?.detail || 'Failed to remove condition');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveBuffDebuff = async (effectName: string) => {
    if (!characterId) return;
    
    try {
      setLoading(true);
      setError('');
      await api.post(`/sessions/${sessionId}/buffs-debuffs/remove`, {
        character_id: characterId,
        effect_name: effectName,
      });
      await fetchBuffsDebuffs();
      if (onUpdate) onUpdate();
    } catch (err: any) {
      console.error('Failed to remove buff/debuff:', err);
      setError(err.response?.data?.detail || 'Failed to remove buff/debuff');
    } finally {
      setLoading(false);
    }
  };

  const formatTimeRemaining = (expiresAt: string | null): string | null => {
    if (!expiresAt) return null;
    
    try {
      const expires = new Date(expiresAt);
      const now = new Date();
      const diffMs = expires.getTime() - now.getTime();
      
      if (diffMs <= 0) return 'Expired';
      
      const minutes = Math.floor(diffMs / 60000);
      const hours = Math.floor(minutes / 60);
      const days = Math.floor(hours / 24);
      
      if (days > 0) return `${days}d ${hours % 24}h`;
      if (hours > 0) return `${hours}h ${minutes % 60}m`;
      return `${minutes}m`;
    } catch {
      return null;
    }
  };

  if (!isOpen || !characterId || !characterName) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <div
        className={`fixed right-0 top-0 h-full w-full max-w-md bg-neutral-900 border-l border-neutral-800 z-50 transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-neutral-800">
            <h2 className="text-xl font-semibold text-white">{characterName}</h2>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              aria-label="Close"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-neutral-400"
              >
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {error && (
              <div className="mb-4 p-3 bg-red-950/40 border border-red-900 text-red-200 text-sm rounded-xl">
                {error}
              </div>
            )}

            {/* Status Conditions Section */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-white mb-4">Status Conditions</h3>
              
              {loading && conditions.length === 0 ? (
                <div className="text-sm text-neutral-400">Loading conditions...</div>
              ) : conditions.length === 0 ? (
                <p className="text-sm text-neutral-300">No active status conditions</p>
              ) : (
                <div className="space-y-2">
                  {conditions.map((condition, idx) => {
                    const timeRemaining = formatTimeRemaining(condition.expires_at);
                    const isExpired = timeRemaining === 'Expired';
                    
                    return (
                      <div
                        key={`${condition.condition_name}-${idx}`}
                        className={`flex items-center justify-between p-3 rounded-xl border ${
                          isExpired
                            ? 'bg-red-500/10 border-red-500/30'
                            : 'bg-neutral-950/40 border-white/10'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 text-xs rounded-full border ${
                            isExpired
                              ? 'bg-red-500/15 text-red-200 border-red-500/30'
                              : 'bg-amber-500/15 text-amber-200 border-amber-500/30'
                          }`}>
                            {condition.condition_name}
                          </span>
                          {timeRemaining && (
                            <span className="text-xs text-neutral-400">
                              {timeRemaining}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => handleRemoveCondition(condition.condition_name)}
                          disabled={loading}
                          className="px-2 py-1 text-xs bg-white/5 text-white border border-white/10 rounded-lg hover:bg-white/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          title="Remove condition"
                        >
                          Remove
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Buffs/Debuffs Section */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-white mb-4">Buffs & Debuffs</h3>
              
              {loading && buffsDebuffs.length === 0 ? (
                <div className="text-sm text-neutral-400">Loading effects...</div>
              ) : buffsDebuffs.length === 0 ? (
                <p className="text-sm text-neutral-300">No active buffs or debuffs</p>
              ) : (
                <div className="space-y-2">
                  {buffsDebuffs.map((effect, idx) => {
                    const timeRemaining = formatTimeRemaining(effect.expires_at);
                    const isExpired = timeRemaining === 'Expired';
                    const isBuff = effect.effect_type === 'buff';
                    
                    // Format stat modifications
                    const statMods = Object.entries(effect.stat_modifications || {})
                      .map(([stat, value]) => {
                        const sign = value >= 0 ? '+' : '';
                        return `${stat}: ${sign}${value}`;
                      })
                      .join(', ');
                    
                    return (
                      <div
                        key={`${effect.effect_name}-${idx}`}
                        className={`flex flex-col gap-2 p-3 rounded-xl border ${
                          isExpired
                            ? 'bg-red-500/10 border-red-500/30'
                            : isBuff
                            ? 'bg-emerald-500/10 border-emerald-500/30'
                            : 'bg-purple-500/10 border-purple-500/30'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-1 text-xs rounded-full border ${
                              isExpired
                                ? 'bg-red-500/15 text-red-200 border-red-500/30'
                                : isBuff
                                ? 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30'
                                : 'bg-purple-500/15 text-purple-200 border-purple-500/30'
                            }`}>
                              {effect.effect_name}
                            </span>
                            {timeRemaining && (
                              <span className="text-xs text-neutral-400">
                                {timeRemaining}
                              </span>
                            )}
                          </div>
                          <button
                            onClick={() => handleRemoveBuffDebuff(effect.effect_name)}
                            disabled={loading}
                            className="px-2 py-1 text-xs bg-white/5 text-white border border-white/10 rounded-lg hover:bg-white/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Remove effect"
                          >
                            Remove
                          </button>
                        </div>
                        {statMods && (
                          <div className="text-xs text-neutral-300">
                            <span className="text-neutral-400">Modifications: </span>
                            {statMods}
                          </div>
                        )}
                        {effect.source && (
                          <div className="text-xs text-neutral-400">
                            Source: {effect.source}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Spell Slots Section */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-white mb-4">Spell Slots Used</h3>
              
              {loading && !spellSlots ? (
                <div className="text-sm text-neutral-400">Loading spell slots...</div>
              ) : !spellSlots || Object.keys(spellSlots.slots_by_level || {}).length === 0 ? (
                <p className="text-sm text-neutral-300">No spell slots used yet</p>
              ) : (
                <div className="space-y-2">
                  {Object.entries(spellSlots.slots_by_level)
                    .sort(([levelA], [levelB]) => parseInt(levelA) - parseInt(levelB))
                    .map(([level, slotsUsed]) => {
                      const levelNum = parseInt(level);
                      const levelLabel = levelNum === 0 ? 'Cantrip' : `Level ${levelNum}`;
                      
                      return (
                        <div
                          key={level}
                          className="flex items-center justify-between p-3 rounded-xl border bg-blue-500/10 border-blue-500/30"
                        >
                          <div className="flex items-center gap-3">
                            <span className="px-2 py-1 text-xs rounded-full border bg-blue-500/15 text-blue-200 border-blue-500/30">
                              {levelLabel}
                            </span>
                            <span className="text-sm text-neutral-300">
                              {slotsUsed} {slotsUsed === 1 ? 'slot' : 'slots'} used
                            </span>
                          </div>
                        </div>
                      );
                    })}
                </div>
              )}
            </div>

            {/* Placeholder for future additions */}
            {/* Additional character details can be added here */}
          </div>
        </div>
      </div>
    </>
  );
}

