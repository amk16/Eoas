import api from './api';
import type { Conversation, ConversationMessage } from '../types';

export interface ConversationWithMessages extends Conversation {
  messages: ConversationMessage[];
}

/**
 * Get all conversations for the current user
 */
export async function getConversations(): Promise<Conversation[]> {
  try {
    const response = await api.get<Conversation[]>('/conversations');
    return response.data;
  } catch (error: any) {
    console.error('Error fetching conversations:', error);
    throw new Error(error.response?.data?.detail || 'Failed to fetch conversations');
  }
}

/**
 * Get a single conversation with its messages
 */
export async function getConversation(conversationId: string): Promise<ConversationWithMessages> {
  try {
    const response = await api.get<ConversationWithMessages>(`/conversations/${conversationId}`);
    return response.data;
  } catch (error: any) {
    console.error('Error fetching conversation:', error);
    throw new Error(error.response?.data?.detail || 'Failed to fetch conversation');
  }
}

/**
 * Create a new conversation
 */
export async function createConversation(title?: string): Promise<Conversation> {
  try {
    const response = await api.post<Conversation>('/conversations', {
      title: title || null,
    });
    return response.data;
  } catch (error: any) {
    console.error('Error creating conversation:', error);
    throw new Error(error.response?.data?.detail || 'Failed to create conversation');
  }
}

/**
 * Update a conversation (e.g., change title)
 */
export async function updateConversation(
  conversationId: string,
  data: { title?: string }
): Promise<Conversation> {
  try {
    const response = await api.put<Conversation>(`/conversations/${conversationId}`, data);
    return response.data;
  } catch (error: any) {
    console.error('Error updating conversation:', error);
    throw new Error(error.response?.data?.detail || 'Failed to update conversation');
  }
}

/**
 * Delete a conversation
 */
export async function deleteConversation(conversationId: string): Promise<void> {
  try {
    await api.delete(`/conversations/${conversationId}`);
  } catch (error: any) {
    console.error('Error deleting conversation:', error);
    throw new Error(error.response?.data?.detail || 'Failed to delete conversation');
  }
}

/**
 * Add a message to a conversation
 */
export async function addMessage(
  conversationId: string,
  role: 'user' | 'assistant',
  content: string
): Promise<ConversationMessage> {
  try {
    const response = await api.post<ConversationMessage>(`/conversations/${conversationId}/messages`, {
      role,
      content,
    });
    return response.data;
  } catch (error: any) {
    console.error('Error adding message:', error);
    throw new Error(error.response?.data?.detail || 'Failed to add message');
  }
}

