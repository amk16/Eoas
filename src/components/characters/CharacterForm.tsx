import { useState, useEffect } from 'react';
import type React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../services/api';
import type { Character, Campaign } from '../../types';

export default function CharacterForm() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [maxHp, setMaxHp] = useState<number>(100);
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchCampaigns();
    if (isEdit) {
      fetchCharacter();
    }
  }, [id]);

  const fetchCampaigns = async () => {
    try {
      const response = await api.get('/campaigns');
      console.log('[Campaigns API] GET /campaigns - Response:', response.data);
      setCampaigns(response.data);
    } catch (err: any) {
      console.error('Failed to load campaigns:', err);
    }
  };

  const fetchCharacter = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/characters/${id}`);
      const character: Character = response.data;
      setName(character.name);
      setMaxHp(character.max_hp);
      setCampaignId(character.campaign_id);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load character');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isEdit) {
        await api.put(`/characters/${id}`, {
          name,
          max_hp: maxHp,
          campaign_id: campaignId || null,
        });
      } else {
        await api.post('/characters', {
          name,
          max_hp: maxHp,
          campaign_id: campaignId || null,
        });
      }
      navigate('/characters');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save character');
    } finally {
      setLoading(false);
    }
  };

  if (loading && isEdit) {
    return (
      <div className="text-center py-8">
        <div className="text-neutral-300">Loading character...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <form onSubmit={handleSubmit} className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
        {error && (
          <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl mb-4">
            {error}
          </div>
        )}

        <div className="mb-4">
          <label htmlFor="name" className="block text-sm font-medium text-white/80 mb-2">
            Character Name
          </label>
          <input
            id="name"
            type="text"
            required
            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
            placeholder="Enter character name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="mb-4">
          <label htmlFor="maxHp" className="block text-sm font-medium text-white/80 mb-2">
            Max HP
          </label>
          <input
            id="maxHp"
            type="number"
            required
            min="1"
            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
            value={maxHp}
            onChange={(e) => setMaxHp(parseInt(e.target.value) || 0)}
          />
        </div>

        <div className="mb-6">
          <label htmlFor="campaign" className="block text-sm font-medium text-white/80 mb-2">
            Campaign (Optional)
          </label>
          <select
            id="campaign"
            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20"
            value={campaignId || ''}
            onChange={(e) => setCampaignId(e.target.value || null)}
          >
            <option value="">No Campaign</option>
            {campaigns.map((campaign) => (
              <option key={campaign.id} value={campaign.id}>
                {campaign.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 disabled:opacity-50 transition-colors text-sm font-medium"
          >
            {loading ? 'Saving...' : isEdit ? 'Update Character' : 'Create Character'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/characters')}
            className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

