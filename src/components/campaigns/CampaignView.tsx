import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import api from '../../services/api';
import type { Campaign, Character, Session } from '../../types';
import CharacterDetailSidebar from '../characters/CharacterDetailSidebar';

export default function CampaignView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedCharacterId, setSelectedCharacterId] = useState<number | null>(null);

  const selectedCharacter = useMemo(() => {
    if (!selectedCharacterId) return null;
    return characters.find((c) => c.id === selectedCharacterId) || null;
  }, [selectedCharacterId, characters]);

  useEffect(() => {
    if (id) {
      fetchCampaign();
    }
  }, [id]);

  const fetchCampaign = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/campaigns/${id}`);
      const data = response.data;
      setCampaign({
        id: data.id,
        user_id: data.user_id,
        name: data.name,
        description: data.description,
        created_at: data.created_at,
        updated_at: data.updated_at,
      });
      setCharacters(data.characters || []);
      setSessions(data.sessions || []);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load campaign');
    } finally {
      setLoading(false);
    }
  };

  const handleCharacterCardClick = (characterId: number) => {
    setSelectedCharacterId(characterId);
  };

  const handleSidebarClose = () => {
    setSelectedCharacterId(null);
  };

  const handleSidebarEdit = (characterId: number) => {
    setSelectedCharacterId(null);
    navigate(`/characters?drawer=edit&id=${characterId}`);
  };

  const handleSidebarDelete = async (characterId: number) => {
    try {
      await api.delete(`/characters/${characterId}`);
      setCharacters(characters.filter((c) => c.id !== characterId));
      setSelectedCharacterId(null);
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to delete character');
    }
  };

  const handleSidebarUpdate = (updatedCharacter: Character) => {
    // Update the character in the list and refresh campaign data
    setCharacters(characters.map((c) => 
      c.id === updatedCharacter.id ? updatedCharacter : c
    ));
  };

  // Get character image URL - use display_art_url if available, otherwise placeholder
  const getCharacterImageUrl = (character: Character): string => {
    if (character.display_art_url) {
      // If the URL starts with /api, prepend the API base URL
      if (character.display_art_url.startsWith('/api/')) {
        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';
        return `${API_URL}${character.display_art_url}`;
      }
      return character.display_art_url;
    }
    // Placeholder image with character name
    return `https://via.placeholder.com/512x512/000000/FFFFFF?text=${encodeURIComponent(character.name || 'Character')}`;
  };

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="text-neutral-300">Loading campaign...</div>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl mb-4">
          {error || 'Campaign not found'}
        </div>
        <button
          onClick={() => navigate('/campaigns')}
          className="px-4 py-2 bg-white/5 text-white border border-white/10 rounded-xl hover:bg-white/10 transition-colors text-sm font-medium"
        >
          Back to Campaigns
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/campaigns')}
          className="text-white/70 hover:text-white mb-4 transition-colors text-sm"
        >
          ← Back to Campaigns
        </button>
        <h1 className="text-3xl font-bold text-white mb-2">{campaign.name}</h1>
        {campaign.description && (
          <p className="text-neutral-300">{campaign.description}</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-white">Characters</h2>
            <Link
              to={`/characters?drawer=new&campaignId=${campaign.id}`}
              className="text-sm px-3 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors font-medium"
            >
              Add Character
            </Link>
          </div>
          {characters.length === 0 ? (
            <p className="text-neutral-300">No characters in this campaign yet.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {characters.map((character) => (
                <div
                  key={character.id}
                  onClick={() => handleCharacterCardClick(character.id)}
                  className="bg-black border border-neutral-800 cursor-pointer hover:border-neutral-700 transition-colors overflow-hidden"
                >
                  {/* Character Art Image */}
                  <div className="aspect-square bg-neutral-950 relative">
                    <img
                      src={getCharacterImageUrl(character)}
                      alt={character.name}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        // Fallback if image fails to load
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                      }}
                    />
                  </div>
                  
                  {/* Character Info */}
                  <div className="p-3">
                    <h3 className="text-white font-semibold text-sm mb-1 truncate">
                      {character.name}
                    </h3>
                    <p className="text-neutral-400 text-xs">
                      HP: {character.max_hp}
                      {character.level && ` • Lv.${character.level}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-white">Sessions</h2>
            <Link
              to={`/sessions?drawer=new&campaignId=${campaign.id}`}
              className="text-sm px-3 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors font-medium"
            >
              New Session
            </Link>
          </div>
          {sessions.length === 0 ? (
            <p className="text-neutral-300">No sessions in this campaign yet.</p>
          ) : (
            <ul className="space-y-2">
              {sessions.map((session) => (
                <li
                  key={session.id}
                  className="flex justify-between items-center p-3 hover:bg-white/5 rounded-xl transition-colors border border-transparent hover:border-white/10"
                >
                  <Link
                    to={`/sessions/${session.id}`}
                    className="text-white/90 hover:text-white transition-colors"
                  >
                    {session.name}
                  </Link>
                  <span className={`text-sm px-2 py-1 rounded-full border ${
                    session.status === 'active'
                      ? 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30'
                      : 'bg-white/10 text-white/70 border-white/15'
                  }`}>
                    {session.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <CharacterDetailSidebar
        character={selectedCharacter}
        open={selectedCharacter !== null}
        onClose={handleSidebarClose}
        onEdit={handleSidebarEdit}
        onDelete={handleSidebarDelete}
        onUpdate={handleSidebarUpdate}
      />
    </div>
  );
}

