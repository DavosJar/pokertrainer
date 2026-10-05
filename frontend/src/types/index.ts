export interface VisualCard {
  rank: string;
  suit: string;
  symbol: string;
  name: string;
  color: string;
  textColor: string;
}

export interface ActionOption {
  id: string;
  label: string;
  color: string;
  hotkey?: string;
  has_followup: boolean;
  text_color?: string | null;
}

/** Estado de mesa en un instante. Los montos ya vienen calculados por el backend. */
export interface TableStateData {
  effective_stack: number;
  pot: number;
  dead: number;
  bets: { sb: number | null; bb: number | null; hero: number | null };
  stacks: { sb: number; bb: number; hero: number };
  all_in: { sb: boolean; bb: boolean; hero: boolean };
  folded: { sb: boolean; bb: boolean };
}

/** PASO 2: qué rival responde y de qué tipo. */
export interface VillainReaction {
  actor: 'SB' | 'BB';
  kind: 'normal' | 'ai';
  label: string;
}

export interface ScenarioListItem {
  id: string;
  name: string;
  position: string;
  stack_range: string;
  spot: string;
  game: string;
  tags: string[];
  action_counts: Record<string, number>;
  actions_config: Record<string, any>;
  total_hands: number;
}

export interface HandDetail {
  hand: string;
  action: string;
  followup?: string | null;
  frequency: number;
  marginal?: boolean;
}

export interface ScenarioDetail {
  id: string;
  name: string;
  position: string;
  stack_range: string;
  spot: string;
  game: string;
  tags: string[];
  actions_config: Record<string, any>;
  followups_config: Record<string, any>;
  reference_stats?: any;
  hands: Record<string, HandDetail>;
  /** Solo en by_stack: los cortes disponibles y cual se esta pintando. */
  by_stack_keys?: string[];
  hands_stack?: string | null;
}

export interface NextHandData {
  session_id: string;
  scenario_id: string;
  scenario_name: string;
  position: string;
  stack_range: string;
  spot: string;
  tags: string[];
  hand: string;
  cards: VisualCard[];
  level: number;
  parent_action?: string | null;
  available_actions: ActionOption[];
  followup_prompt?: string | null;
  current_streak: number;
  session_hands_played: number;
  session_accuracy_pct: number;
  table?: TableStateData | null;
  villain?: VillainReaction | null;
  /** True si la mesa es de 2 asientos: hero en una ciega y un solo rival. */
  heads_up?: boolean;
}

export interface AnswerResponse {
  is_correct: boolean;
  level: number;
  chosen_action: string;
  correct_action: string;
  correct_followup?: string | null;
  explanation: string;
  response_ms: number;
  needs_level_2: boolean;
  next_level?: number | null;
  current_streak: number;
  session_total_hands: number;
  session_correct_hands: number;
  session_accuracy_pct: number;
  full_matrix?: Record<string, any> | null;
  actions_config?: Record<string, any> | null;
  followups_config?: Record<string, any> | null;
  table?: TableStateData | null;
  villain?: VillainReaction | null;
  next_actions?: ActionOption[] | null;
  /** True si la mesa es de 2 asientos: hero en una ciega y un solo rival. */
  heads_up?: boolean;
}

export interface SessionStatus {
  session_id: string;
  mode: string;
  started_at: string;
  ended_at?: string | null;
  scenario_ids: string[];
  total_hands: number;
  correct_hands: number;
  accuracy_pct: number;
  median_response_ms: number;
  correct_fast_pct: number;
  time_limit_seconds?: number | null;
  hand_limit?: number | null;
  remaining_time_seconds?: number | null;
  has_reached_time_limit: boolean;
  has_reached_hand_limit: boolean;
}

export interface StatsOverview {
  total_answers: number;
  total_correct: number;
  global_accuracy_pct: number;
  avg_response_ms: number;
  median_response_ms: number;
  correct_fast_pct: number;
  current_streak: number;
  best_streak: number;
  total_sessions: number;
}

export interface AccuracyPoint {
  date: string;
  accuracy_pct: number;
  avg_response_ms: number;
  total_hands: number;
}

export interface CategoryAccuracy {
  category: string;
  label: string;
  total_hands: number;
  correct_hands: number;
  accuracy_pct: number;
  avg_response_ms: number;
}

export interface HandHeatmapCell {
  hand: string;
  total_attempts: number;
  correct_attempts: number;
  accuracy_pct?: number | null;
  median_response_ms?: number | null;
  default_action: string;
  default_color: string;
}

export interface TopFailedHand {
  hand: string;
  scenario_id: string;
  scenario_name: string;
  position: string;
  stack_range: string;
  total_attempts: number;
  failures: number;
  accuracy_pct: number;
  correct_action: string;
  correct_followup?: string | null;
}
