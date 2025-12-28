import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api from '../../services/api';
import type { Session } from '../../types';
import SessionWizardDrawer from './SessionWizardDrawer';

export default function SessionList() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();

  const drawerMode = searchParams.get('drawer'); // 'new' | null
  const drawerOpen = drawerMode === 'new';
  const presetCampaignId = useMemo(() => {
    const raw = searchParams.get('campaignId');
    return raw || null;
  }, [searchParams]);

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      setLoading(true);
      const response = await api.get('/sessions');
      setSessions(response.data);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleEndSession = async (id: string) => {
    if (!confirm('Are you sure you want to end this session?')) {
      return;
    }

    try {
      await api.put(`/sessions/${id}`, {
        status: 'ended',
        ended_at: new Date().toISOString()
      });
      fetchSessions(); // Refresh list
    } catch (err: any) {
      alert(err.response?.data?.error || 'Failed to end session');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="text-center py-8">
        <div className="text-neutral-300">Loading sessions...</div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-end items-center mb-6">
        <Link
          to="/sessions?drawer=new"
          className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 transition-colors text-sm font-medium"
        >
          New Session
        </Link>
      </div>

      {error && (
        <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl mb-4">
          {error}
        </div>
      )}

      {sessions.length === 0 ? (
        <div className="text-center py-12 bg-neutral-900/60 border border-neutral-800 rounded-2xl">
          <p className="text-neutral-300 text-lg mb-4">No sessions yet</p>
          <Link
            to="/sessions?drawer=new"
            className="text-white/90 hover:text-white font-medium"
          >
            Create your first session
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {sessions.map((session) => (
            <div
              key={session.id}
              className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 hover:bg-neutral-900/80 transition-colors"
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-xl font-semibold text-white">
                      {session.name}
                    </h3>
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        session.status === 'active'
                          ? 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/30'
                          : 'bg-white/10 text-white/70 border border-white/15'
                      }`}
                    >
                      {session.status}
                    </span>
                  </div>
                  <p className="text-sm text-neutral-300">
                    Started: {formatDate(session.started_at)}
                  </p>
                  {session.ended_at && (
                    <p className="text-sm text-neutral-300">
                      Ended: {formatDate(session.ended_at)}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Link
                    to={`/sessions/${session.id}`}
                    className="px-4 py-2 bg-white text-black rounded-xl hover:bg-neutral-200 text-sm font-medium transition-colors"
                  >
                    {session.status === 'active' ? 'View' : 'Details'}
                  </Link>
                  {session.status === 'active' && (
                    <button
                      onClick={() => handleEndSession(session.id)}
                      className="px-4 py-2 bg-red-500/20 text-red-200 border border-red-500/30 rounded-xl hover:bg-red-500/25 text-sm font-medium transition-colors"
                    >
                      End Session
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <SessionWizardDrawer
        open={drawerOpen}
        presetCampaignId={presetCampaignId}
        onClose={() => {
          setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.delete('drawer');
            next.delete('campaignId');
            return next;
          });
        }}
      />
    </div>
  );
}

