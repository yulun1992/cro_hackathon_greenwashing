"""Regenerate the three fictional cases and human-authored expected findings."""
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"


def expectation(status, tests, quote, explanation, question):
    return dict(status=status, test_types=tests, evidence_quote=quote,
                explanation=explanation, follow_up_question=question)


a1 = "Total Scope 1 and 2 emissions increased from 100,000 tCO2e in 2024 to 108,000 tCO2e in 2025. Emissions intensity per tonne of product decreased by 30% in the same period."
a2 = "In 2025, renewable electricity accounted for 60% of electricity consumed by all owned factories. The remaining 40% was non-renewable electricity."
a3 = "Our target is net zero emissions for owned operations by 2040. Net zero has not yet been achieved."
b1 = "Packaging recyclability assessments cover Europe, representing 60% of global packaging sales in 2025. No assessment is disclosed for the remaining markets."
b2 = "Product-level life-cycle emissions, residual emissions and neutralization evidence are not disclosed."
b3 = "Freshwater withdrawal in 2024 covers five European factories. The 2025 boundary covers eight factories across Europe and Asia. No restated 2024 figures are provided."
c1 = "Owned-facility Scope 1 and 2 emissions were 100,000 tCO2e in 2020 and 80,000 tCO2e in 2025. Organizational boundaries and calculation methods are unchanged."
c2 = "Of 1,000 tonnes of cardboard packaging purchased in Europe in 2025, 700 tonnes were recycled material. Recycled content was 70% by mass."
c3 = "The target is a 50% reduction in owned-facility Scope 1 and 2 emissions by 2030 against 2020. It remains a future target and has not been achieved."

cases = [
    dict(id="A", name="A · Verdant Manufacturing · Contradictions", synthetic=True,
         claims=["Our total Scope 1 and 2 greenhouse gas emissions fell by 30% in 2025 compared with 2024.",
                 "All electricity consumed by our owned factories in 2025 was renewable.",
                 "Our owned operations have already achieved net zero greenhouse gas emissions."],
         disclosure="Verdant Manufacturing — SYNTHETIC 2025 disclosure. Fictional company and figures.\n\n" + a1 + " Boundaries and methods are unchanged between years.\n\n" + a2 + " The figures cover all owned factories and the full year.\n\n" + a3,
         expected=[expectation("contradicted", ["numeric", "metric_basis", "time"], a1,
                               "A 30% intensity reduction is presented as an absolute emissions reduction. Total emissions actually rose by 8% on unchanged boundaries.",
                               "Will the company state that the reduction concerns intensity and disclose the absolute increase?"),
                   expectation("contradicted", ["numeric", "scope"], a2,
                               "The same factories and period are covered, but the renewable share is 60%, not 100%.",
                               "What supports describing the remaining 40% as renewable?"),
                   expectation("contradicted", ["time", "target_vs_actual"], a3,
                               "A future 2040 target is presented as an achievement, which the disclosure explicitly contradicts.",
                               "Can the claim distinguish the future target from current performance?")],
         numeric_facts=[dict(metric="Scope 1 + 2 absolute emissions", unit="tCO2e", baseline_year=2024, current_year=2025, baseline=100000, current=108000)]),
    dict(id="B", name="B · Blueleaf Consumer Goods · Evidence gaps", synthetic=True,
         claims=["Every package sold worldwide in 2025 was recyclable in its sales market.",
                 "Every Blueleaf product sold in 2025 was carbon neutral across its full life cycle.",
                 "Our global freshwater withdrawal fell by 25% in 2025 compared with 2024."],
         disclosure="Blueleaf Consumer Goods — SYNTHETIC 2025 disclosure. Fictional company and figures.\n\n" + b1 + " Assessed European packaging was recyclable in its sales markets.\n\nThe company publishes a corporate Scope 1 and 2 inventory. " + b2 + " This report does not determine whether products are carbon neutral.\n\n" + b3,
         expected=[expectation("insufficient_evidence", ["scope"], b1,
                               "Regional evidence covers 60% of global sales. Missing evidence for the other markets does not prove their packaging is non-recyclable.",
                               "Can the company provide assessments for the remaining 40% of packaging sales?"),
                   expectation("insufficient_evidence", ["scope", "metric_basis"], b2,
                               "A corporate inventory does not establish full-life-cycle carbon neutrality for every product. The supplied material does not establish whether the claim is true or false.",
                               "Where are the product life-cycle calculations and neutralization evidence?"),
                   expectation("not_comparable", ["scope", "time"], b3,
                               "The company and geographic boundaries changed. These figures cannot test a like-for-like global 25% reduction.",
                               "Can 2024 withdrawal be restated on the 2025 boundary?")], numeric_facts=[]),
    dict(id="C", name="C · Clearpath Components · Consistent statements", synthetic=True,
         claims=["Owned-facility Scope 1 and 2 emissions fell by 20% in 2025 compared with 2020, using unchanged boundaries and methods.",
                 "Recycled material accounted for 70% by mass of cardboard packaging purchased in Europe in 2025.",
                 "We aim to reduce owned-facility Scope 1 and 2 emissions by 50% by 2030 against 2020; this target has not yet been achieved."],
         disclosure="Clearpath Components — SYNTHETIC 2025 disclosure. Fictional company and figures.\n\n" + c1 + " Scope 3 is outside this specific metric.\n\n" + c2 + " This metric does not describe recyclability or other packaging materials or regions.\n\n" + c3 + " The current reduction against the baseline is 20%.",
         expected=[expectation("supported", ["numeric", "scope", "time"], c1,
                               "The claimed reduction, scope, years and methods align with the disclosure. This establishes consistency within the supplied material, not independent verification.",
                               "Can the underlying emissions inventory be independently reviewed?"),
                   expectation("supported", ["numeric", "scope", "metric_basis"], c2,
                               "The percentage, mass basis, material, geography and year align. Recycled content is not presented as recyclability.",
                               "Can supplier records substantiate the recycled material weights?"),
                   expectation("supported", ["time", "target_vs_actual"], c3,
                               "The statement accurately describes a future target and says it has not been achieved. This check does not establish feasibility of the target.",
                               "What milestones and financing support delivery of the target?")],
         numeric_facts=[dict(metric="Owned-facility Scope 1 + 2 emissions", unit="tCO2e", baseline_year=2020, current_year=2025, baseline=100000, current=80000)])
]

if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    (DATA / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in cases:
        (DATA / f"{case['id']}_claims.txt").write_text("\n".join(case["claims"]), encoding="utf-8")
        (DATA / f"{case['id']}_disclosure.txt").write_text(case["disclosure"], encoding="utf-8")
