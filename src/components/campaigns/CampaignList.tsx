import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import api from '../../services/api';
import type { Campaign } from '../../types';
import CampaignWizardDrawer from './CampaignWizardDrawer';

export default function CampaignList() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generatingArt, setGeneratingArt] = useState<Set<string>>(new Set());
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const drawerMode = searchParams.get('drawer'); // 'new' | 'edit' | null
  const drawerOpen = drawerMode === 'new' || drawerMode === 'edit';
  const editId = useMemo(() => {
    if (drawerMode !== 'edit') return null;
    const raw = searchParams.get('id');
    return raw || null;
  }, [drawerMode, searchParams]);

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      setLoading(true);
      const response = await api.get('/campaigns');
      console.log('[Campaigns API] GET /campaigns - Response:', response.data);
      setCampaigns(response.data);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent banner click
    if (!confirm('Are you sure you want to delete this campaign? This will not delete associated characters or sessions, but they will no longer be linked to a campaign.')) {
      return;
    }

    try {
      const response = await api.delete(`/campaigns/${id}`);
      console.log(`[Campaigns API] DELETE /campaigns/${id} - Response:`, response.data);
      setCampaigns(campaigns.filter((c) => c.id !== id));
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete campaign');
    }
  };

  const handleEdit = (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent banner click
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('drawer', 'edit');
      next.set('id', String(id));
      return next;
    });
  };

  const handleGenerateArt = async (campaignId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent banner click
    if (generatingArt.has(campaignId)) return;
    
    try {
      setGeneratingArt((prev) => new Set(prev).add(campaignId));
      const response = await api.post(`/campaigns/${campaignId}/generate-art`);
      // Update the campaign in the list
      setCampaigns(campaigns.map((c) => 
        c.id === campaignId ? response.data : c
      ));
    } catch (err: any) {
      alert(err.response?.data?.error || err.response?.data?.detail || 'Failed to generate campaign art');
    } finally {
      setGeneratingArt((prev) => {
        const next = new Set(prev);
        next.delete(campaignId);
        return next;
      });
    }
  };

  // Get campaign image URL - use display_art_url if available, otherwise placeholder/gradient
  const getCampaignImageUrl = (campaign: Campaign, index: number): string => {
    if (campaign.display_art_url) {
      // If the URL starts with /api, prepend the API base URL
      if (campaign.display_art_url.startsWith('/api/')) {
        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';
        return `${API_URL}${campaign.display_art_url}`;
      }
      return campaign.display_art_url;
    }
    // Generate gradient placeholder based on index
    const gradients = [
      'linear-gradient(145deg,#4F46E5,#000)',
      'linear-gradient(210deg,#10B981,#000)',
      'linear-gradient(165deg,#F59E0B,#000)',
      'linear-gradient(195deg,#EF4444,#000)',
      'linear-gradient(225deg,#8B5CF6,#000)',
      'linear-gradient(135deg,#06B6D4,#000)',
      'linear-gradient(180deg,#EC4899,#000)',
      'linear-gradient(120deg,#14B8A6,#000)',
    ];
    // Return a data URL for gradient (we'll use CSS gradient instead)
    return '';
  };

  const getGradientForIndex = (index: number): string => {
    const gradients = [
      'linear-gradient(145deg,#4F46E5,#000)',
      'linear-gradient(210deg,#10B981,#000)',
      'linear-gradient(165deg,#F59E0B,#000)',
      'linear-gradient(195deg,#EF4444,#000)',
      'linear-gradient(225deg,#8B5CF6,#000)',
      'linear-gradient(135deg,#06B6D4,#000)',
      'linear-gradient(180deg,#EC4899,#000)',
      'linear-gradient(120deg,#14B8A6,#000)',
    ];
    return gradients[index % gradients.length];
  };

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="text-neutral-300">Loading campaigns...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-end items-center mb-6">
        <Link
          to="/campaigns?drawer=new"
          className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium"
        >
          Create Campaign
        </Link>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl mb-4">
          {error}
        </div>
      )}

      {campaigns.length === 0 ? (
        <div className="text-center py-12 bg-neutral-900/60 border border-neutral-800 rounded-2xl">
          <p className="text-neutral-300 text-lg mb-4">No campaigns yet</p>
          <Link
            to="/campaigns?drawer=new"
            className="text-white/90 hover:text-white font-medium"
          >
            Create your first campaign
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {campaigns.map((campaign, index) => {
            const hasImage = !!campaign.display_art_url;
            const isGenerating = generatingArt.has(campaign.id);
            const imageUrl = getCampaignImageUrl(campaign, index);
            const gradient = getGradientForIndex(index);
            
            return (
              <div
                key={campaign.id}
                onClick={() => navigate(`/campaigns/${campaign.id}`)}
                className="group relative w-full rounded-xl overflow-hidden border border-neutral-800 hover:border-neutral-700 transition-all cursor-pointer bg-neutral-900/60"
                style={{ aspectRatio: '21/9' }}
              >
                {/* Background Image or Gradient */}
                {hasImage && imageUrl ? (
                  <div className="absolute inset-0">
                    <img
                      src={imageUrl}
                      alt={campaign.name}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        // Fallback if image fails to load
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                      }}
                    />
                    <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/50 to-transparent" />
                  </div>
                ) : (
                  <div 
                    className="absolute inset-0"
                    style={{ background: gradient }}
                  />
                )}
                
                {/* Content Overlay */}
                <div className="relative z-10 h-full flex items-center justify-between p-6 md:p-8">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-2xl md:text-3xl font-bold text-white mb-2 truncate">
                      {campaign.name}
                    </h3>
                    {campaign.description && (
                      <p className="text-neutral-200 text-sm md:text-base line-clamp-2">
                        {campaign.description}
                      </p>
                    )}
                  </div>
                  
                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 ml-4">
                    {!hasImage && (
                      <button
                        onClick={(e) => handleGenerateArt(campaign.id, e)}
                        disabled={isGenerating}
                        className="px-4 py-2 bg-white/20 backdrop-blur-sm text-white rounded-lg hover:bg-white/30 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isGenerating ? 'Generating...' : 'Generate Art'}
                      </button>
                    )}
                    <button
                      onClick={(e) => handleEdit(campaign.id, e)}
                      className="px-4 py-2 bg-white/20 backdrop-blur-sm text-white rounded-lg hover:bg-white/30 text-sm font-medium transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={(e) => handleDelete(campaign.id, e)}
                      className="px-4 py-2 bg-red-500/80 backdrop-blur-sm text-white rounded-lg hover:bg-red-500 text-sm font-medium transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <CampaignWizardDrawer
        open={drawerOpen}
        mode={drawerMode === 'edit' ? 'edit' : 'new'}
        campaignId={editId}
        onClose={() => {
          setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.delete('drawer');
            next.delete('id');
            return next;
          });
        }}
        onSaved={() => {
          fetchCampaigns();
        }}
      />
    </div>
  );
}

