# Proposed next feature: multiple regulations and temporal applicability

**Status: design for discussion, not implemented.** This describes a proposed information model and review workflow, not a legal determination or a claim about any particular regulation.

## Separate three questions

- **Identity:** Which instrument, version and provision does this text belong to?
- **Applicability:** Does the provision apply to the entity, jurisdiction, activity and assessment date?
- **Currency:** What authoritative source was checked, when was it checked, and how confident are we that relevant amendments or repeals have been captured?

An uploaded file's timestamp, content hash or user-entered version label answers none of these on its own. “Latest available”, “in force” and “applicable on the assessment date” must remain distinct states.

## Corpus ingestion and chunking

Ingest each document separately. Never concatenate all regulations and then split the resulting string. Assign an instrument ID and immutable version ID before chunking. Preserve source bytes and their hash separately from extracted text.

Parse articles, sections, annexes and definitions into structural parent nodes. Create child passages within those nodes when they exceed the token budget. A child carries its heading path, parent ID and source spans. Preserve requirements with conditions/exceptions where feasible, and represent cross-page/cross-article dependencies explicitly. Attach referenced definitions and exceptions during context assembly. Flag extraction failures and tables for review instead of silently flattening them.

Suggested metadata:

| Level | Proposed fields |
| --- | --- |
| Instrument | `instrument_id`, title, issuing authority, jurisdiction, instrument type, authoritative source URL |
| Version | `version_id`, source hash, publication date, source retrieval time, source URL, amendment/repeal relationships |
| Provision | `provision_id`, article/section path, applicability scope, effective and applicable intervals, transition rules, review state |
| Chunk | `chunk_id`, `instrument_id`, `version_id`, `provision_id`, parent ID, page/text spans, heading path, text hash, parser/chunker version |
| Verification | reviewer, checked time, evidence/source snapshot, verification method, unresolved issues |

Use composite/global IDs such as `instrument_id/version_id/provision_id/chunk_id` so one file's `R0001` cannot collide with another's. Keep a version-independent provision identity where a reviewed mapping exists; do not infer legal continuity from position alone.

## Temporal eligibility before retrieval

Make `assessment_date` explicit, along with jurisdiction and entity/activity scope. Store publication, entry into force, application and repeal dates separately. Provisions within one instrument may need different applicability intervals and transition conditions.

For a reviewed interval represented as `[applicable_from, applicable_to)`, use:

`applicable_from <= assessment_date < applicable_to`

The exclusive end convention is an internal storage choice. Transform dates from source language through reviewed rules rather than assuming all legal dates use that convention. Unknown dates, unsettled transition rules or unresolved scope produce **unknown**, not silently “current”. Future, historical, potentially applicable and confirmed applicable sources should remain distinguishable. Do not discard unknown candidates silently; route them to a separate review lane so missing metadata is visible.

Verify source currency using an authoritative publication/register and amendment/repeal records. Save what was checked and when. Re-check on a scheduled freshness policy or a detected source update. A source page's HTTP modification time is not an effective date. Automated extraction can propose metadata; ambiguous legal applicability needs domain review.

## Retrieval and evidence assembly

1. Resolve eligible versions/provisions for the date and scope, recording exclusions and unknowns.
2. Retrieve per claim over eligible chunks; compare lexical, hybrid and embedding approaches using a labeled set.
3. Expand selected children to necessary parent context, definitions, conditions and exceptions.
4. Deduplicate and enforce a measured context budget without silently suppressing competing relevant instruments.
5. Pass instrument identity, version and provision-level temporal state with every citation.
6. Validate quotations against the exact selected source version and show unresolved applicability clearly.

Relevance ranking alone must not decide which law takes precedence. Detect conflicting provisions, amendments and overlapping scopes; preserve the competing sources for review. Any future automated precedence rule needs an explicit reviewed basis.

## Evaluation before rollout

Use synthetic cases first: two files sharing local passage numbers; old/new versions; a future application date; a repealed provision; a provision with delayed application; an unknown date; a partial amendment; a cross-page exception; conflicting instruments; a historical assessment requiring an older version.

Measure temporal-filter false exclusions/inclusions, correct version selection, required-provision recall, preservation of conditions/exceptions, cross-version citation errors and downstream claim conclusions. Regression tests should keep the existing nine claims intact while new tests exercise corpus identity and date selection.

## Suggested implementation order

1. Agree the minimum metadata contract and explicit assessment date.
2. Add a document registry, immutable version records and globally unique source references.
3. Implement structure-preserving ingestion and manual temporal metadata with unknown states.
4. Add per-claim retrieval and version-aware citation checks.
5. Only then add authoritative-source update checks and assisted metadata extraction.

Decisions to discuss: intended jurisdictions/instrument types; where authoritative versions come from; whether the review asks about today or a historical reporting period; who confirms ambiguous applicability; and where the registry should live in the company platform.
