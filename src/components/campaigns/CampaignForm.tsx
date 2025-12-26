import { useState, useEffect } from 'react';
import type React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../services/api';
import type { Campaign } from '../../types';

export default function CampaignForm() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isEdit) {
      fetchCampaign();
    }
  }, [id]);

  const fetchCampaign = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/campaigns/${id}`);
      const campaign: Campaign = response.data;
      setName(campaign.name);
      setDescription(campaign.description || '');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load campaign');
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
        await api.put(`/campaigns/${id}`, {
          name,
          description: description || null,
        });
      } else {
        await api.post('/campaigns', {
          name,
          description: description || null,
        });
      }
      navigate('/campaigns');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save campaign');
    } finally {
      setLoading(false);
    }
  };

  if (loading && isEdit) {
    return (
      <div className="text-center py-8">
        <div className="text-neutral-300">Loading campaign...</div>
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
            Campaign Name
          </label>
          <input
            id="name"
            type="text"
            required
            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
            placeholder="Enter campaign name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div className="mb-6">
          <label htmlFor="description" className="block text-sm font-medium text-white/80 mb-2">
            Description (Optional)
          </label>
          <textarea
            id="description"
            rows={4}
            className="w-full px-3 py-2 bg-neutral-950 border border-neutral-800 text-white rounded-xl focus:outline-none focus:ring-1 focus:ring-white/10 focus:border-white/20 placeholder:text-neutral-500"
            placeholder="Enter campaign description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 disabled:opacity-50 transition-colors text-sm font-medium"
          >
            {loading ? 'Saving...' : isEdit ? 'Update Campaign' : 'Create Campaign'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/campaigns')}
            className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

