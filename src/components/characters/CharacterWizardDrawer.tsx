import { useEffect, useMemo, useState } from 'react';
import api from '../../services/api';
import type { Campaign, Character } from '../../types';
import Drawer from '../ui/Drawer';
import Stepper, { type StepperStep } from '../ui/Stepper';

type Mode = 'new' | 'edit';

type CharacterDraft = {
  // required
  name: string;
  max_hp: number;
  // optional links
  campaign_id: string | null;
  // optional combat + flavor
  race: string;
  class_name: string;
  level: number | null;
  ac: number | null;
  initiative_bonus: number | null;
  temp_hp: number | null;
  background: string;
  alignment: string;
  notes: string;
  // Stats (optional)
  strength_base: number | null;
  strength_bonus: number | null;
  dexterity_base: number | null;
  dexterity_bonus: number | null;
  wisdom_base: number | null;
  wisdom_bonus: number | null;
  intelligence_base: number | null;
  intelligence_bonus: number | null;
  constitution_base: number | null;
  constitution_bonus: number | null;
  charisma_base: number | null;
  charisma_bonus: number | null;
  // Flavour (optional)
  style: string;
  clothing: string;
  expression: string;
};

const steps: StepperStep[] = [
  { id: 'basics', title: 'Basics', description: 'Name, campaign, race' },
  { id: 'combat', title: 'Combat', description: 'HP, AC, initiative' },
  { id: 'flavor', title: 'Flavor', description: 'Artistic details' },
  { id: 'review', title: 'Review', description: 'Confirm & save' },
];

const defaultDraft = (preset?: Partial<CharacterDraft>): CharacterDraft => ({
  name: '',
  max_hp: 100,
  campaign_id: null,
  race: '',
  class_name: '',
  level: null,
  ac: null,
  initiative_bonus: null,
  temp_hp: null,
  background: '',
  alignment: '',
  notes: '',
  strength_base: null,
  strength_bonus: null,
  dexterity_base: null,
  dexterity_bonus: null,
  wisdom_base: null,
  wisdom_bonus: null,
  intelligence_base: null,
  intelligence_bonus: null,
  constitution_base: null,
  constitution_bonus: null,
  charisma_base: null,
  charisma_bonus: null,
  style: '',
  clothing: '',
  expression: '',
  ...preset,
});

