# MSAF v1.0.0 — proposed erratum and scope clarification

Date: 2026-09-20. Status: proposed correction, pending maintainer review and merge. Prepared with ChatGPT assistance following AI-assisted critical reports attributed to Claude (Anthropic). This is not independent human peer review.

## Meaning of the initial release

The initial v1.0.0 is a **conceptual framework/research preview**. It does not establish model-value alignment, AGI/ASI safety, validated swarm performance, or production security. A DOI and a version number identify a publication; they do not themselves establish peer review or empirical validity.

The historical project title and tags remain recorded for attribution and reproducibility. They must not be interpreted as a demonstrated AGI/ASI result.

## Specific corrections

1. **DecisionScore:** the undefined multiplicative-minus-penalties expression in `docs/framework/00-overview.md` is withdrawn as a recommended algorithm. Scales, dependence, missing values and calibration were not specified. No validated replacement algorithm is claimed.
2. **Hard constraints:** YAML booleans and system-prompt instructions are declarations, not proof of runtime enforcement. Each requirement needs a specified mechanism, assumptions, test and assurance level. Preferences such as `rollback_preferred` are not unconditional invariants.
3. **Training curriculum:** the original section is an outline of topics, not a completed training procedure. No training data, optimization or model results were supplied with the initial release.
4. **Evals:** the 15 labels are proposed evaluation concepts, not measured benchmarks. Five later protocols and their numerical thresholds remain drafts. Nineteen nominal links in a review table do not mean 19 rules are validated.
5. **Qur'anic mappings:** the mappings are interpretive motivations, not technical proofs. In particular, 6:116 is not a theorem about majority aggregation. No completed qualified theological review of all 47 mappings is claimed.
6. **Software classification:** the main contribution of the initial publication is text. Its bibliographic type and keywords require an author-approved correction in Zenodo/ORCID as appropriate. This file does not modify those services or grant a new license. Existing license boundaries remain in force pending an explicit author decision.
7. **AI assistance:** ChatGPT assisted the framework, drafts, code and tool checks. According to the supplied critical report, Claude generated the earlier critique, eval specification and working-paper critique. Both partially review their own contributions. No human expert endorsement is implied.

## Later work and evidence

The working-paper draft is in [PR #4](https://github.com/Weekross/mizan-swarm-alignment-framework/pull/4), targeting `develop/v1.1`, not a new published release. It contains the mock source, 24 tests and a correction notice. The [public conformance run](https://github.com/Weekross/mizan-swarm-alignment-framework/actions/runs/35497184874) passed 24 existing unit tests. That does not validate B2 or the five planned LLM evaluations, and it does not add evidence retroactively to the original archived release.

Before a new empirical claim: define executable B2, separate architecture/instructions/budget effects, compare stronger baselines, assess gate bypasses and human approval risks, run a preregistered study, and obtain appropriate human review.

## Preservation of history

Do not delete or silently move the v1.0.0 tag or replace archived files. Link this erratum from current documentation, add an explicit metadata note to the existing record if authorized, and use a new documented version for changed publication files. A correction in this repository is not proof that Zenodo metadata were already edited.

The proposed amendment does not close the outstanding research tasks in issue #3. Publication bookkeeping in issue #1 may be separated from those tasks rather than marking unfinished review as complete.
