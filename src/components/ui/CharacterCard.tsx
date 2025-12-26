import { memo } from 'react';
import type { Character } from '../../types';
import { cn } from '@/lib/utils';

interface CharacterCardProps {
  character: Character;
  className?: string;
}

export const CharacterCard = memo(({ character, className }: CharacterCardProps) => {
  return (
    <div className={cn(
      "my-4 py-4 border-l-2 border-neutral-700 pl-4 space-y-2",
      className
    )}>
      <div className="flex items-baseline gap-3">
        <h3 className="text-lg font-semibold text-neutral-100">{character.name || 'Unnamed Character'}</h3>
        {character.level && (
          <span className="text-sm text-neutral-400">Level {character.level}</span>
        )}
      </div>
      
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-neutral-300">
        {character.race && (
          <div>
            <span className="text-neutral-500">Race:</span>{' '}
            <span className="text-neutral-200">{character.race}</span>
          </div>
        )}
        {character.class_name && (
          <div>
            <span className="text-neutral-500">Class:</span>{' '}
            <span className="text-neutral-200">{character.class_name}</span>
          </div>
        )}
        {character.max_hp !== undefined && character.max_hp !== null && (
          <div>
            <span className="text-neutral-500">HP:</span>{' '}
            <span className="text-neutral-200">{character.max_hp}</span>
          </div>
        )}
        {character.ac !== null && (
          <div>
            <span className="text-neutral-500">AC:</span>{' '}
            <span className="text-neutral-200">{character.ac}</span>
          </div>
        )}
        {character.alignment && (
          <div>
            <span className="text-neutral-500">Alignment:</span>{' '}
            <span className="text-neutral-200">{character.alignment}</span>
          </div>
        )}
      </div>
      
      {character.background && (
        <p className="text-sm text-neutral-400 mt-2 italic">{character.background}</p>
      )}
      
      {character.notes && (
        <div className="mt-3 pt-3 border-t border-neutral-800">
          <p className="text-sm text-neutral-400 leading-relaxed">{character.notes}</p>
        </div>
      )}
    </div>
  );
});

CharacterCard.displayName = 'CharacterCard';

interface CharacterGridProps {
  characters: Character[];
  className?: string;
}

export const CharacterGrid = memo(({ characters, className }: CharacterGridProps) => {
  if (characters.length === 0) return null;
  
  if (characters.length === 1) {
    return <CharacterCard character={characters[0]} className={className} />;
  }
  
  return (
    <div className={cn("my-4 space-y-4", className)}>
      {characters.map((character) => (
        <CharacterCard key={character.id} character={character} />
      ))}
    </div>
  );
});

CharacterGrid.displayName = 'CharacterGrid';

