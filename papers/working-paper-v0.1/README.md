# MĪZĀN — working paper v0.1

**Vasyl Perehinskyi · ORCID [0009-0004-7272-5286](https://orcid.org/0009-0004-7272-5286)**

## Manuscript

[Read the complete Ukrainian working paper](MSAF_Working_Paper_v0.1_UA.md).

English title: *MĪZĀN: From Qur’anic Principles to Testable Multi-Agent Governance*.

This is an unreviewed author draft, not a validated alignment method, a production security system, a fatwa or a tafsir. The complete English edition is not yet prepared. The paper separates normative motivation, proposed runtime mechanisms, planned evaluations and actual local test results.

## Actual results and reproduction

24 local deterministic unit tests passed. No LLM calls, full EVAL-01…05 runs, production-isolation tests or completed independent peer review are claimed. Two tests cover a statistical helper and a zero denominator; these are not 24 independent security trials.

From this directory:

```sh
cd reproduction
PYTHONPATH=prototype python -m unittest discover -s tests -v
```

Python standard library only; the actual tested environment and hashes are in [validation.json](evidence/validation.json). Full local output: [unit-test-output.txt](evidence/unit-test-output.txt).

The fixture key and signer are intentionally accessible to the tests in the same process. Do not use this mock as a production security boundary. Assumed broker authentication, isolated execution, durable nonce storage and an independent actual-effect oracle require further implementation.

## Version and citation boundaries

The working-paper version `0.1` is separate from the historical MSAF release `v1.0.0` and the planned framework version `v1.1.0`.

No DOI has been assigned to this manuscript. `10.5281/zenodo.22846304` identifies the previous MSAF record; it must not be copied into the manuscript's own DOI field. Existing tags, releases and the historical archive have not been replaced.

[zenodo-working-paper.template.json](zenodo-working-paper.template.json) is a template for a possible later deposit using `publication` / `workingpaper`. It does not create or edit a Zenodo record and must not replace the repository-root `.zenodo.json`. Confirm author approval, publication date, rights, metadata and uploaded files before publishing. The root CFF still refers to the previous framework record.

## Outstanding review

- Author approval of scope, contribution and AI-assistance disclosure.
- Qualified review of contextual Quranic mappings; a full 47-rule source audit is not complete.
- Independent technical review and actual external-proxy experiments.
- Selection of models, datasets, budgets, oracle and preregistered analysis.
- Confirmation of external-review attribution and code-license boundaries before a separate software release.

The original externally supplied eval-review file is not republished here. Its fingerprint and use are described in the manuscript. ChatGPT assistance is disclosed and is not presented as independent peer review.

The standalone PDF/HTML reading editions are delivered separately. This branch contains the source manuscript and reproduction materials; no merge, new Release or new DOI is implied.
