import { useEffect, useMemo, useState } from 'react';
import type React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api from '../../services/api';
import type { Character } from '../../types';
import CharacterWizardDrawer from './CharacterWizardDrawer';
import CharacterDetailSidebar from './CharacterDetailSidebar';

export default function CharacterList() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedCharacterId, setSelectedCharacterId] = useState<number | null>(null);
  
  const drawerMode = searchParams.get('drawer'); // 'new' | 'edit' | null
  const drawerOpen = drawerMode === 'new' || drawerMode === 'edit';
  const editId = useMemo(() => {
    if (drawerMode !== 'edit') return null;
    const raw = searchParams.get('id');
    const n = raw ? parseInt(raw, 10) : NaN;
    return Number.isFinite(n) ? n : null;
  }, [drawerMode, searchParams]);
  const presetCampaignId = useMemo(() => {
    const raw = searchParams.get('campaignId');
    const n = raw ? parseInt(raw, 10) : NaN;
    return Number.isFinite(n) ? n : null;
  }, [searchParams]);

  const selectedCharacter = useMemo(() => {
    if (!selectedCharacterId) return null;
    return characters.find((c) => c.id === selectedCharacterId) || null;
  }, [selectedCharacterId, characters]);

  useEffect(() => {
    fetchCharacters();
  }, []);

  const fetchCharacters = async () => {
    try {
      setLoading(true);
      const response = await api.get('/characters');
      setCharacters(response.data);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load characters');
    } finally {
      setLoading(false);
    }
  };

  const handleCardClick = (characterId: number) => {
    setSelectedCharacterId(characterId);
  };

  const handleSidebarClose = () => {
    setSelectedCharacterId(null);
  };

  const handleSidebarEdit = (characterId: number) => {
    setSelectedCharacterId(null);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('drawer', 'edit');
      next.set('id', String(characterId));
      next.delete('campaignId');
      return next;
    });
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
    // Update the character in the list
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
        <div className="text-neutral-300">Loading characters...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-end items-center mb-6">
        <Link
          to="/characters?drawer=new"
          className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium"
        >
          Create Character
        </Link>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl mb-4">
          {error}
        </div>
      )}

      {characters.length === 0 ? (
        <div className="text-center py-12 bg-neutral-900/60 border border-neutral-800 rounded-2xl">
          <p className="text-neutral-300 text-lg mb-4">No characters yet</p>
          <Link
            to="/characters?drawer=new"
            className="text-white/90 hover:text-white font-medium"
          >
            Create your first character
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {characters.map((character) => (
            <div
              key={character.id}
              onClick={() => handleCardClick(character.id)}
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
              <div className="p-4">
                <h3 className="text-white font-semibold text-lg mb-1 truncate">
                  {character.name}
                </h3>
                <p className="text-neutral-400 text-sm">
                  Max HP: {character.max_hp}
                  {character.level && ` • Level ${character.level}`}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      <CharacterWizardDrawer
        open={drawerOpen}
        mode={drawerMode === 'edit' ? 'edit' : 'new'}
        characterId={editId}
        presetCampaignId={presetCampaignId}
        onClose={() => {
          setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.delete('drawer');
            next.delete('id');
            next.delete('campaignId');
            return next;
          });
        }}
        onSaved={() => {
          fetchCharacters();
        }}
      />

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

