import { useEffect, useMemo, useState } from 'react';
import api from '../../services/api';
import type { Campaign } from '../../types';
import Drawer from '../ui/Drawer';
import Stepper, { type StepperStep } from '../ui/Stepper';

type Mode = 'new' | 'edit';

type CampaignDraft = {
  name: string;
  description: string;
};

const steps: StepperStep[] = [
  { id: 'basics', title: 'Basics', description: 'Name & description' },
  { id: 'review', title: 'Review', description: 'Confirm & save' },
];

export default function CampaignWizardDrawer({
  open,
  mode,
  campaignId,
  onClose,
  onSaved,
}: {
  open: boolean;
  mode: Mode;
  campaignId?: number | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingCampaign, setLoadingCampaign] = useState(false);
  const [error, setError] = useState('');

  const [draft, setDraft] = useState<CampaignDraft>({ name: '', description: '' });

  const validation = useMemo(() => {
    const issues: string[] = [];
    if (!draft.name.trim()) issues.push('Campaign name is required.');
    return { ok: issues.length === 0, issues };
  }, [draft.name]);

  useEffect(() => {
    if (!open) return;
    setError('');
    setActiveStep(0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (mode !== 'edit') {
      setDraft({ name: '', description: '' });
      return;
    }
    if (!campaignId) return;

    setLoadingCampaign(true);
    setError('');
    api
      .get(`/campaigns/${campaignId}`)
      .then((r) => {
        console.log(`[Campaigns API] GET /campaigns/${campaignId} - Response:`, r.data);
        const c: Campaign = r.data;
        setDraft({ name: c.name, description: c.description || '' });
      })
      .catch((err: any) => {
        setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to load campaign');
      })
      .finally(() => setLoadingCampaign(false));
  }, [open, mode, campaignId]);

  const save = async () => {
    setLoading(true);
    setError('');
    try {
      const payload = {
        name: draft.name.trim(),
        description: draft.description.trim() || null,
      };
      if (mode === 'edit' && campaignId) {
        const response = await api.put(`/campaigns/${campaignId}`, payload);
        console.log(`[Campaigns API] PUT /campaigns/${campaignId} - Response:`, response.data);
      } else {
        const response = await api.post('/campaigns', payload);
        console.log('[Campaigns API] POST /campaigns - Response:', response.data);
      }
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to save campaign');
    } finally {
      setLoading(false);
    }
  };

  const footer = (
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs text-neutral-400">{validation.ok ? 'Ready to save.' : validation.issues[0]}</div>
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
            disabled={loading || !validation.ok}
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={save}
            className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium disabled:opacity-50"
            disabled={loading || loadingCampaign || !validation.ok}
          >
            {loading ? 'Saving…' : mode === 'edit' ? 'Save Changes' : 'Create Campaign'}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <Drawer
      open={open}
      title={mode === 'edit' ? 'Edit Campaign' : 'Create Campaign'}
      description={mode === 'edit' ? 'Update campaign basics.' : 'Create a new campaign world.'}
      onClose={onClose}
      footer={footer}
    >
      <div className="space-y-5">
        <Stepper steps={steps} activeIndex={activeStep} />

        {error && (
          <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl">{error}</div>
        )}

        {loadingCampaign ? (
          <div className="text-sm text-neutral-300">Loading campaign…</div>
        ) : (
          <>
            {activeStep === 0 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Campaign Name</label>
                  <input
                    value={draft.name}
                    onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                    placeholder="e.g., Shattered Isles"
                    autoFocus
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Description (Optional)</label>
                  <textarea
                    rows={5}
                    value={draft.description}
                    onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                    placeholder="Setting notes, campaign pitch, key themes…"
                  />
                </div>
              </div>
            )}

            {activeStep === 1 && (
              <div className="space-y-4">
                {!validation.ok && (
                  <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl">
                    Please fix: {validation.issues.join(' ')}
                  </div>
                )}

                <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4">
                  <div className="text-sm font-semibold text-white mb-3">Summary</div>
                  <div className="space-y-3 text-sm">
                    <div>
                      <div className="text-neutral-400">Name</div>
                      <div className="text-white">{draft.name || '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Description</div>
                      <div className="text-white whitespace-pre-wrap">{draft.description || '—'}</div>
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


