import { memo } from 'react';
import { EnhancedResponse } from './EnhancedResponse';
import { cn } from '@/lib/utils';

interface CampaignDetailViewProps {
  content: string;
  className?: string;
}

/**
 * Rich formatted view for campaign deep-dives.
 * Renders markdown content with enhanced styling for comprehensive campaign explanations.
 */
export const CampaignDetailView = memo(({ content, className }: CampaignDetailViewProps) => {
  return (
    <div className={cn(
      "my-6 p-6 rounded-lg border-l-4 border-purple-500 bg-neutral-900/50",
      "shadow-lg",
      className
    )}>
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wide">
          Campaign Detail
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

CampaignDetailView.displayName = 'CampaignDetailView';





