import type { Character } from '../types';
import api from './api';
import { logger } from '../lib/logger';

/**
 * Generate a descriptive prompt for character art generation based on character data
 * @param character - The character object containing all character information
 * @returns A formatted prompt string suitable for image generation
 */
export function generateCharacterArtPrompt(character: Character): string {
  const parts: string[] = [];
  
  // Core identity
  if (character.name) {
    parts.push(character.name);
  }
  
  // Race and class (most defining visual features)
  if (character.race) {
    parts.push(character.race);
  }
  if (character.class_name) {
    parts.push(character.class_name);
  }
  
  // Level (can influence appearance/equipment)
  if (character.level) {
    parts.push(`Level ${character.level}`);
  }
  
  // Alignment (can influence aesthetic)
  if (character.alignment) {
    parts.push(character.alignment);
  }
  
  // Background (can add flavor)
  if (character.background) {
    parts.push(character.background);
  }
  
  // Additional context from notes if available
  if (character.notes) {
    // Extract key visual descriptors from notes (simplified - could be enhanced with NLP)
    const noteWords = character.notes.split(/\s+/).slice(0, 10).join(' ');
    if (noteWords) {
      parts.push(noteWords);
    }
  }
  
  // Base prompt structure
  const basePrompt = 'D&D fantasy character portrait, detailed, professional artwork';
  const characterDetails = parts.filter(Boolean).join(', ');
  
  const finalPrompt = characterDetails 
    ? `${basePrompt}, ${characterDetails}`
    : basePrompt;
  
  return finalPrompt;
}

/**
 * Generate character art using nano banana image generation service
 * 
 * @param character - The character object to generate art for
 * @returns Promise resolving to the image URL (or placeholder if not configured)
 */
export async function generateCharacterArt(character: Character): Promise<{
  imageUrl: string;
  prompt: string;
}> {
  try {
    const prompt = generateCharacterArtPrompt(character);
    
    // Placeholder: Return a placeholder image URL
    // In production, this would call the actual API
    const placeholderImageUrl = `https://via.placeholder.com/512x512/000000/FFFFFF?text=${encodeURIComponent(character.name || 'Character')}`;
    
    logger.warn('Using placeholder image. Nano banana API integration not yet configured.', {
      characterId: character.id,
    });
    
    const result = {
      imageUrl: placeholderImageUrl,
      prompt: prompt,
    };
    
    return result;
  } catch (error) {
    logger.error('generateCharacterArt failed', {
      characterId: character.id,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

/**
 * Generate and save character art via backend API
 * This calls the backend endpoint which handles image generation and updates the character
 * 
 * @param characterId - The ID of the character to generate art for
 * @returns Promise resolving to the updated character with art URL and prompt
 */
export async function generateAndSaveCharacterArt(characterId: string): Promise<Character> {
  try {
    // Call backend endpoint to generate art
    const response = await api.post(`/characters/${characterId}/generate-art`);
    
    logger.info('Character art generated and saved', { characterId });
    
    return response.data;
  } catch (error: any) {
    logger.error('generateAndSaveCharacterArt failed', {
      characterId: characterId,
      error: error instanceof Error ? error.message : String(error),
    });
    throw new Error(
      error.response?.data?.detail || error.response?.data?.error || 'Failed to generate character art'
    );
  }
}

