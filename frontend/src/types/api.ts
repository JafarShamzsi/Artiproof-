/**
 * Shapes returned by the ArtiProof backend. These mirror the Pydantic
 * response models in `backend/app/schemas/` and the breakdown JSON shapes
 * in `backend/app/schemas/breakdown.py`.
 *
 * If you change a shape here, also change it in the backend and bump
 * FORMULA_VERSION on breakdowns.
 */

// ─── Shared breakdown shapes (mirror backend/app/schemas/breakdown.py) ───

export interface Deduction {
  reason: string;
  impact: number;
  detail?: Record<string, unknown>;
}

export interface ScoreBreakdown {
  base: number;
  deductions: Deduction[];
  warnings: string[];
  final: number;
  confidence?: number;
  formula_version: string;
}

export interface IntegrityAdjustment {
  reason: string;
  impact: number;
  detail?: Record<string, unknown>;
}

export interface IntegrityBreakdown {
  base: number;
  adjustments: IntegrityAdjustment[];
  warnings: string[];
  final: number;
  confidence?: number;
  formula_version: string;
}

export interface ProcessingWarning {
  type: string;
  module?: string;
  [key: string]: unknown;
}

export interface ModelMetadata {
  model_provider: string;
  model_name: string;
  apis_used: string[];
  fallback_used: boolean;
  processing_warnings: ProcessingWarning[];
  timestamp: string;
  formula_version: string;
  context: Record<string, unknown>;
}

// ─── Source check ───

export type CheckStatus = "pending" | "processing" | "completed" | "failed";

export type ClaimVerdict =
  | "true"
  | "false"
  | "misleading"
  | "unverified"
  | "partially_true";

export interface ClaimAnalysis {
  id: string;
  claim_text: string;
  verdict: ClaimVerdict;
  confidence: number;
  explanation: string;
  true_version: string | null;
  sources: Array<{ name?: string; url?: string }> | null;
  origin_trace: Record<string, unknown> | null;
  position_in_text: { start: number; end: number } | null;
}

export interface AIDetectionResult {
  id: string;
  paragraph_index: number;
  paragraph_text: string;
  ai_probability: number;
  detection_method: string;
}

export interface CitationCheck {
  id: string;
  original_citation: string;
  citation_url: string | null;
  is_accessible: boolean;
  is_retracted: boolean;
  credibility_score: number | null;
  issues: string[] | null;
  suggested_alternative: string | null;
}

export interface SourceCheck {
  id: string;
  user_id: string;
  input_type: "url" | "text" | "document";
  input_content: string;
  input_title: string | null;
  status: CheckStatus;
  overall_credibility_score: number | null;
  ai_content_percentage: number | null;
  misinfo_claims_found: number | null;
  has_pdf: boolean;
  has_annotated_pdf: boolean;
  created_at: string;
  completed_at: string | null;
  claims: ClaimAnalysis[];
  ai_detections: AIDetectionResult[];
  citations: CitationCheck[];
  score_breakdown?: ScoreBreakdown | null;
  model_metadata?: ModelMetadata | null;
}

export interface SourceCheckListItem {
  id: string;
  input_type: string;
  input_title: string | null;
  status: CheckStatus;
  overall_credibility_score: number | null;
  ai_content_percentage: number | null;
  misinfo_claims_found: number | null;
  created_at: string;
}

export interface SourceCheckListResponse {
  items: SourceCheckListItem[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Researcher ───

export interface PublicationAnalysis {
  id: string;
  title: string;
  journal: string | null;
  year: number | null;
  doi: string | null;
  citation_count: number;
  suspicious_citations: number;
  topic_match_score: number | null;
  is_self_cited_heavily: boolean;
  flags: string[] | null;
}

export interface CitationGraphNode {
  id: string;
  name: string;
  type: "target" | "citer";
  citation_count: number;
}

export interface CitationGraphEdge {
  source: string;
  target: string;
  weight: number;
  papers: string[];
}

export interface CitationRingFlags {
  rings: Array<{
    members: Array<{ id: string; name: string; citations_to_target: number }>;
    total_mutual_citations: number;
    confidence: number;
  }>;
  suspicious_pairs: Array<{
    author_id: string;
    author_name: string;
    citation_count: number;
    papers_cited: string[];
  }>;
  flags: string[];
  graph?: { nodes: CitationGraphNode[]; edges: CitationGraphEdge[] };
}

export interface ResearcherProfile {
  id: string;
  researcher_name: string;
  scopus_id: string | null;
  google_scholar_id: string | null;
  orcid: string | null;
  institution: string | null;
  official_h_index: number | null;
  official_citation_count: number | null;
  adjusted_h_index: number | null;
  adjusted_citation_count: number | null;
  integrity_score: number | null;
  self_citation_rate: number | null;
  citation_ring_flags: CitationRingFlags | null;
  topic_relevance_score: number | null;
  analysis_status: string;
  last_analyzed_at: string | null;
  created_at: string;
  publications: PublicationAnalysis[];
  integrity_breakdown?: IntegrityBreakdown | null;
  model_metadata?: ModelMetadata | null;
}

export interface ResearcherListItem {
  id: string;
  researcher_name: string;
  institution: string | null;
  integrity_score: number | null;
  analysis_status: string;
  created_at: string;
}

export interface ResearcherListResponse {
  items: ResearcherListItem[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Reports ───

export interface Report {
  id: string;
  user_id: string;
  source_check_id: string | null;
  researcher_profile_id: string | null;
  report_type: "source_verification" | "researcher_integrity";
  title: string;
  summary: string | null;
  pdf_path: string | null;
  share_token: string;
  created_at: string;
}

// ─── SSE pipeline events ───

export interface ProgressEvent {
  step: string;
  status: "processing" | "done" | "error" | "warning" | "completed" | "failed";
  detail: string;
  progress: number;
}
