# MĪZĀN Swarm Alignment Framework (MSAF)

**Research preview — Qur’an-inspired multi-agent governance and runtime assurance**

**Original author:** Vasyl Perehinskyi  
**ORCID:** [0009-0004-7272-5286](https://orcid.org/0009-0004-7272-5286)

## Working paper

**[MĪZĀN: від коранічних принципів до перевірюваного управління мультиагентними системами](papers/working-paper-v0.1/MSAF_Working_Paper_v0.1_UA.md)**

English title: *MĪZĀN: From Qur’anic Principles to Testable Multi-Agent Governance*.

This branch contains **working paper draft v0.1**. It is an unreviewed research proposal, not a demonstrated method for aligning model values or guaranteeing AGI/ASI safety. It distinguishes normative motivation, engineering proposals, candidate runtime constraints and actual evidence.

The paper withdraws the old undefined `DecisionScore` as a recommended algorithm and does not treat YAML booleans or system-prompt instructions as enforced invariants. Historical framework chapters remain available below; the paper explicitly discusses their limitations rather than silently rewriting the published snapshot.

### Evidence status

24 deterministic local mock unit tests passed; no LLM calls or full EVAL-01…05 runs were performed. No production isolation or completed independent theological/security review is claimed. These are not 24 independent security episodes. See the [reproduction materials and validation record](papers/working-paper-v0.1/README.md).

## Historical framework record

**Published framework version:** v1.0.0 (2026)  
**Previous record identifier:** [10.5281/zenodo.22846304](https://doi.org/10.5281/zenodo.22846304)

[![Historical MSAF DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22846304.svg)](https://doi.org/10.5281/zenodo.22846304)

This identifier belongs to the previous MSAF record, **not** to the new working paper. No manuscript DOI has been assigned. The root `CITATION.cff` and `.zenodo.json` describe the earlier framework; do not use them to claim the paper was already deposited. Published tags and archived versions are not modified by this branch.

## Core themes

Epistemic humility, evidence and tabayyun; consultation and dependence-aware reasoning; amanah-based permissions; privacy, auditability, resource limits, reversibility and human agency. Qur’anic anchors, contextual interpretation and engineering analogy remain distinct. The project is not a fatwa or tafsīr.

## Project files

- [`MSAF.md`](MSAF.md) — index of historical framework chapters.
- [`index.html`](index.html) — existing GitHub Pages landing page, not the full new paper.
- [`papers/working-paper-v0.1/`](papers/working-paper-v0.1/) — manuscript, reproduction code, test evidence and draft deposit metadata.
- [`AUTHORS.md`](AUTHORS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CHANGELOG.md`](CHANGELOG.md), [`ROADMAP.md`](ROADMAP.md) — project records and development guidance.

## Machine-readable development

- `schema/msaf-invariant.schema.json` — schema for one candidate rule.
- `schema/msaf-eval.schema.json` — schema for one proposed evaluation.
- `data/invariants.v1.0.0.json` — structured representation of 47 historical rules.
- `data/evals.v1.0.0.json` — 15 initial evaluation definitions, not experimental results.

The `analogy_level` classifications are draft interpretations. JSON structure alone does not validate a religious mapping, enforce a runtime property or establish benchmark performance.

## License and review

Existing documentation remains under CC BY-SA 4.0 unless otherwise stated. No silent change to the repository license is made here. The boundaries and license for a separate executable-software release still require an author decision.

AI assistance is disclosed in the paper. Qualified source review, independent technical review, an English edition and actual preregistered model experiments remain open work.

**الله أعلم — Allah knows best.**
