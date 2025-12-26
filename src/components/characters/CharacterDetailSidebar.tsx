import { useState } from 'react';
import type React from 'react';
import type { Character } from '../../types';
import Drawer from '../ui/Drawer';
import { generateAndSaveCharacterArt } from '../../services/imageGenerationService';

interface CharacterDetailSidebarProps {
  character: Character | null;
  open: boolean;
  onClose: () => void;
  onEdit: (characterId: number) => void;
  onDelete: (characterId: number) => void;
  onUpdate?: (updatedCharacter: Character) => void;
}

export default function CharacterDetailSidebar({
  character,
  open,
  onClose,
  onEdit,
  onDelete,
  onUpdate,
}: CharacterDetailSidebarProps) {
  const [generatingArt, setGeneratingArt] = useState(false);
  const [artError, setArtError] = useState<string | null>(null);

  const handleDelete = () => {
    if (!character) return;
    
    if (confirm(`Are you sure you want to delete ${character.name}? This action cannot be undone.`)) {
      onDelete(character.id);
    }
  };

  const handleEdit = () => {
    if (!character) return;
    onEdit(character.id);
  };

  const handleGenerateArt = async () => {
    if (!character) return;
    
    setGeneratingArt(true);
    setArtError(null);
    
    try {
      const updatedCharacter = await generateAndSaveCharacterArt(character.id);
      
      // Notify parent to update character data
      if (onUpdate) {
        onUpdate(updatedCharacter);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to generate character art';
      setArtError(errorMessage);
      console.error('Error generating character art:', error);
    } finally {
      setGeneratingArt(false);
    }
  };

  if (!character) return null;

  const footer = (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={handleEdit}
        className="flex-1 px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium"
      >
        Edit
      </button>
      <button
        type="button"
        onClick={handleDelete}
        className="flex-1 px-4 py-2 bg-red-500/80 text-white rounded-xl hover:bg-red-500 transition-colors text-sm font-medium"
      >
        Delete
      </button>
    </div>
  );

  return (
    <Drawer
      open={open}
      title={character.name}
      description="Character details and information"
      onClose={onClose}
      footer={footer}
    >
      <div className="space-y-6">
        {/* Character Art/Image */}
        <div>
          {character.display_art_url ? (
            <div className="w-full aspect-square bg-neutral-950 rounded-xl overflow-hidden border border-neutral-800 mb-3">
              <img
                src={
                  character.display_art_url.startsWith('/api/')
                    ? `${import.meta.env.VITE_API_URL || 'http://localhost:3001'}${character.display_art_url}`
                    : character.display_art_url
                }
                alt={character.name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  // Fallback if image fails to load
                  const target = e.target as HTMLImageElement;
                  target.style.display = 'none';
                }}
              />
            </div>
          ) : (
            <div className="w-full aspect-square bg-neutral-950 rounded-xl border border-neutral-800 mb-3 flex items-center justify-center">
              <p className="text-neutral-500 text-sm">No character art generated yet</p>
            </div>
          )}
          
          {/* Generate Art Button */}
          <button
            type="button"
            onClick={handleGenerateArt}
            disabled={generatingArt}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {generatingArt ? (
              <>
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Generating Art...
              </>
            ) : (
              'Generate Art'
            )}
          </button>
          
          {artError && (
            <div className="mt-2 bg-red-950/40 border border-red-900 text-red-200 px-3 py-2 rounded-xl text-sm">
              {artError}
            </div>
          )}
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
            <div className="text-sm text-neutral-400 mb-1">Max HP</div>
            <div className="text-2xl font-bold text-white">{character.max_hp}</div>
          </div>
          
          {character.ac !== null && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm text-neutral-400 mb-1">AC</div>
              <div className="text-2xl font-bold text-white">{character.ac}</div>
            </div>
          )}

          {character.level !== null && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm text-neutral-400 mb-1">Level</div>
              <div className="text-2xl font-bold text-white">{character.level}</div>
            </div>
          )}

          {character.initiative_bonus !== null && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm text-neutral-400 mb-1">Initiative</div>
              <div className="text-2xl font-bold text-white">
                {character.initiative_bonus >= 0 ? `+${character.initiative_bonus}` : character.initiative_bonus}
              </div>
            </div>
          )}

          {character.temp_hp !== null && character.temp_hp > 0 && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm text-neutral-400 mb-1">Temp HP</div>
              <div className="text-2xl font-bold text-white">{character.temp_hp}</div>
            </div>
          )}
        </div>

        {/* Character Details */}
        <div className="space-y-4">
          {(character.race || character.class_name) && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm font-semibold text-white mb-3">Identity</div>
              <div className="space-y-2 text-sm">
                {character.race && (
                  <div className="flex justify-between">
                    <span className="text-neutral-400">Race</span>
                    <span className="text-white">{character.race}</span>
                  </div>
                )}
                {character.class_name && (
                  <div className="flex justify-between">
                    <span className="text-neutral-400">Class</span>
                    <span className="text-white">{character.class_name}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {(character.background || character.alignment) && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm font-semibold text-white mb-3">Background</div>
              <div className="space-y-2 text-sm">
                {character.background && (
                  <div className="flex justify-between">
                    <span className="text-neutral-400">Background</span>
                    <span className="text-white">{character.background}</span>
                  </div>
                )}
                {character.alignment && (
                  <div className="flex justify-between">
                    <span className="text-neutral-400">Alignment</span>
                    <span className="text-white">{character.alignment}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {character.campaign_id && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm font-semibold text-white mb-2">Campaign</div>
              <div className="text-sm text-neutral-300">
                Campaign ID: {character.campaign_id}
              </div>
            </div>
          )}

          {character.notes && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4">
              <div className="text-sm font-semibold text-white mb-3">Notes</div>
              <div className="text-sm text-neutral-300 whitespace-pre-wrap">
                {character.notes}
              </div>
            </div>
          )}
        </div>

        {/* Metadata */}
        <div className="text-xs text-neutral-500 space-y-1 border-t border-neutral-800 pt-4">
          <div>Created: {new Date(character.created_at).toLocaleDateString()}</div>
          <div>Last updated: {new Date(character.updated_at).toLocaleDateString()}</div>
        </div>
      </div>
    </Drawer>
  );
}

