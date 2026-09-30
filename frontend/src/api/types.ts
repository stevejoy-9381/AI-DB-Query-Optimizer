/**
 * frontend/src/api/types.ts
 * TypeScript interfaces matching api/schemas.py Pydantic models.
 */

export interface QueryRequest {
  query: string;
}

export interface SimulateIndexRequest {
  query: string;
  index: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface SampleQueryItem {
  query: string;
  description: string;
  category: string;
}

export interface ScoreBreakdownItem {
  code: string;
  label: string;
  delta: number;
  severity: string;
  explanation: string;
}

export interface ScoreResponse {
  score: number;
  cost_estimate: string;
  complexity: string;
  rows_scanned_estimate: string;
  table_multiplier: number;
  breakdown: ScoreBreakdownItem[];
}

export interface AnalyzeResponse {
  query: string;
  query_type: string;
  statement_type: string;
  complexity: string;
  issues: Array<{
    code?: string;
    message?: string;
    severity?: string;
    [key: string]: any;
  }>;
  warnings: Array<{
    code?: string;
    message?: string;
    severity?: string;
    [key: string]: any;
  }>;
  filter_columns: string[];
  join_count: number;
  subquery_count: number;
  has_aggregation: boolean;
  has_group_by: boolean;
  has_order_by: boolean;
  has_limit: boolean;
  has_distinct: boolean;
  select_star: boolean;
  has_where: boolean;
  analysis_engine: string;
  score?: ScoreResponse;
}

export interface OptimizeResponse {
  query: string;
  optimizations: Array<{
    title: string;
    priority: string;
    description: string;
    example?: string;
    [key: string]: any;
  }>;
  insight: string;
}

export interface RecommendationItem {
  index_name?: string;
  index_type?: string;
  table?: string;
  columns?: string[];
  ddl: string;
  reason: string;
  estimated_improvement?: string;
  priority?: string;
  estimated_size?: string;
  trade_offs?: string;
  [key: string]: any;
}

export interface RecommendationsResponse {
  query: string;
  count: number;
  recommendations: RecommendationItem[];
}

export interface RewriteResponse {
  original: string;
  rewritten: string;
  is_changed: boolean;
  changes: string[];
  rewrite_score_est: number;
  validation: {
    is_valid_sql?: boolean;
    level?: string;
    badge_color?: string;
    message?: string;
    details?: string[];
    [key: string]: any;
  };
  supported: boolean;
}

export interface PlanNode {
  node_type: string;
  description: string;
  estimated_rows: number;
  startup_cost: number;
  total_cost: number;
  icon: string;
  table?: string;
  access_type?: string;
  possible_keys?: string[];
  key_used?: string | null;
  filtered_pct?: number;
  extra?: string[];
  children?: PlanNode[];
  cost_label?: string;
  [key: string]: any;
}

export interface ExecutionPlanResponse {
  query: string;
  plan_root: PlanNode;
  flattened_nodes: Array<{
    node_type: string;
    description: string;
    estimated_rows: number;
    total_cost: number;
    depth: number;
    table?: string;
    access_type?: string;
    [key: string]: any;
  }>;
  summary: {
    max_depth?: number;
    total_cost?: number;
    total_nodes?: number;
    estimated_rows?: number;
    has_full_scan?: boolean;
    has_filesort?: boolean;
    has_temporary?: boolean;
    [key: string]: any;
  };
}

export interface SimulateIndexResponse {
  query: string;
  index: string;
  simulation: {
    before_score: number;
    after_score: number;
    score_improvement: number;
    before_cost: string;
    after_cost: string;
    before_rows: number;
    after_rows: number;
    rows_reduction_pct: number;
    before_time_ms: number;
    after_time_ms: number;
    speedup_factor: number;
    speedup_label: string;
    impact_level: string;
    [key: string]: any;
  };
}

export interface ApiError {
  error: string;
  detail?: any;
}
