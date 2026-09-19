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
