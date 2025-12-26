import { memo } from 'react';
import type { Session } from '../../types';
import { cn } from '@/lib/utils';

interface SessionCardProps {
  session: Session;
  className?: string;
}

export const SessionCard = memo(({ session, className }: SessionCardProps) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const statusColor = session.status === 'active' 
    ? 'text-green-400' 
    : 'text-neutral-400';

  return (
    <div className={cn(
      "my-4 py-4 border-l-2 border-neutral-700 pl-4 space-y-2",
      className
    )}>
      <div className="flex items-baseline gap-3">
        <h3 className="text-lg font-semibold text-neutral-100">{session.name || 'Unnamed Session'}</h3>
        {session.status && (
          <span className={cn("text-xs font-medium uppercase tracking-wide", statusColor)}>
            {session.status}
          </span>
        )}
      </div>
      
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-neutral-300">
        {session.started_at && (
          <div>
            <span className="text-neutral-500">Started:</span>{' '}
            <span className="text-neutral-200">{formatDate(session.started_at)}</span>
          </div>
        )}
        {session.ended_at && (
          <div>
            <span className="text-neutral-500">Ended:</span>{' '}
            <span className="text-neutral-200">{formatDate(session.ended_at)}</span>
          </div>
        )}
        {session.campaign_id && (
          <div>
            <span className="text-neutral-500">Campaign ID:</span>{' '}
            <span className="text-neutral-200">{session.campaign_id}</span>
          </div>
        )}
      </div>
    </div>
  );
});

SessionCard.displayName = 'SessionCard';

interface SessionGridProps {
  sessions: Session[];
  className?: string;
}

export const SessionGrid = memo(({ sessions, className }: SessionGridProps) => {
  if (sessions.length === 0) return null;
  
  if (sessions.length === 1) {
    return <SessionCard session={sessions[0]} className={className} />;
  }
  
  return (
    <div className={cn("my-4 space-y-4", className)}>
      {sessions.map((session) => (
        <SessionCard key={session.id || session.name || Math.random()} session={session} />
      ))}
    </div>
  );
});

SessionGrid.displayName = 'SessionGrid';

