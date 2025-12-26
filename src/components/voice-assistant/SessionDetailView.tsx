import { memo } from 'react';
import { EnhancedResponse } from './EnhancedResponse';
import { cn } from '@/lib/utils';

interface SessionDetailViewProps {
  content: string;
  className?: string;
}

/**
 * Rich formatted view for session deep-dives.
 * Renders markdown content with enhanced styling for comprehensive session explanations.
 */
export const SessionDetailView = memo(({ content, className }: SessionDetailViewProps) => {
  return (
    <div className={cn(
      "my-6 p-6 rounded-lg border-l-4 border-green-500 bg-neutral-900/50",
      "shadow-lg",
      className
    )}>
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-green-400 uppercase tracking-wide">
          Session Detail
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

SessionDetailView.displayName = 'SessionDetailView';




