import { useState, useEffect } from 'react';
import { CharacterCard, CharacterGrid, SessionCard, SessionGrid, CampaignCard } from '../ui';
import { getCharacter, getCharacters, getSession, getCampaign } from '../../services/dataService';
import type { Character, Session, Campaign } from '../../types';

interface StructuredDataRendererProps {
  language: string;
  code: string;
}

export function StructuredDataRenderer({ language, code }: StructuredDataRendererProps) {
  const [data, setData] = useState<Character | Character[] | Session | Session[] | Campaign | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        let parsedData: any;
        try {
          parsedData = JSON.parse(code);
          console.log('[StructuredDataRenderer] Parsed data:', { language, parsedData, codeLength: code.length });
        } catch (e) {
          console.error('[StructuredDataRenderer] JSON parse error:', e, 'Code:', code);
          throw new Error('Invalid JSON in code block');
        }

        // Handle different structured data types
        if (language === 'json:character' || language === 'json:characters' || language.startsWith('json:character')) {
          if (Array.isArray(parsedData)) {
            // Check if array contains IDs or full objects
            if (parsedData.length === 0) {
              throw new Error('Empty character array');
            }
            if (typeof parsedData[0] === 'number') {
              // Array of character IDs
              const characters = await getCharacters(parsedData);
              setData(characters);
            } else if (parsedData[0] && typeof parsedData[0] === 'object') {
              // Array of full character objects - validate they have required fields
              const isValidCharacterArray = parsedData.every((item: any) => 
                item && typeof item === 'object' && (item.id || item.name)
              );
              if (isValidCharacterArray) {
                setData(parsedData as Character[]);
              } else {
                throw new Error('Invalid character array format: objects must have at least an id or name');
              }
            } else {
              throw new Error(`Invalid character array format: expected numbers or objects, got ${typeof parsedData[0]}`);
            }
          } else if (typeof parsedData === 'number') {
            // Single character ID
            const character = await getCharacter(parsedData);
            setData(character);
          } else if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData)) {
            // Full character object - accept any object, let CharacterCard handle missing fields
            setData(parsedData as Character);
          } else {
            console.error('[StructuredDataRenderer] Invalid character data:', { parsedData, type: typeof parsedData, isArray: Array.isArray(parsedData) });
            throw new Error(`Invalid character data format: expected object or number, got ${Array.isArray(parsedData) ? 'array' : typeof parsedData}`);
          }
        } else if (language === 'json:session' || language === 'json:sessions' || language.startsWith('json:session')) {
          if (Array.isArray(parsedData)) {
            // Array of sessions
            if (parsedData.length === 0) {
              throw new Error('Empty session array');
            }
            if (typeof parsedData[0] === 'number') {
              // Array of session IDs - fetch them
              const sessions = await Promise.all(parsedData.map((id: number) => getSession(id)));
              setData(sessions);
            } else if (parsedData[0] && typeof parsedData[0] === 'object') {
              // Array of full session objects
              setData(parsedData as Session[]);
            } else {
              throw new Error(`Invalid session array format: expected numbers or objects, got ${typeof parsedData[0]}`);
            }
          } else if (typeof parsedData === 'number') {
            // Single session ID
            const session = await getSession(parsedData);
            setData(session);
          } else if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData)) {
            // Full session object - accept any object, let SessionCard handle missing fields
            setData(parsedData as Session);
          } else {
            console.error('[StructuredDataRenderer] Invalid session data:', { parsedData, type: typeof parsedData, isArray: Array.isArray(parsedData) });
            throw new Error(`Invalid session data format: expected object, array, or number, got ${Array.isArray(parsedData) ? 'array' : typeof parsedData}`);
          }
        } else if (language === 'json:campaign' || language.startsWith('json:campaign')) {
          if (typeof parsedData === 'number') {
            // Campaign ID
            const campaign = await getCampaign(parsedData);
            setData(campaign);
          } else if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData)) {
            // Full campaign object - accept any object, let CampaignCard handle missing fields
            setData(parsedData as Campaign);
          } else {
            console.error('[StructuredDataRenderer] Invalid campaign data:', { parsedData, type: typeof parsedData, isArray: Array.isArray(parsedData) });
            throw new Error(`Invalid campaign data format: expected object or number, got ${Array.isArray(parsedData) ? 'array' : typeof parsedData}`);
          }
        }
      } catch (err: any) {
        console.error('Error fetching structured data:', err);
        setError(err.message || 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    if (language && (language.startsWith('json:character') || language === 'json:characters' || language.startsWith('json:session') || language.startsWith('json:campaign'))) {
      fetchData();
    }
  }, [language, code]);

  // Only render for special language types
  if (!language || (!language.startsWith('json:character') && language !== 'json:characters' && !language.startsWith('json:session') && language !== 'json:sessions' && !language.startsWith('json:campaign'))) {
    return null;
  }

  if (loading) {
    return (
      <div className="my-4 py-4 border-l-2 border-neutral-700 pl-4">
        <div className="text-sm text-neutral-500">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="my-4 py-4 border-l-2 border-red-700 pl-4">
        <div className="text-sm text-red-400">Error: {error}</div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  // Render appropriate component based on data type
  if (language.startsWith('json:character')) {
    if (Array.isArray(data)) {
      return <CharacterGrid characters={data as Character[]} />;
    } else {
      return <CharacterCard character={data as Character} />;
    }
  } else if (language.startsWith('json:session') || language === 'json:sessions') {
    if (Array.isArray(data)) {
      return <SessionGrid sessions={data as Session[]} />;
    } else {
      return <SessionCard session={data as Session} />;
    }
  } else if (language.startsWith('json:campaign')) {
    return <CampaignCard campaign={data as Campaign} />;
  }

  return null;
}

