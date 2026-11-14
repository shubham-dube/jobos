export type JobRow = {
  match_id: string; job_id: string; title: string; company: string; locations: string[]; countries: string[];
  remote_type: string; ats: string; url: string; apply_url: string; posted_at: string | null; status: string;
  score: number | null; reasons: string[]; gaps: string[]; eligibility: { eligible?: boolean; status?: string; reasons?: string[] };
  legitimacy: number | null; legitimacy_reasons: string[]; filter_reasons: string[]; seniority: string;
  salary: Record<string, unknown> | null; feedback: string; application: { id: string; state: string } | null;
  description?: string;
  documents?: DocSummary[];
};
export type DocSummary = {
  id: string; kind: string; label: string; filename: string; job_id: string | null; generator: string;
  reworded: number; rejected: number; pages: number | null;
};
export type DiffLine = {
  section: string; item_id: string; item_name: string; sources: string[]; source_text: string; final_text: string;
  status: "verbatim" | "reworded" | "kept_original"; reason: string;
};
export type DocDetail = DocSummary & {
  created_at: string;
  meta: {
    generator?: string; job_title?: string; company?: string; pages?: number; trimmed?: string[]; used_llm?: boolean;
    keywords?: string[]; diff?: DiffLine[];
    grounding?: { reworded: number; verbatim: number; rejected: number; dropped_items: string[]; dropped_skills: number; notes: string[] };
    variant?: { skills?: string[] };
    paragraphs?: string[]; dropped?: string[];
  };
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
    documents?: { resume: { document_id: string; filename: string; tailored: boolean; reworded: number; rejected: number }; cover_letter_id: string };
    match_score?: number;
    message?: string;
    url?: string;
  };
};
export type Stats = {
  applications: Record<string, number>; matches: Record<string, number>; open_interventions: number;
  open_jobs: number; llm_cost_24h: number; llm_cost_total: number; llm_budget_24h: number;
};
