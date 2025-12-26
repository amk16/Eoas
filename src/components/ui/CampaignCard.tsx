import { memo } from 'react';
import type { Campaign } from '../../types';
import { cn } from '@/lib/utils';

interface CampaignCardProps {
  campaign: Campaign;
  className?: string;
}

export const CampaignCard = memo(({ campaign, className }: CampaignCardProps) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className={cn(
      "my-4 py-4 border-l-2 border-neutral-700 pl-4 space-y-2",
      className
    )}>
      <h3 className="text-lg font-semibold text-neutral-100">{campaign.name || 'Unnamed Campaign'}</h3>
      
      {campaign.description && (
        <p className="text-sm text-neutral-300 leading-relaxed mt-2">
          {campaign.description}
        </p>
      )}
      
      {campaign.created_at && (
        <div className="text-xs text-neutral-500 mt-3">
          Created {formatDate(campaign.created_at)}
        </div>
      )}
    </div>
  );
});

CampaignCard.displayName = 'CampaignCard';

