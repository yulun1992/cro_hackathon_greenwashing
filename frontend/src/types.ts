export type Case = {
  id: string;
  name: string;
  claims: string[];
  disclosure: string;
};
export type Status =
  "supported" | "contradicted" | "insufficient_evidence" | "not_comparable";
export type Passage = { id: string; text: string; location: string };
export type Reference = {
  id: string;
  quote: string;
  location: string;
  quote_verified: boolean;
  candidate_only?: boolean;
};
export type Finding = {
  claim_id: string;
  claim: string;
  status: Status;
  test_types: string[];
  explanation: string;
  evidence: Reference[];
  regulation_references: Reference[];
  candidate_regulation_passages?: Reference[];
  regulation_status: string;
  regulation_explanation: string;
  follow_up_question: string;
  verification?: VerificationClaim;
};
export type Fact = {
  metric: string | null;
  unit: string | null;
  period: string | null;
  baseline_period: string | null;
  scope: string | null;
  metric_basis: string | null;
  nature: string | null;
  references: Reference[];
  quote_verified: boolean;
  extraction_semantics_verified: false;
};
export type FactCheck = {
  status: "aligned" | "not_aligned" | "incomplete" | "unverified";
  dimensions: { dimension: string; claim: string | null; disclosure: string | null; status: string }[];
  claim_fact: Fact | null;
  disclosure_fact: Fact | null;
  arithmetic: {
    status: "match" | "mismatch" | "not_computed";
    reason?: string;
    formula?: string;
    claimed_value?: string;
    calculated_value?: string;
    absolute_tolerance?: string;
    operands?: Record<string, { text: string; reference: Reference }>;
  };
  note: string;
};
export type JudgeReview = {
  status: "agree" | "needs_review" | "uncertain";
  comparison_verdict: string;
  regulation_verdict: string;
  issues: string[];
  explanation: string;
  disclosure_references: Reference[];
  regulation_references: Reference[];
  warnings: string[];
};
export type VerificationClaim = {
  claim_id: string;
  facts?: FactCheck;
  judge?: JudgeReview;
  human_review_required: boolean;
  review_reasons: string[];
};
export type Report = {
  generated_at_utc: string;
  mode: string;
  model: string | null;
  summary: Record<Status, number>;
  findings: Finding[];
  numeric_checks: {
    metric: string;
    baseline: number;
    current: number;
    unit: string;
    calculated_change_pct: number;
  }[];
  warnings: string[];
  limitations: string[];
  input_fingerprint: string;
  verification?: {
    mode: string;
    stages: { fact_extraction: string; judge: string };
    expected_model_calls: number;
    limitations: string[];
    claims: VerificationClaim[];
  };
  regulation: {
    filename: string;
    version: string;
    sha256: string;
    latest_version_verified: boolean;
  } | null;
  regulation_passages_sent: number;
  regulation_total_passages: number;
};
export type Result = {
  report: Report;
  sources: { disclosure: Passage[]; regulation: Passage[] };
};
export type Config = {
  live_available: boolean;
  max_file_bytes: number;
  max_disclosure_chars: number;
  max_claims: number;
};
