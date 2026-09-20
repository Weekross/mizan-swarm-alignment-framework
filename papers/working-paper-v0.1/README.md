# MĪZĀN — working paper v0.1

**Vasyl Perehinskyi · ORCID [0009-0004-7272-5286](https://orcid.org/0009-0004-7272-5286)**

> **Read the [2026-09-20 correction notice](CORRECTIONS.md) before citing this draft.** It corrects the attribution of M2 to Claude (according to the supplied critical report), clarifies evidence, and records open methodological work. The old MD/PDF/HTML have not yet been integrated into a revised manuscript. Content status: **research protocol draft**, not a validated alignment method.

## Manuscript

[Read the Ukrainian working paper v0.1](MSAF_Working_Paper_v0.1_UA.md).

English title: *MĪZĀN: From Qur’anic Principles to Testable Multi-Agent Governance*.

This is an unreviewed author draft, not a production security system, fatwa or tafsir. A complete English edition, fully specified B2, qualified source review and actual model evaluations remain unfinished.

## Actual checks and reproduction

[Public CI run with the 24 test results](https://github.com/Weekross/mizan-swarm-alignment-framework/actions/runs/35497184874).

The run completed successfully at commit `10486218c965935f2d616c6b5b62e32ceffb9384`. Its artifact contains per-test `run.json` and `unittest.log`. No LLM calls, full EVAL-01…05 runs or production-isolation tests were performed. Two tests cover a statistical helper and a zero denominator; these are not 24 independent security trials. CI execution is not independent expert review.

From the repository root:

```sh
python3 papers/working-paper-v0.1/reproduction/run_conformance.py \
  --reproduction papers/working-paper-v0.1/reproduction \
  --paper papers/working-paper-v0.1 \
  --out ci-evidence
```

Python standard library only. The runner records current environment, timestamps, source revision, outcomes and hashes. No hermetic container or invented digest is claimed. PDF/HTML are delivered separately and their absence in CI is explicitly recorded.

Historical local evidence remains at [validation.json](evidence/validation.json) and [unit-test-output.txt](evidence/unit-test-output.txt); it is not the new CI evidence.

The fixture signer is intentionally accessible to tests in the same process. Do not use this mock as a production security boundary. Broker authentication, process/network isolation, durable nonce storage, halt/revocation and an independent actual-effect oracle require further implementation.

## Version and citation boundaries

The working-paper version `0.1` is separate from framework release `v1.0.0` and planned development `v1.1.0`. No DOI has been assigned to this manuscript. `10.5281/zenodo.22846304` identifies the previous MSAF record, not this draft. No historical tag or archive was replaced.

[zenodo-working-paper.template.json](zenodo-working-paper.template.json) is a possible later deposit template, not an existing record. It must not replace root `.zenodo.json`. Review authorship, rights, metadata and files before depositing. Root `CITATION.cff` refers to the previous framework record.

## AI assistance and outstanding review

ChatGPT assisted the manuscript and code. According to the supplied critical report, Claude (Anthropic) generated the earlier critique, eval specification and subsequent paper critique. Neither constitutes independent human review. The exact scope of human author checking remains to be recorded; no expert approval is asserted.

Outstanding work: an executable B2 definition; factorial architecture/instruction controls and stronger baselines; gate conformance beyond hand-written examples; power analysis and preregistration; provenance/source fields for all 47 rules; integrated manuscript corrections; and author decisions on licensing and deposition. See [CORRECTIONS.md](CORRECTIONS.md).

The original supplied review is not republished here. No merge, new Release or DOI is implied by these draft-branch changes.
