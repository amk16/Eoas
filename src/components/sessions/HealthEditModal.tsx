import { useState, useEffect } from 'react';
import api from '../../services/api';

interface HealthEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  characterId: number | string;  // Can be string (Firestore) or number (legacy)
  characterName: string;
  currentHp: number;
  maxHp: number;
  sessionId: string;
  onSave?: () => void;
}

export default function HealthEditModal({
  isOpen,
  onClose,
  characterId,
  characterName,
  currentHp,
  maxHp,
  sessionId,
  onSave,
}: HealthEditModalProps) {
  const [newHp, setNewHp] = useState<number>(currentHp);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setNewHp(currentHp);
      setError('');
    }
  }, [isOpen, currentHp]);

  if (!isOpen) return null;

  const handleSave = async () => {
    // Validate
    if (newHp < 0 || newHp > maxHp) {
      setError(`HP must be between 0 and ${maxHp}`);
      return;
    }

    if (newHp === currentHp) {
      onClose();
      return;
    }

    try {
      setLoading(true);
      setError('');

      // Calculate the difference
      const difference = newHp - currentHp;
      const amount = Math.abs(difference);
      const eventType = difference > 0 ? 'healing' : 'damage';

      // Create event
      await api.post(`/sessions/${sessionId}/event`, {
        type: eventType,
        character_id: characterId,
        amount: amount,
      });

      // Call onSave callback if provided
      if (onSave) {
        onSave();
      }

      onClose();
    } catch (err: any) {
      console.error('Failed to update health:', err);
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to update health');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

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
          className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 max-w-md w-full"
          onClick={(e) => e.stopPropagation()}
        >
          <h3 className="text-xl font-semibold text-white mb-4">Edit Health</h3>

          <div className="mb-4">
            <label className="block text-sm font-medium text-neutral-300 mb-2">
              {characterName}
            </label>
            <div className="text-sm text-neutral-400 mb-4">
              Current: {currentHp} / {maxHp} HP
            </div>

            <label className="block text-sm font-medium text-neutral-300 mb-2" htmlFor="new-hp">
              New HP (0 - {maxHp})
            </label>
            <input
              id="new-hp"
              type="number"
              min={0}
              max={maxHp}
              value={newHp}
              onChange={(e) => {
                const value = parseInt(e.target.value, 10);
                if (!isNaN(value)) {
                  setNewHp(Math.max(0, Math.min(maxHp, value)));
                } else if (e.target.value === '') {
                  setNewHp(0);
                }
              }}
              onKeyDown={handleKeyDown}
              className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />

            {error && (
              <p className="mt-2 text-sm text-red-400">{error}</p>
            )}

            {newHp !== currentHp && (
              <div className="mt-3 p-3 bg-neutral-950 border border-neutral-800 rounded-lg">
                <p className="text-sm text-neutral-300">
                  {newHp > currentHp ? (
                    <span className="text-emerald-400">
                      +{newHp - currentHp} HP (healing)
                    </span>
                  ) : (
                    <span className="text-red-400">
                      {newHp - currentHp} HP (damage)
                    </span>
                  )}
                </p>
              </div>
            )}
          </div>

          <div className="flex gap-3 justify-end">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={loading || newHp === currentHp}
              className="px-4 py-2 bg-blue-500/15 text-blue-200 border border-blue-500/30 rounded-xl hover:bg-blue-500/20 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

