import api from './api';
import type { Character, Session, Campaign } from '../types';

/**
 * Fetch a single character by ID
 */
export async function getCharacter(characterId: number): Promise<Character> {
  try {
    const response = await api.get<Character>(`/characters/${characterId}`);
    return response.data;
  } catch (error: any) {
    console.error('Error fetching character:', error);
    throw new Error(error.response?.data?.error || 'Failed to fetch character');
  }
}

/**
 * Fetch multiple characters by IDs
 */
export async function getCharacters(characterIds: number[]): Promise<Character[]> {
  try {
    // Fetch all characters in parallel
    const promises = characterIds.map(id => getCharacter(id));
    return await Promise.all(promises);
  } catch (error: any) {
    console.error('Error fetching characters:', error);
    throw error;
  }
}

/**
 * Fetch a single session by ID
 */
export async function getSession(sessionId: number): Promise<Session> {
  try {
    const response = await api.get<Session>(`/sessions/${sessionId}`);
    return response.data;
  } catch (error: any) {
    console.error('Error fetching session:', error);
    throw new Error(error.response?.data?.error || 'Failed to fetch session');
  }
}

/**
 * Fetch a single campaign by ID
 */
export async function getCampaign(campaignId: number): Promise<Campaign> {
  try {
    const response = await api.get<Campaign>(`/campaigns/${campaignId}`);
    return response.data;
  } catch (error: any) {
    console.error('Error fetching campaign:', error);
    throw new Error(error.response?.data?.error || 'Failed to fetch campaign');
  }
}

