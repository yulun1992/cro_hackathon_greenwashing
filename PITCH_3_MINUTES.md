# Three-minute pitch

建议：英文讲解，屏幕只显示结果区，不展示代码。预先跑好 A 和 C，并保留 B。若展示 live 模式，提前完成一次实际 Azure 调用并导出结果；若使用预置结果，明确称为 authored demonstration。不要让现场等待 API 占掉三分钟。

## 0:00–0:30 · Problem

“A company says its emissions fell by thirty percent. Its sustainability report says something more specific: emissions intensity fell by thirty percent, while total emissions increased.

For a risk reviewer, the challenge is finding that mismatch, identifying the evidence, and knowing what to ask next. Our prototype helps make that review faster and more traceable.”

## 0:30–1:15 · Comparison and testing

操作：打开 A，停在第一条结果，指出两边原文和 8% 的计算。

“We compare each green claim with the supporting disclosure. We test five dimensions: numbers, time periods, scope, metric definitions, and future targets versus achieved results.

Here, the claim describes an absolute reduction. The report describes an intensity reduction, and absolute emissions move from one hundred thousand to one hundred and eight thousand tonnes. Python calculates the eight-percent increase from our synthetic source figures.

The reviewer gets the discrepancy, the exact evidence, and a concrete follow-up question.”

## 1:15–1:55 · Regulation and traceability

操作：如果已完成真实 AI 分析，展开上传法规的引用。否则明确说明展示的是虚构标准候选片段。

“The reviewer can upload the regulation they want to use. The live model links its assessment to quoted passages from that file. We preserve the filename, version label and page or paragraph reference.

The application checks that quoted text actually exists in the supplied source. If a citation fails validation, the conclusion is downgraded. We do not independently verify that the uploaded version is current, and a valid quote still needs review for legal applicability.”

## 1:55–2:25 · Avoiding false accusations

操作：切换到 C；有时间再展示 B 的证据不足标签。

“A useful screening tool should not flag every company. This second example is consistent with its disclosure. Where evidence is missing, we say insufficient evidence. Where boundaries differ, we say not comparable.

That distinction matters: absence of evidence is not proof of greenwashing.”

## 2:25–3:00 · Delivery and next step

“The prototype runs inside a Databricks notebook and connects to an existing Azure OpenAI endpoint. It needs no separate application deployment.

Today we demonstrate the workflow with three fictional companies and nine claims. We have tested the software's citation checks and request handling; we have not established real-world detection accuracy.

The next step is a small set of real, permissioned cases labeled by CRO reviewers, to measure missed issues, false flags and review time. The intended outcome is evidence-backed review support, with the final decision remaining with the reviewer.”

## 现场备用回答

**Is this just a prompt?**

“The model does the language comparison. The application adds a consistent claim-level schema, document/version traceability, quote validation, explicit abstention and a review workflow. The next validation question is whether that reduces reviewer effort on real cases.”

**Why not build a full RAG pipeline?**

“For short documents, we pass the material directly. Long regulations use a transparent keyword shortlist in this prototype. A production version would need better retrieval and tests for missed provisions, definitions and exceptions.”

**Is the demo regulation real law?**

“No. The bundled standard is fictional and clearly labeled. Live analysis can use a reviewer-uploaded regulation, but applicability and version currency still need confirmation.”

**What do the automated tests prove?**

“They verify the software behavior, such as rejecting fabricated quotes and preserving source references. They do not establish the model's real-world greenwashing detection accuracy.”