export default function CharacterWizardDrawer({
  open,
  mode,
  characterId,
  presetCampaignId,
  onClose,
  onSaved,
}: {
  open: boolean;
  mode: Mode;
  characterId?: string | null;
  presetCampaignId?: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingCharacter, setLoadingCharacter] = useState(false);
  const [error, setError] = useState('');
  const [extraOptionsExpanded, setExtraOptionsExpanded] = useState(false);

  const [draft, setDraft] = useState<CharacterDraft>(() =>
    defaultDraft({ campaign_id: presetCampaignId ?? null })
  );

  const title = mode === 'edit' ? 'Edit Character' : 'Create Character';
  const description = mode === 'edit' ? 'Update details for this character.' : 'Create a character for your campaigns and sessions.';

  const canGoBack = activeStep > 0;

  const validation = useMemo(() => {
    const issues: string[] = [];
    if (!draft.name.trim()) issues.push('Character name is required.');
    if (!draft.max_hp || draft.max_hp < 1) issues.push('Max HP must be at least 1.');
    if (draft.level !== null && draft.level < 1) issues.push('Level must be at least 1.');
    if (draft.ac !== null && draft.ac < 1) issues.push('AC must be at least 1.');
    if (draft.temp_hp !== null && draft.temp_hp < 0) issues.push('Temp HP cannot be negative.');
    return {
      issues,
      ok: issues.length === 0,
    };
  }, [draft]);

  useEffect(() => {
    if (!open) return;
    setError('');
    setActiveStep(0);
    setExtraOptionsExpanded(false);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    api
      .get('/campaigns')
      .then((r) => setCampaigns(r.data))
      .catch(() => {
        // Non-fatal: we can still create characters without campaign selection
        setCampaigns([]);
      });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (mode !== 'edit') {
      setDraft(defaultDraft({ campaign_id: presetCampaignId ?? null }));
      return;
    }
    if (!characterId) return;

    setLoadingCharacter(true);
    setError('');
    api
      .get(`/characters/${characterId}`)
      .then((r) => {
        const c: Character & Partial<Record<string, any>> = r.data;
        setDraft(
          defaultDraft({
            name: c.name,
            max_hp: c.max_hp,
            campaign_id: c.campaign_id ?? null,
            race: (c as any).race ?? '',
            class_name: (c as any).class_name ?? '',
            level: (c as any).level ?? null,
            ac: (c as any).ac ?? null,
            initiative_bonus: (c as any).initiative_bonus ?? null,
            temp_hp: (c as any).temp_hp ?? null,
            background: (c as any).background ?? '',
            alignment: (c as any).alignment ?? '',
            notes: (c as any).notes ?? '',
            strength_base: (c as any).strength_base ?? null,
            strength_bonus: (c as any).strength_bonus ?? null,
            dexterity_base: (c as any).dexterity_base ?? null,
            dexterity_bonus: (c as any).dexterity_bonus ?? null,
            wisdom_base: (c as any).wisdom_base ?? null,
            wisdom_bonus: (c as any).wisdom_bonus ?? null,
            intelligence_base: (c as any).intelligence_base ?? null,
            intelligence_bonus: (c as any).intelligence_bonus ?? null,
            constitution_base: (c as any).constitution_base ?? null,
            constitution_bonus: (c as any).constitution_bonus ?? null,
            charisma_base: (c as any).charisma_base ?? null,
            charisma_bonus: (c as any).charisma_bonus ?? null,
            style: (c as any).style ?? '',
            clothing: (c as any).clothing ?? '',
            expression: (c as any).expression ?? '',
          })
        );
      })
      .catch((err: any) => {
        setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to load character');
      })
      .finally(() => setLoadingCharacter(false));
  }, [open, mode, characterId, presetCampaignId]);

  const save = async () => {
    setLoading(true);
    setError('');
    try {
      const payload = {
        name: draft.name.trim(),
        max_hp: draft.max_hp,
        campaign_id: draft.campaign_id,
        race: draft.race.trim() || null,
        class_name: draft.class_name.trim() || null,
        level: draft.level,
        ac: draft.ac,
        initiative_bonus: draft.initiative_bonus,
        temp_hp: draft.temp_hp,
        background: draft.background.trim() || null,
        alignment: draft.alignment.trim() || null,
        notes: draft.notes.trim() || null,
        strength_base: draft.strength_base,
        strength_bonus: draft.strength_bonus,
        dexterity_base: draft.dexterity_base,
        dexterity_bonus: draft.dexterity_bonus,
        wisdom_base: draft.wisdom_base,
        wisdom_bonus: draft.wisdom_bonus,
        intelligence_base: draft.intelligence_base,
        intelligence_bonus: draft.intelligence_bonus,
        constitution_base: draft.constitution_base,
        constitution_bonus: draft.constitution_bonus,
        charisma_base: draft.charisma_base,
        charisma_bonus: draft.charisma_bonus,
        style: draft.style.trim() || null,
        clothing: draft.clothing.trim() || null,
        expression: draft.expression.trim() || null,
      };

      if (mode === 'edit' && characterId) {
        await api.put(`/characters/${characterId}`, payload);
      } else {
        await api.post('/characters', payload);
      }
      onSaved();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to save character');
    } finally {
      setLoading(false);
    }
  };

  const footer = (
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs text-neutral-400">
        {validation.ok ? 'Ready to save.' : validation.issues[0]}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => (canGoBack ? setActiveStep((s) => s - 1) : onClose())}
          className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium"
          disabled={loading}
        >
          {canGoBack ? 'Back' : 'Cancel'}
        </button>

        {activeStep < steps.length - 1 ? (
          <button
            type="button"
            onClick={() => setActiveStep((s) => Math.min(steps.length - 1, s + 1))}
            className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium disabled:opacity-50"
            disabled={loading || !validation.ok}
            title={!validation.ok ? 'Fix required fields to continue' : undefined}
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={save}
            className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium disabled:opacity-50"
            disabled={loading || loadingCharacter || !validation.ok}
          >
            {loading ? 'Saving…' : mode === 'edit' ? 'Save Changes' : 'Create Character'}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <Drawer open={open} title={title} description={description} onClose={onClose} footer={footer}>
      <div className="space-y-5">
        <Stepper steps={steps} activeIndex={activeStep} />

        {error && (
          <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl">
            {error}
          </div>
        )}

        {loadingCharacter ? (
          <div className="text-sm text-neutral-300">Loading character…</div>
        ) : (
          <>
            {activeStep === 0 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Character Name *</label>
                  <input
                    value={draft.name}
                    onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                    placeholder="e.g., Kethra Stormshield"
                    autoFocus
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Campaign (Optional)</label>
                  <select
                    value={draft.campaign_id ?? ''}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, campaign_id: e.target.value || null }))
                    }
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

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Race (Optional)</label>
                  <input
                    value={draft.race}
                    onChange={(e) => setDraft((d) => ({ ...d, race: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                    placeholder="e.g., Half-Elf"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Class (Optional)</label>
                  <input
                    value={draft.class_name}
                    onChange={(e) => setDraft((d) => ({ ...d, class_name: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                    placeholder="e.g., Paladin"
                  />
                </div>
              </div>
            )}

            {activeStep === 1 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-2">Max HP *</label>
                    <input
                      type="number"
                      min={1}
                      value={draft.max_hp}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, max_hp: parseInt(e.target.value, 10) || 0 }))
                      }
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-2">Temp HP (Optional)</label>
                    <input
                      type="number"
                      min={0}
                      value={draft.temp_hp ?? ''}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          temp_hp: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                        }))
                      }
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                      placeholder="0"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-2">AC (Optional)</label>
                    <input
                      type="number"
                      min={1}
                      value={draft.ac ?? ''}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          ac: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                        }))
                      }
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                      placeholder="e.g., 16"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-2">Initiative (Optional)</label>
                    <input
                      type="number"
                      value={draft.initiative_bonus ?? ''}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          initiative_bonus: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                        }))
                      }
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                      placeholder="e.g., +3"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-2">Level (Optional)</label>
                    <input
                      type="number"
                      min={1}
                      value={draft.level ?? ''}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          level: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                        }))
                      }
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                      placeholder="e.g., 3"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-3">Ability Scores (Optional)</label>
                  <div className="space-y-3">
                    {/* Strength */}
                    <div className="grid grid-cols-3 gap-3 items-end">
                      <div className="text-sm text-neutral-400">Strength</div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Base</label>
                        <input
                          type="number"
                          value={draft.strength_base ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              strength_base: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Bonus</label>
                        <input
                          type="number"
                          value={draft.strength_bonus ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              strength_bonus: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                    </div>
                    {/* Dexterity */}
                    <div className="grid grid-cols-3 gap-3 items-end">
                      <div className="text-sm text-neutral-400">Dexterity</div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Base</label>
                        <input
                          type="number"
                          value={draft.dexterity_base ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              dexterity_base: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Bonus</label>
                        <input
                          type="number"
                          value={draft.dexterity_bonus ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              dexterity_bonus: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                    </div>
                    {/* Wisdom */}
                    <div className="grid grid-cols-3 gap-3 items-end">
                      <div className="text-sm text-neutral-400">Wisdom</div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Base</label>
                        <input
                          type="number"
                          value={draft.wisdom_base ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              wisdom_base: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Bonus</label>
                        <input
                          type="number"
                          value={draft.wisdom_bonus ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              wisdom_bonus: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                    </div>
                    {/* Intelligence */}
                    <div className="grid grid-cols-3 gap-3 items-end">
                      <div className="text-sm text-neutral-400">Intelligence</div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Base</label>
                        <input
                          type="number"
                          value={draft.intelligence_base ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              intelligence_base: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Bonus</label>
                        <input
                          type="number"
                          value={draft.intelligence_bonus ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              intelligence_bonus: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                    </div>
                    {/* Constitution */}
                    <div className="grid grid-cols-3 gap-3 items-end">
                      <div className="text-sm text-neutral-400">Constitution</div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Base</label>
                        <input
                          type="number"
                          value={draft.constitution_base ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              constitution_base: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Bonus</label>
                        <input
                          type="number"
                          value={draft.constitution_bonus ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              constitution_bonus: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                    </div>
                    {/* Charisma */}
                    <div className="grid grid-cols-3 gap-3 items-end">
                      <div className="text-sm text-neutral-400">Charisma</div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Base</label>
                        <input
                          type="number"
                          value={draft.charisma_base ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              charisma_base: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-neutral-500 mb-1">Bonus</label>
                        <input
                          type="number"
                          value={draft.charisma_bonus ?? ''}
                          onChange={(e) =>
                            setDraft((d) => ({
                              ...d,
                              charisma_bonus: e.target.value === '' ? null : parseInt(e.target.value, 10) || 0,
                            }))
                          }
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
                          placeholder="—"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeStep === 2 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-2">Background (Optional)</label>
                    <input
                      value={draft.background}
                      onChange={(e) => setDraft((d) => ({ ...d, background: e.target.value }))}
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                      placeholder="e.g., Soldier"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-white/80 mb-2">Alignment (Optional)</label>
                    <input
                      value={draft.alignment}
                      onChange={(e) => setDraft((d) => ({ ...d, alignment: e.target.value }))}
                      className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                      placeholder="e.g., Chaotic Good"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-white/80 mb-2">Notes (Optional)</label>
                  <textarea
                    rows={5}
                    value={draft.notes}
                    onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
                    className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                    placeholder="Personality, bonds, features, custom rules, etc."
                  />
                </div>

                <div className="border border-neutral-800 rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setExtraOptionsExpanded(!extraOptionsExpanded)}
                    className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
                  >
                    <span className="text-sm font-medium text-white/80">Extra Options</span>
                    <svg
                      className={`w-4 h-4 text-neutral-400 transition-transform ${extraOptionsExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {extraOptionsExpanded && (
                    <div className="px-4 pb-4 space-y-4 border-t border-neutral-800">
                      <div>
                        <label className="block text-sm font-medium text-white/80 mb-2">Style (Optional)</label>
                        <input
                          value={draft.style}
                          onChange={(e) => setDraft((d) => ({ ...d, style: e.target.value }))}
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                          placeholder="e.g., Elegant, Rough, Mystical"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-white/80 mb-2">Clothing (Optional)</label>
                        <input
                          value={draft.clothing}
                          onChange={(e) => setDraft((d) => ({ ...d, clothing: e.target.value }))}
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                          placeholder="e.g., Robes, Armor, Traveler's clothes"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-white/80 mb-2">Expression (Optional)</label>
                        <input
                          value={draft.expression}
                          onChange={(e) => setDraft((d) => ({ ...d, expression: e.target.value }))}
                          className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
                          placeholder="e.g., Stern, Friendly, Mysterious"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeStep === 3 && (
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
                    <div>
                      <div className="text-neutral-400">Max HP</div>
                      <div className="text-white">{draft.max_hp}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Temp HP</div>
                      <div className="text-white">{draft.temp_hp ?? '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">AC</div>
                      <div className="text-white">{draft.ac ?? '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Initiative</div>
                      <div className="text-white">
                        {draft.initiative_bonus === null ? '—' : draft.initiative_bonus >= 0 ? `+${draft.initiative_bonus}` : draft.initiative_bonus}
                      </div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Class</div>
                      <div className="text-white">{draft.class_name || '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Level</div>
                      <div className="text-white">{draft.level ?? '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Race</div>
                      <div className="text-white">{draft.race || '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Background</div>
                      <div className="text-white">{draft.background || '—'}</div>
                    </div>
                    <div>
                      <div className="text-neutral-400">Alignment</div>
                      <div className="text-white">{draft.alignment || '—'}</div>
                    </div>
                  </div>

                  {draft.notes.trim() && (
                    <div className="mt-4">
                      <div className="text-neutral-400 text-sm">Notes</div>
                      <div className="text-white text-sm whitespace-pre-wrap mt-1">{draft.notes}</div>
                    </div>
                  )}

                  {(() => {
                    const hasAnyStats =
                      draft.strength_base !== null ||
                      draft.strength_bonus !== null ||
                      draft.dexterity_base !== null ||
                      draft.dexterity_bonus !== null ||
                      draft.wisdom_base !== null ||
                      draft.wisdom_bonus !== null ||
                      draft.intelligence_base !== null ||
                      draft.intelligence_bonus !== null ||
                      draft.constitution_base !== null ||
                      draft.constitution_bonus !== null ||
                      draft.charisma_base !== null ||
                      draft.charisma_bonus !== null;

                    if (!hasAnyStats) return null;

                    return (
                      <div className="mt-4 border-t border-neutral-800 pt-4">
                        <div className="text-neutral-400 text-sm font-semibold mb-3">Ability Scores</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                          {[
                            { name: 'Strength', base: draft.strength_base, bonus: draft.strength_bonus },
                            { name: 'Dexterity', base: draft.dexterity_base, bonus: draft.dexterity_bonus },
                            { name: 'Wisdom', base: draft.wisdom_base, bonus: draft.wisdom_bonus },
                            { name: 'Intelligence', base: draft.intelligence_base, bonus: draft.intelligence_bonus },
                            { name: 'Constitution', base: draft.constitution_base, bonus: draft.constitution_bonus },
                            { name: 'Charisma', base: draft.charisma_base, bonus: draft.charisma_bonus },
                          ].map(
                            (stat) =>
                              (stat.base !== null || stat.bonus !== null) && (
                                <div key={stat.name}>
                                  <div className="text-neutral-400">{stat.name}</div>
                                  <div className="text-white">
                                    {stat.base !== null && stat.bonus !== null
                                      ? `${stat.base}${stat.bonus >= 0 ? '+' : ''}${stat.bonus}`
                                      : stat.base !== null
                                        ? `${stat.base}`
                                        : stat.bonus !== null
                                          ? `${stat.bonus >= 0 ? '+' : ''}${stat.bonus}`
                                          : '—'}
                                  </div>
                                </div>
                              )
                          )}
                        </div>
                      </div>
                    );
                  })()}

                  {(() => {
                    const hasAnyExtraOptions = draft.style.trim() || draft.clothing.trim() || draft.expression.trim();

                    if (!hasAnyExtraOptions) return null;

                    return (
                      <div className="mt-4 border-t border-neutral-800 pt-4">
                        <div className="text-neutral-400 text-sm font-semibold mb-3">Extra Options</div>
                        <div className="space-y-2 text-sm">
                          {draft.style.trim() && (
                            <div>
                              <div className="text-neutral-400">Style</div>
                              <div className="text-white">{draft.style}</div>
                            </div>
                          )}
                          {draft.clothing.trim() && (
                            <div>
                              <div className="text-neutral-400">Clothing</div>
                              <div className="text-white">{draft.clothing}</div>
                            </div>
                          )}
                          {draft.expression.trim() && (
                            <div>
                              <div className="text-neutral-400">Expression</div>
                              <div className="text-white">{draft.expression}</div>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Drawer>
  );
}


