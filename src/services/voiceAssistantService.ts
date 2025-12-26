import api from './api';

export interface ConversationToken {
  signedUrl?: string;
  conversationToken?: string;
  agentId?: string;
  agent_id?: string; // Keep for backward compatibility
  conversation_id?: string;
  [key: string]: any;
}

export interface PendingAction {
  action_id: string;
  status: string;
  description: string;
  tool_name: string;
  parameters: Record<string, any>;
}

/**
 * Fetch a conversation token from the backend
 */
export async function getConversationToken(): Promise<ConversationToken> {
  try {
    const response = await api.get<ConversationToken>('/conversational-ai/token');
    return response.data;
  } catch (error: any) {
    console.error('Error fetching conversation token:', error);
    throw new Error(error.response?.data?.detail || 'Failed to get conversation token');
  }
}

/**
 * Submit an action proposed by the assistant
 */
export async function submitAction(
  toolName: string,
  parameters: Record<string, any>
): Promise<PendingAction> {
  try {
    const response = await api.post<PendingAction>('/conversational-ai/action', {
      tool_name: toolName,
      parameters,
    });
    return response.data;
  } catch (error: any) {
    console.error('Error submitting action:', error);
    throw new Error(error.response?.data?.detail || 'Failed to submit action');
  }
}

/**
 * Confirm or reject a pending action
 */
export async function confirmAction(
  actionId: string,
  confirmed: boolean
): Promise<{ action_id: string; status: string; result?: any; message?: string }> {
  try {
    const response = await api.post('/conversational-ai/confirm', {
      action_id: actionId,
      confirmed,
    });
    return response.data;
  } catch (error: any) {
    console.error('Error confirming action:', error);
    throw new Error(error.response?.data?.detail || 'Failed to confirm action');
  }
}

/**
 * Get all pending actions for the current user
 */
export async function getPendingActions(): Promise<PendingAction[]> {
  try {
    const response = await api.get<PendingAction[]>('/conversational-ai/pending-actions');
    return response.data;
  } catch (error: any) {
    console.error('Error fetching pending actions:', error);
    throw new Error(error.response?.data?.detail || 'Failed to fetch pending actions');
  }
}

// Note: buildConversationWebSocketUrl removed - SDK handles URL construction internally

