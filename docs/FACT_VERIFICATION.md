# Claim verification and the role of regulation

This optional Live AI layer adds auditable checks to the existing comparison. The original reviewer still produces its finding first. It is not overwritten when a later check disagrees.

## Two distinct questions

| Question | Source | What the result means |
| --- | --- | --- |
| Does the company claim match its own evidence? | Claim text and disclosure | Factual consistency, including metric, unit, reporting period, baseline, scope and actual versus target. |
| Does a supplied rule support a regulatory concern? | The provision, its conditions and the company material | A screening opinion about the supplied rule. It is not a legal determination. |

A regulation supplies a **criterion**, not evidence that a company emitted a particular amount. A factual contradiction can be found with no regulation; it does not alone establish a violation. A claim can match the disclosure yet still omit information required by an applicable rule. Every regulatory conclusion needs a quotation from the selected provision. Its mere presence in the file does not prove current legal force, jurisdictional applicability, semantic relevance or that exceptions were considered. The app handles one uploaded regulation at a time and does not verify currency.

## Execution

1. The original generation prompt produces comparison and regulatory screening findings from claims, all disclosure passages, and the selected regulation passages. Its original citation validator checks that referenced quotations occur in supplied passages.
2. With `verification=facts`, a separate model prompt receives **claims and disclosure only**, without the first review or regulation. It extracts one focal fact pair per claim: metric, unit, period, baseline period, scope, metric basis and actual/target nature. Each side cites its own source. It may return null or describe a compound claim that cannot be represented.
3. Python validates the citation IDs and exact quotation substrings. It records dimension differences and computes an explicit level, relative percent change or percentage-point change only if the necessary fields align. Numeric literals, unit labels and period labels must appear in each side's cited quotations; semantic interpretations still need review. Arithmetic uses `Decimal`. A percent-change comparison allows 0.1 percentage points of rounding; a level comparison uses exact values. Scaled, approximate, ranged or implied numbers, missing baselines and unsupported conversions are not calculated.
4. With `verification=facts_and_judge`, a third model call receives the first findings, fact checks and original selected sources. Its rubric asks separately whether the claim/disclosure inference and regulatory inference are supported. Its `agree`, `disagree` or `uncertain` opinions are recorded next to the original result. Comparison quotations must resolve to disclosure (`D`) passages; regulatory quotations to selected regulation (`R`) passages. No supplied regulation yields `not_assessed`.
5. A conflict, incomplete fact check, uncomputed arithmetic or unavailable stage sets `human_review_required` with reasons. A failed optional call leaves the first finding intact and adds a sanitized warning. The HTML, JSON and web view display the stages independently.

For example, the claim “absolute emissions decreased 30% in 2025 from 2024” and disclosure “2024: 100 tCO2e; 2025: 108 tCO2e” give a conditional change of `(108 / 100 - 1) × 100 = +8%`. That differs from a claimed −30%. A claim about *emissions intensity* would be a different metric basis, so the arithmetic comparison should be skipped. In both cases, a reviewer must verify the extracted context and any material outside the selected passages.

## Use and limits

The original Live AI call uses `verification=none` by default in Python/API/CLI, preserving existing callers. The web UI defaults to `facts` when Live AI is selected. `facts` attempts two model calls total; `facts_and_judge` attempts three. Choose the optional mode through the web selector, CLI `--verification`, API multipart `verification`, or modular notebook dropdown. Offline demo has no verification calls; the archived `mvp_demo/` remains unchanged. Approved custom generators need `extract_facts(context, language)` and, for the judge, `judge(context, findings, fact_checks, language)` in addition to `generate`.

Exact quote matching is **not** proof that the model extracted the right meaning or associated a number with the right year, metric or unit. The arithmetic result is explicitly conditional on those premises and covers only one focal comparison per claim. The judge is another opinion from the configured model and can repeat its biases; it does not establish ground truth. The feature does not resolve jurisdiction, effective date, exceptions, or conflicts across multiple regulations. Treat flagged and unflagged findings as review aids rather than compliance certificates.
