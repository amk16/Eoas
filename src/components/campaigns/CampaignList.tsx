import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import api from '../../services/api';
import type { Campaign } from '../../types';
import ChromaGrid, { type ChromaItem } from '../ChromaGrid';
import CampaignWizardDrawer from './CampaignWizardDrawer';

export default function CampaignList() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const drawerMode = searchParams.get('drawer'); // 'new' | 'edit' | null
  const drawerOpen = drawerMode === 'new' || drawerMode === 'edit';
  const editId = useMemo(() => {
    if (drawerMode !== 'edit') return null;
    const raw = searchParams.get('id');
    const n = raw ? parseInt(raw, 10) : NaN;
    return Number.isFinite(n) ? n : null;
  }, [drawerMode, searchParams]);

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      setLoading(true);
      const response = await api.get('/campaigns');
      setCampaigns(response.data);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click
    if (!confirm('Are you sure you want to delete this campaign? This will not delete associated characters or sessions, but they will no longer be linked to a campaign.')) {
      return;
    }

    try {
      await api.delete(`/campaigns/${id}`);
      setCampaigns(campaigns.filter((c) => c.id !== id));
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete campaign');
    }
  };

  const handleEdit = (id: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('drawer', 'edit');
      next.set('id', String(id));
      return next;
    });
  };

  // Generate gradient colors based on campaign index
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

  const borderColors = [
    '#4F46E5',
    '#10B981',
    '#F59E0B',
    '#EF4444',
    '#8B5CF6',
    '#06B6D4',
    '#EC4899',
    '#14B8A6',
  ];

  // Generate avatar image URL based on campaign name
  const getCampaignAvatar = (name: string, borderColor: string) => {
    const color = borderColor.replace('#', '');
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&size=300&background=${color}&color=fff&bold=true&font-size=0.5`;
  };

  const chromaItems: ChromaItem[] = campaigns.map((campaign, index) => {
    const borderColor = borderColors[index % borderColors.length];
    return {
      title: campaign.name,
      subtitle: campaign.description || 'No description',
      image: getCampaignAvatar(campaign.name, borderColor),
      gradient: gradients[index % gradients.length],
      borderColor: borderColor,
      onClick: () => navigate(`/campaigns/${campaign.id}`),
      customFooter: (
        <div>
          <div className="mb-3">
            <h3 className="m-0 text-[1.05rem] font-semibold mb-1">{campaign.name}</h3>
            <p className="m-0 text-[0.85rem] opacity-85">{campaign.description || 'No description'}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={(e) => handleEdit(campaign.id, e)}
              className="flex-1 px-3 py-2 bg-white/20 backdrop-blur-sm text-white rounded-md hover:bg-white/30 text-sm font-medium transition-colors"
            >
              Edit
            </button>
            <button
              onClick={(e) => handleDelete(campaign.id, e)}
              className="flex-1 px-3 py-2 bg-red-500/80 backdrop-blur-sm text-white rounded-md hover:bg-red-500 text-sm font-medium transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      ),
    };
  });

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
        <div className="min-h-[400px] py-4">
          <ChromaGrid items={chromaItems} className="min-h-[400px]" />
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

