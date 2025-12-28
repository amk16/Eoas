import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import type { Campaign, Character } from '../../types';
import Drawer from '../ui/Drawer';
import Stepper, { type StepperStep } from '../ui/Stepper';

type SessionDraft = {
  name: string;
  campaign_id: string | null;
  character_ids: string[];
};

const steps: StepperStep[] = [
  { id: 'basics', title: 'Basics', description: 'Name & campaign' },
  { id: 'party', title: 'Party', description: 'Select characters' },
  { id: 'review', title: 'Review', description: 'Confirm & start' },
];

function parseIntOrNull(v: string | null): number | null {
  if (!v) return null;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
}

export default function SessionWizardDrawer({
  open,
  presetCampaignId,
  onClose,
}: {
  open: boolean;
  presetCampaignId?: string | null;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [draft, setDraft] = useState<SessionDraft>({
    name: '',
    campaign_id: presetCampaignId ?? null,
    character_ids: [],
  });

  useEffect(() => {
    if (!open) return;
    setError('');
    setActiveStep(0);
    setDraft({ name: '', campaign_id: presetCampaignId ?? null, character_ids: [] });
  }, [open, presetCampaignId]);

  useEffect(() => {
    if (!open) return;
    api
      .get('/campaigns')
      .then((r) => setCampaigns(r.data))
      .catch(() => setCampaigns([]));
    api
      .get('/characters')
      .then((r) => setCharacters(r.data))
      .catch(() => setCharacters([]));
  }, [open]);

  const validation = useMemo(() => {
    const issues: string[] = [];
    if (!draft.name.trim()) issues.push('Session name is required.');
    if (draft.character_ids.length === 0) issues.push('Select at least one character.');
    return { ok: issues.length === 0, issues };
  }, [draft.name, draft.character_ids.length]);

  const toggleCharacter = (id: number) => {
    setDraft((d) => ({
      ...d,
      character_ids: d.character_ids.includes(id) ? d.character_ids.filter((x) => x !== id) : [...d.character_ids, id],
    }));
  };

  const save = async () => {
    setLoading(true);
    setError('');
    try {
      const sessionResponse = await api.post('/sessions', {
        name: draft.name.trim(),
        campaign_id: draft.campaign_id,
      });
      const sessionId = sessionResponse.data.id;

      await api.post(`/sessions/${sessionId}/characters`, {
        character_ids: draft.character_ids,
      });

      onClose();
      navigate(`/sessions/${sessionId}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  const footer = (
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs text-neutral-400">{validation.ok ? 'Ready to start.' : validation.issues[0]}</div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => (activeStep > 0 ? setActiveStep((s) => s - 1) : onClose())}
          className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium"
          disabled={loading}
        >
          {activeStep > 0 ? 'Back' : 'Cancel'}
        </button>

        {activeStep < steps.length - 1 ? (
          <button
            type="button"
            onClick={() => setActiveStep((s) => Math.min(steps.length - 1, s + 1))}
            className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium disabled:opacity-50"
            disabled={loading || (activeStep === 1 && draft.character_ids.length === 0) || (activeStep === 0 && !draft.name.trim())}
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={save}
            className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium disabled:opacity-50"
            disabled={loading || !validation.ok}
          >
            {loading ? 'Starting…' : 'Start Session'}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <Drawer
      open={open}
      title="New Session"
      description="Create a session and pick your party."
      onClose={onClose}
      footer={footer}
    >
      <div className="space-y-5">
        <Stepper steps={steps} activeIndex={activeStep} />

        {error && (
          <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl">{error}</div>
        )}

        {characters.length === 0 ? (
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
            <div className="text-sm font-semibold text-white mb-1">No characters yet</div>
            <div className="text-sm text-neutral-300">
              Create at least one character first, then come back to start a session.
            </div>
            <div className="mt-3">
              <button
                type="button"
                onClick={() => {
                  onClose();
                  navigate('/characters?drawer=new');
                }}
                className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium"
              >
                Create Character
              </button>
            </div>
          </div>
        ) : (
          <>
            {activeStep === 0 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Session Name</label>
                  <input
                    value={draft.name}
                    onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                    placeholder="e.g., Session 1 — The Tavern"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Campaign (Optional)</label>
                  <select
                    value={draft.campaign_id ?? ''}
                    onChange={(e) => setDraft((d) => ({ ...d, campaign_id: e.target.value || null }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                  >
                    <option value="">No Campaign</option>
                    {campaigns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {activeStep === 1 && (
              <div className="space-y-3">
                <div className="text-sm text-neutral-300">
                  Select the characters participating in this session.
                </div>
                <div className="border border-neutral-800 rounded-2xl bg-neutral-950 p-3 max-h-[420px] overflow-y-auto space-y-2">
                  {characters.map((c) => (
                    <label
                      key={c.id}
                      className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 cursor-pointer border border-transparent hover:border-white/10 transition-colors"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-white"
                        checked={draft.character_ids.includes(c.id)}
                        onChange={() => toggleCharacter(c.id)}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-white truncate">{c.name}</div>
                        <div className="text-xs text-neutral-400">Max HP: {c.max_hp}</div>
                      </div>
                    </label>
                  ))}
                </div>
                <div className="text-xs text-neutral-400">
                  Selected: {draft.character_ids.length}
                </div>
              </div>
            )}

            {activeStep === 2 && (
              <div className="space-y-4">
                {!validation.ok && (
                  <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl">
                    Please fix: {validation.issues.join(' ')}
                  </div>
                )}

                <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
                  <div className="text-sm font-semibold text-white mb-3">Summary</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-neutral-400">Name</div>
                      <div className="text-white">{draft.name || '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Campaign</div>
                      <div className="text-white">
                        {draft.campaign_id
                          ? campaigns.find((c) => c.id === draft.campaign_id)?.name || `#${draft.campaign_id}`
                          : 'No campaign'}
                      </div>
                    </div>
                    <div className="sm:col-span-2">
                      <div className="text-neutral-400">Party</div>
                      <div className="text-white">
                        {draft.character_ids.length === 0
                          ? '—'
                          : draft.character_ids
                              .map((id) => characters.find((c) => c.id === id)?.name || `#${id}`)
                              .join(', ')}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Drawer>
  );
}


