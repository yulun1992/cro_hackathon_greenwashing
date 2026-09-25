import type { Reference, VerificationClaim } from "./types";

const label = (text: string) => text.replaceAll("_", " ");

export default function VerificationDetails({
  value,
  inspect,
}: {
  value: VerificationClaim;
  inspect: (reference: Reference, kind: "disclosure" | "regulation") => void;
}) {
  const facts = value.facts;
  const judge = value.judge;
  return (
    <details className="verification-details">
      <summary>
        Evidence cross-check · {value.human_review_required ? "Human review needed" : "No flagged conflict"}
      </summary>
      {value.review_reasons.length > 0 && (
        <p className="verification-alert">{value.review_reasons.join(" · ")}</p>
      )}
      {facts ? (
        <>
          <p className="small">Fact alignment: <strong>{label(facts.status)}</strong>. Model extracted one focal comparison; quotation matching does not verify its meaning.</p>
          <div className="verification-scroll">
            <table className="verification-table">
              <thead><tr><th>Dimension</th><th>Claim</th><th>Disclosure</th><th>Check</th></tr></thead>
              <tbody>{facts.dimensions.map((d) => (
                <tr key={d.dimension}><th>{label(d.dimension)}</th><td>{d.claim ?? "—"}</td><td>{d.disclosure ?? "—"}</td><td>{label(d.status)}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <p className="small">Arithmetic: <strong>{label(facts.arithmetic.status)}</strong>
            {facts.arithmetic.reason ? ` · ${facts.arithmetic.reason}` : ""}</p>
          {facts.arithmetic.formula && (
            <p className="small">{facts.arithmetic.formula}: claim {facts.arithmetic.claimed_value}; calculated {facts.arithmetic.calculated_value}; tolerance {facts.arithmetic.absolute_tolerance}.</p>
          )}
          {facts.arithmetic.operands && Object.entries(facts.arithmetic.operands).map(([name, operand]) => (
            <button className="verification-source" key={name} type="button"
              onClick={() => operand.reference.id.startsWith("D") && inspect(operand.reference, "disclosure")}
              disabled={!operand.reference.id.startsWith("D")}
            >{name}: {operand.text} · {operand.reference.id} · {operand.reference.quote}</button>
          ))}
          {facts.note && <p className="small muted">Extraction note: {facts.note}</p>}
        </>
      ) : <p className="small muted">Fact extraction unavailable. No arithmetic was verified.</p>}
      {judge && (
        <div className="judge-result">
          <p className="small"><strong>LLM judge:</strong> claim/disclosure {label(judge.comparison_verdict)}; regulation {label(judge.regulation_verdict)}. This is a model opinion.</p>
          <p className="small">{judge.explanation}</p>
          {judge.issues.length > 0 && <p className="small">Issues: {judge.issues.map(label).join(", ")}</p>}
          {judge.warnings.map((warning, i) => <p className="small" key={i}>{warning}</p>)}
          {[...judge.disclosure_references.map((ref) => ({ ref, kind: "disclosure" as const })),
            ...judge.regulation_references.map((ref) => ({ ref, kind: "regulation" as const }))]
            .map(({ ref, kind }, i) => <button className="verification-source" type="button" key={`${ref.id}-${i}`} onClick={() => inspect(ref, kind)}>{ref.id}: {ref.quote}</button>)}
        </div>
      )}
    </details>
  );
}
