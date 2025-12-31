import { useState, useEffect } from 'react';
import type React from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import type { Character, Campaign } from '../../types';

export default function SessionSetup() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchCampaigns();
    fetchCharacters();
  }, []);

  const fetchCampaigns = async () => {
    try {
      const response = await api.get('/campaigns');
      console.log('[Campaigns API] GET /campaigns - Response:', response.data);
      setCampaigns(response.data);
    } catch (err: any) {
      console.error('Failed to load campaigns:', err);
    }
  };

  const fetchCharacters = async () => {
    try {
      const response = await api.get('/characters');
      setCharacters(response.data);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load characters');
    }
  };

  const handleToggleCharacter = (characterId: string) => {
    setSelectedCharacterIds((prev) =>
      prev.includes(characterId)
        ? prev.filter((id) => id !== characterId)
        : [...prev, characterId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('Session name is required');
      return;
    }

    if (selectedCharacterIds.length === 0) {
      setError('Please select at least one character');
      return;
    }

    setLoading(true);

    try {
      // Create session
      const sessionResponse = await api.post('/sessions', { 
        name,
        campaign_id: campaignId || null,
      });
      const sessionId = sessionResponse.data.id;

      // Add characters to session
      await api.post(`/sessions/${sessionId}/characters`, {
        character_ids: selectedCharacterIds,
      });

      navigate(`/sessions/${sessionId}`);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  if (characters.length === 0) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
          <div className="text-center py-8">
            <p className="text-neutral-300 mb-4">You need to create characters first</p>
            <button
              onClick={() => navigate('/characters?drawer=new')}
              className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium"
            >
              Create Character
            </button>
          </div>
        </div>
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
            Session Name
          </label>
          <input
            id="name"
            type="text"
            required
            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
            placeholder="e.g., Campaign Session 1"
            value={name}
            onChange={(e) => setName(e.target.value)}
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

        <div className="mb-6">
          <label className="block text-sm font-medium text-white/80 mb-3">
            Select Characters
          </label>
          <div className="space-y-2 max-h-64 overflow-y-auto border border-neutral-800 rounded-xl p-4 bg-neutral-950">
            {characters.map((character) => (
              <label
                key={character.id}
                className="flex items-center p-3 hover:bg-white/5 rounded-lg cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedCharacterIds.includes(character.id)}
                  onChange={() => handleToggleCharacter(character.id)}
                  className="h-4 w-4 accent-white rounded"
                />
                <div className="ml-3 flex-1">
                  <div className="text-sm font-medium text-white">
                    {character.name}
                  </div>
                  <div className="text-sm text-neutral-400">
                    Max HP: {character.max_hp}
                  </div>
                </div>
              </label>
            ))}
          </div>
          {selectedCharacterIds.length > 0 && (
            <p className="mt-2 text-sm text-neutral-300">
              {selectedCharacterIds.length} character(s) selected
            </p>
          )}
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 disabled:opacity-50 transition-colors text-sm font-medium"
          >
            {loading ? 'Creating...' : 'Create Session'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/sessions')}
            className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

