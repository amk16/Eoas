import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Drawer from '../ui/Drawer';
import { getConversations, deleteConversation } from '../../services/conversationService';
import type { Conversation } from '../../types';

interface ConversationsDrawerProps {
  open: boolean;
  onClose: () => void;
  onSelectConversation?: (conversationId: string) => void;
}

export default function ConversationsDrawer({
  open,
  onClose,
  onSelectConversation,
}: ConversationsDrawerProps) {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      fetchConversations();
    }
  }, [open]);

  const fetchConversations = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await getConversations();
      setConversations(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load conversations');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectConversation = (conversationId: string) => {
    if (onSelectConversation) {
      onSelectConversation(conversationId);
    } else {
      // Default behavior: navigate to conversation
      navigate(`/ioun-silence/${conversationId}`);
    }
    onClose();
  };

  const handleDeleteConversation = async (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent selecting the conversation when clicking delete
    
    if (!confirm('Are you sure you want to delete this conversation?')) {
      return;
    }

    try {
      setDeletingId(conversationId);
      await deleteConversation(conversationId);
      setConversations(conversations.filter((c) => c.id !== conversationId));
    } catch (err: any) {
      alert(err.message || 'Failed to delete conversation');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
      <Drawer
        open={open}
        title="Conversations"
        description={conversations.length > 0 ? `${conversations.length} conversation${conversations.length !== 1 ? 's' : ''}` : 'View and manage your past conversations'}
        onClose={onClose}
      >
      <div className="space-y-3">
        {error && (
          <div className="bg-red-950/40 border border-red-900 text-red-200 px-4 py-3 rounded-xl">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-8">
            <div className="text-neutral-300">Loading conversations...</div>
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-12 bg-neutral-900/60 border border-neutral-800 rounded-2xl">
            <p className="text-neutral-300 text-lg mb-2">No conversations yet</p>
            <p className="text-neutral-400 text-sm">Start a new chat to create your first conversation</p>
          </div>
        ) : (
          <div className="space-y-2">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                onClick={() => handleSelectConversation(conversation.id)}
                className="bg-neutral-900/60 border border-neutral-800 rounded-xl p-4 hover:bg-neutral-900/80 transition-colors cursor-pointer group"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-white truncate mb-1">
                      {conversation.title}
                    </h3>
                    <p className="text-xs text-neutral-400">
                      {formatDate(conversation.last_message_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conversation.id, e)}
                    disabled={deletingId === conversation.id}
                    className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity px-2 py-1 text-xs text-red-200 hover:text-red-100 hover:bg-red-500/10 rounded-lg border border-red-500/20 disabled:opacity-50"
                  >
                    {deletingId === conversation.id ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Drawer>
  );
}

