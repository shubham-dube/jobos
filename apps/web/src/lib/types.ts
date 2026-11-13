export type JobRow = {
  match_id: string; job_id: string; title: string; company: string; locations: string[]; countries: string[];
  remote_type: string; ats: string; url: string; apply_url: string; posted_at: string | null; status: string;
  score: number | null; reasons: string[]; gaps: string[]; eligibility: { eligible?: boolean; status?: string; reasons?: string[] };
  legitimacy: number | null; legitimacy_reasons: string[]; filter_reasons: string[]; seniority: string;
  salary: Record<string, unknown> | null; feedback: string; application: { id: string; state: string } | null;
  description?: string;
};
export type AppRow = {
  id: string; state: string; title: string; company: string; ats: string; apply_url: string; attempt: number;
  error: string; submitted_at: string | null; updated_at: string; gate: Record<string, unknown>;
};
export type Question = { key: string; label: string; type: string; options: string[]; reason?: string; suggestion?: unknown };
export type Intervention = {
  id: string; kind: string; title: string; status: string; application_id: string | null; created_at: string;
  expires_at: string | null; answer: Record<string, unknown> | null;
  payload: {
    job?: { title: string; company: string; url: string; id: string };
    questions?: Question[];
    pages?: { url: string; fields: { label: string; value: unknown; source: string; confidence: number }[] }[];
    gate?: { rule?: string; facts?: Record<string, unknown> };
    match_score?: number;
    message?: string;
    url?: string;
  };
};
export type Stats = {
  applications: Record<string, number>; matches: Record<string, number>; open_interventions: number;
  open_jobs: number; llm_cost_24h: number; llm_cost_total: number; llm_budget_24h: number;
};
