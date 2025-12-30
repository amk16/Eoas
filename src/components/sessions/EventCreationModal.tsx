import { useState, useEffect } from 'react';
import api from '../../services/api';

interface SessionCharacter {
  character_id: number | string;  // Can be string (Firestore) or number (legacy)
  character_name: string;
}

interface EventCreationModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId: string;
  characters: SessionCharacter[];
  onEventCreated?: () => void;
}

type EventType = 
  | 'damage'
  | 'healing'
  | 'initiative_roll'
  | 'spell_cast'
  | 'status_condition_applied'
  | 'status_condition_removed'
  | 'buff_debuff_applied'
  | 'buff_debuff_removed'
  | 'turn_advance'
  | 'round_start'
  | 'combat_end';

export default function EventCreationModal({
  isOpen,
  onClose,
  sessionId,
  characters,
  onEventCreated,
}: EventCreationModalProps) {
  const [eventType, setEventType] = useState<EventType>('damage');
  const [characterId, setCharacterId] = useState<number | string | null>(null);
  const [amount, setAmount] = useState<number>(0);
  const [initiativeValue, setInitiativeValue] = useState<number>(0);
  const [spellName, setSpellName] = useState<string>('');
  const [spellLevel, setSpellLevel] = useState<number>(1);
  const [conditionName, setConditionName] = useState<string>('');
  const [durationMinutes, setDurationMinutes] = useState<number | null>(null);
  const [effectName, setEffectName] = useState<string>('');
  const [effectType, setEffectType] = useState<'buff' | 'debuff'>('buff');
  const [stackingRule, setStackingRule] = useState<string>('replace');
  const [source, setSource] = useState<string>('');
  const [roundNumber, setRoundNumber] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  // Reset form when modal opens/closes or event type changes
  useEffect(() => {
    if (isOpen) {
      // Reset all fields
      setCharacterId(characters.length > 0 ? characters[0].character_id : null);
      setAmount(0);
      setInitiativeValue(0);
      setSpellName('');
      setSpellLevel(1);
      setConditionName('');
      setDurationMinutes(null);
      setEffectName('');
      setEffectType('buff');
      setStackingRule('replace');
      setSource('');
      setRoundNumber(null);
      setError('');
    }
  }, [isOpen, eventType, characters]);

  const requiresCharacter = (type: EventType): boolean => {
    return !['turn_advance', 'round_start', 'combat_end'].includes(type);
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setError('');

      const eventData: any = {
        type: eventType,
      };

      // Add character_id if required
      if (requiresCharacter(eventType)) {
        if (!characterId) {
          setError('Please select a character');
          return;
        }
        // character_id can be string (Firestore) or number (legacy), send as-is
        eventData.character_id = characterId;
      }

      // Add type-specific fields
      if (eventType === 'damage' || eventType === 'healing') {
        if (!amount || amount <= 0) {
          setError('Amount must be greater than 0');
          return;
        }
        eventData.amount = amount;
      } else if (eventType === 'initiative_roll') {
        eventData.initiative_value = initiativeValue;
      } else if (eventType === 'spell_cast') {
        if (!spellName.trim()) {
          setError('Spell name is required');
          return;
        }
        if (spellLevel < 0 || spellLevel > 9) {
          setError('Spell level must be between 0 and 9');
          return;
        }
        eventData.spell_name = spellName;
        eventData.spell_level = spellLevel;
      } else if (eventType === 'status_condition_applied') {
        if (!conditionName.trim()) {
          setError('Condition name is required');
          return;
        }
        eventData.condition_name = conditionName;
        if (durationMinutes !== null && durationMinutes >= 0) {
          eventData.duration_minutes = durationMinutes;
        }
      } else if (eventType === 'status_condition_removed') {
        if (!conditionName.trim()) {
          setError('Condition name is required');
          return;
        }
        eventData.condition_name = conditionName;
      } else if (eventType === 'buff_debuff_applied') {
        if (!effectName.trim()) {
          setError('Effect name is required');
          return;
        }
        eventData.effect_name = effectName;
        eventData.effect_type = effectType;
        eventData.stat_modifications = {}; // Simplified for now - can be enhanced later
        eventData.stacking_rule = stackingRule;
        if (source.trim()) {
          eventData.source = source;
        }
        if (durationMinutes !== null && durationMinutes >= 0) {
          eventData.duration_minutes = durationMinutes;
        }
      } else if (eventType === 'buff_debuff_removed') {
        if (!effectName.trim()) {
          setError('Effect name is required');
          return;
        }
        eventData.effect_name = effectName;
      } else if (eventType === 'round_start') {
        if (roundNumber !== null) {
          eventData.round_number = roundNumber;
        }
      }

      await api.post(`/sessions/${sessionId}/event`, eventData);

      if (onEventCreated) {
        onEventCreated();
      }

      onClose();
    } catch (err: any) {
      console.error('Failed to create event:', err);
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to create event');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <h3 className="text-xl font-semibold text-white mb-4">Create Event</h3>

          {/* Event Type Selection */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-neutral-300 mb-2">
              Event Type
            </label>
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value as EventType)}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="damage">Damage</option>
              <option value="healing">Healing</option>
              <option value="initiative_roll">Initiative Roll</option>
              <option value="spell_cast">Spell Cast</option>
              <option value="status_condition_applied">Status Condition Applied</option>
              <option value="status_condition_removed">Status Condition Removed</option>
              <option value="buff_debuff_applied">Buff/Debuff Applied</option>
              <option value="buff_debuff_removed">Buff/Debuff Removed</option>
              <option value="turn_advance">Turn Advance</option>
              <option value="round_start">Round Start</option>
              <option value="combat_end">Combat End</option>
            </select>
          </div>

          {/* Character Selection (if required) */}
          {requiresCharacter(eventType) && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Character
              </label>
                <select
                  value={characterId !== null ? String(characterId) : ''}
                  onChange={(e) => {
                    const value = e.target.value;
                    setCharacterId(value || null);
                  }}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {characters.map((char) => (
                    <option key={char.character_id} value={String(char.character_id)}>
                      {char.character_name}
                    </option>
                  ))}
                </select>
            </div>
          )}

          {/* Damage/Healing Fields */}
          {(eventType === 'damage' || eventType === 'healing') && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Amount
              </label>
              <input
                type="number"
                min={1}
                value={amount}
                onChange={(e) => setAmount(parseInt(e.target.value, 10) || 0)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Initiative Roll Fields */}
          {eventType === 'initiative_roll' && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Initiative Value
              </label>
              <input
                type="number"
                value={initiativeValue}
                onChange={(e) => setInitiativeValue(parseInt(e.target.value, 10) || 0)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {/* Spell Cast Fields */}
          {eventType === 'spell_cast' && (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Spell Name
                </label>
                <input
                  type="text"
                  value={spellName}
                  onChange={(e) => setSpellName(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Fireball"
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Spell Level (0-9, where 0 is cantrip)
                </label>
                <input
                  type="number"
                  min={0}
                  max={9}
                  value={spellLevel}
                  onChange={(e) => setSpellLevel(parseInt(e.target.value, 10) || 0)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </>
          )}

          {/* Status Condition Applied Fields */}
          {eventType === 'status_condition_applied' && (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Condition Name
                </label>
                <input
                  type="text"
                  value={conditionName}
                  onChange={(e) => setConditionName(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Poisoned, Stunned"
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Duration (minutes, optional)
                </label>
                <input
                  type="number"
                  min={0}
                  value={durationMinutes || ''}
                  onChange={(e) => setDurationMinutes(e.target.value ? parseInt(e.target.value, 10) : null)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Leave empty for indefinite"
                />
              </div>
            </>
          )}

          {/* Status Condition Removed Fields */}
          {eventType === 'status_condition_removed' && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Condition Name
              </label>
              <input
                type="text"
                value={conditionName}
                onChange={(e) => setConditionName(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Poisoned, Stunned"
              />
            </div>
          )}

          {/* Buff/Debuff Applied Fields */}
          {eventType === 'buff_debuff_applied' && (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Effect Name
                </label>
                <input
                  type="text"
                  value={effectName}
                  onChange={(e) => setEffectName(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Bless, Shield of Faith"
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Effect Type
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      value="buff"
                      checked={effectType === 'buff'}
                      onChange={(e) => setEffectType(e.target.value as 'buff')}
                      className="text-blue-500"
                    />
                    <span className="text-neutral-300">Buff</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      value="debuff"
                      checked={effectType === 'debuff'}
                      onChange={(e) => setEffectType(e.target.value as 'debuff')}
                      className="text-blue-500"
                    />
                    <span className="text-neutral-300">Debuff</span>
                  </label>
                </div>
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Stacking Rule
                </label>
                <select
                  value={stackingRule}
                  onChange={(e) => setStackingRule(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="none">None (don't apply if exists)</option>
                  <option value="replace">Replace (replace existing)</option>
                  <option value="stack">Stack (combine values)</option>
                  <option value="highest">Highest (keep highest value)</option>
                </select>
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Source (optional)
                </label>
                <input
                  type="text"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Spell name, Item name"
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-neutral-300 mb-2">
                  Duration (minutes, optional)
                </label>
                <input
                  type="number"
                  min={0}
                  value={durationMinutes || ''}
                  onChange={(e) => setDurationMinutes(e.target.value ? parseInt(e.target.value, 10) : null)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Leave empty for indefinite"
                />
              </div>
            </>
          )}

          {/* Buff/Debuff Removed Fields */}
          {eventType === 'buff_debuff_removed' && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Effect Name
              </label>
              <input
                type="text"
                value={effectName}
                onChange={(e) => setEffectName(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Bless, Shield of Faith"
              />
            </div>
          )}

          {/* Round Start Fields */}
          {eventType === 'round_start' && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-neutral-300 mb-2">
                Round Number (optional)
              </label>
              <input
                type="number"
                min={1}
                value={roundNumber || ''}
                onChange={(e) => setRoundNumber(e.target.value ? parseInt(e.target.value, 10) : null)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Leave empty to auto-increment"
              />
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-950/40 border border-red-900 text-red-200 text-sm rounded-xl">
              {error}
            </div>
          )}

          <div className="flex gap-3 justify-end">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-4 py-2 bg-blue-500/15 text-blue-200 border border-blue-500/30 rounded-xl hover:bg-blue-500/20 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create Event'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

