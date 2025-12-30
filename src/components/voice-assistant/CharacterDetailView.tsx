import { memo } from 'react';
import { EnhancedResponse } from './EnhancedResponse';
import { cn } from '@/lib/utils';

interface CharacterDetailViewProps {
  content: string;
  className?: string;
}

/**
 * Rich formatted view for character deep-dives.
 * Renders markdown content with enhanced styling for comprehensive character explanations.
 */
export const CharacterDetailView = memo(({ content, className }: CharacterDetailViewProps) => {
  return (
    <div className={cn(
      "my-6 p-6 rounded-lg border-l-4 border-blue-500 bg-neutral-900/50",
      "shadow-lg",
      className
    )}>
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wide">
          Character Detail
        </h3>
      </div>
      <div className="prose prose-invert prose-sm max-w-none">
        <EnhancedResponse>
          {content}
        </EnhancedResponse>
      </div>
    </div>
  );
});

CharacterDetailView.displayName = 'CharacterDetailView';






