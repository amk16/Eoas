import type { Character } from '../types';
import api from './api';

/**
 * Generate a descriptive prompt for character art generation based on character data
 * @param character - The character object containing all character information
 * @returns A formatted prompt string suitable for image generation
 */
export function generateCharacterArtPrompt(character: Character): string {
  console.log('[imageGenerationService] generateCharacterArtPrompt called', {
    characterId: character.id,
    characterName: character.name,
  });
  
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
  
  console.log('[imageGenerationService] Prompt generated', {
    characterId: character.id,
    promptParts: parts.filter(Boolean),
    finalPrompt: finalPrompt,
    promptLength: finalPrompt.length,
  });
  
  return finalPrompt;
}

/**
 * Generate character art using nano banana image generation service
 * 
 * NOTE: This is a placeholder structure. Actual implementation will depend on:
 * - Nano banana API endpoint details
 * - Authentication requirements
 * - Request/response format
 * - Image storage location (S3, CDN, etc.)
 * 
 * @param character - The character object to generate art for
 * @returns Promise resolving to the image URL (or placeholder if not configured)
 */
export async function generateCharacterArt(character: Character): Promise<{
  imageUrl: string;
  prompt: string;
}> {
  console.log('[imageGenerationService] generateCharacterArt called', {
    characterId: character.id,
    characterName: character.name,
    hasExistingArt: !!character.display_art_url,
  });
  
  const startTime = Date.now();
  
  try {
    const prompt = generateCharacterArtPrompt(character);
    
    // TODO: Replace with actual nano banana API integration
    // Expected flow:
    // 1. Call nano banana API with the generated prompt
    // 2. Receive image data/URL from the service
    // 3. Optionally upload to S3 or other storage solution
    // 4. Return the final image URL and prompt
    
    // Placeholder: Return a placeholder image URL
    // In production, this would call the actual API
    const placeholderImageUrl = `https://via.placeholder.com/512x512/000000/FFFFFF?text=${encodeURIComponent(character.name || 'Character')}`;
    
    console.warn(
      '[imageGenerationService] Using placeholder image. ' +
      'Nano banana API integration not yet configured.',
      {
        characterId: character.id,
        placeholderUrl: placeholderImageUrl,
      }
    );
    
    const result = {
      imageUrl: placeholderImageUrl,
      prompt: prompt,
    };
    
    const duration = Date.now() - startTime;
    console.log('[imageGenerationService] generateCharacterArt completed', {
      characterId: character.id,
      imageUrl: result.imageUrl,
      promptLength: result.prompt.length,
      durationMs: duration,
    });
    
    return result;
  } catch (error) {
    const duration = Date.now() - startTime;
    console.error('[imageGenerationService] generateCharacterArt failed', {
      characterId: character.id,
      error: error instanceof Error ? error.message : String(error),
      durationMs: duration,
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
  console.log('[imageGenerationService] generateAndSaveCharacterArt called', {
    characterId: characterId,
  });
  
  const startTime = Date.now();
  
  try {
    // Call backend endpoint to generate art
    const response = await api.post(`/characters/${characterId}/generate-art`);
    
    const duration = Date.now() - startTime;
    console.log('[imageGenerationService] generateAndSaveCharacterArt completed', {
      characterId: characterId,
      character: response.data,
      durationMs: duration,
    });
    
    return response.data;
  } catch (error: any) {
    const duration = Date.now() - startTime;
    console.error('[imageGenerationService] generateAndSaveCharacterArt failed', {
      characterId: characterId,
      error: error instanceof Error ? error.message : String(error),
      durationMs: duration,
    });
    throw new Error(
      error.response?.data?.detail || error.response?.data?.error || 'Failed to generate character art'
    );
  }
}

