export type User = {
  id: number;
  email: string;
};

export type Campaign = {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  display_art_url: string | null;
  art_prompt: string | null;
  created_at: string;
  updated_at: string;
};

export type Character = {
  id: string;
  user_id: string;
  campaign_id: string | null;
  name: string;
  max_hp: number;
  race: string | null;
  class_name: string | null;
  level: number | null;
  ac: number | null;
  initiative_bonus: number | null;
  temp_hp: number | null;
  background: string | null;
  alignment: string | null;
  notes: string | null;
  display_art_url: string | null;
  art_prompt: string | null;
  created_at: string;
  updated_at: string;
};

export type Session = {
  id: string;
  user_id: string;
  campaign_id: string | null;
  name: string;
  started_at: string;
  ended_at: string | null;
  status: 'active' | 'ended';
};

export type SessionCharacter = {
  session_id: number;
  character_id: number;
  starting_hp: number;
  current_hp: number;
};

export type DamageEvent = {
  id: number;
  session_id: number;
  character_id: number;
  amount: number;
  type: 'damage' | 'healing';
  timestamp: string;
  transcript_segment: string | null;
};

