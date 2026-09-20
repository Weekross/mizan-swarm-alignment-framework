# MSAF executable research slice — gate v0.3 / B2-QA v0.1

20 September 2026. Author/project lead: Vasyl Perehinskyi. Implemented with ChatGPT assistance after an AI-generated follow-up supplied by the author and attributed to Claude. This is code plus regression evidence, not an independently reviewed safety system.

## Run

Python 3.12+; standard library only. From repository root:

```sh
python experiments/v0_3/run_checks.py --out ci-evidence-v03 \
  --legacy papers/working-paper-v0.1/reproduction
```

In the standalone ZIP, use `--legacy legacy_baseline` instead. A nonzero exit indicates a failing baseline, undetected selected mutant, error, or failed protocol check. Mutation compile/import failures and timeouts are not counted as successful detection. Evidence includes all logs and exact mutant diffs.

## What is implemented

**Gate**: exact tenant/workflow/resource/action scope with separate rejection reasons; instance-owned monotonic clock; scoped approval challenge; two distinct authorized signing identities excluding requester; single-use nonce, expiry, revocation and halt; relevant resource version binding; serialized in-memory effects; attempted-call and execution quotas; bounded challenge registry and audit; redacted, sequenced, timestamped hash-chain audit and a checkpoint verifier.

**B2-QA**: a terminating state machine for closed-corpus multiple-choice evidence QA. Three context-isolated proposers followed by a support checker and a challenge checker. Checkers see all proposals and corpus, but never each other's reviews. A deterministic aggregator commits only when the eligible proposals support exactly one answer. Any malformed response is a protocol ERROR, not a successful UNKNOWN. All literal prompts and schemas are in this directory. These components are executable, not a prose-only B2 description.

**Controls**: B0 one agent; B1 three answers with strict majority; B2 as above; B3 three initial answers + one simultaneous-snapshot revision round + majority; B4 one answer + one verifier veto; B5 five independent-context answers + majority. B3 and B5 are local debate/self-consistency-inspired controls, not claimed faithful replications of published implementations. All six support none/neutral/quran framing and use the same output contract. The 18 cells are run with scripted providers in tests, not with LLMs.

## Exact B2 treatment

Version `B2-qa-v0.1`; no training, adaptive prompt changes, web tools, routing retries or candidate-dependent extra calls. Fixed call order `p1, p2, p3, support_checker, challenge_checker`. Implementation is synchronous; the first three contexts do not contain prior proposals. Context isolation is not statistical independence. Each checker must return exactly one verdict per proposal ID. ENTAILS requires resolvable spans. The runtime checks span boundaries, not semantic truth: entailment remains a fallible model judgment.

States: `INIT -> PROPOSE -> VERIFY -> AGGREGATE -> DONE`, with `ERROR` from any active state. For B3, `DEBATE` replaces VERIFY. B0/B1/B5 go directly to AGGREGATE. No cycles; no repair loop.

A proposal is eligible only if it commits to an option, has nonempty resolvable evidence and every applicable checker returns ENTAILS with its own resolvable spans. Zero eligible answer values: UNKNOWN. Multiple eligible answer values: UNCERTAIN. Exactly one: INFERRED. Deduplicate exact citation objects, not opinions. No DecisionScore, authority weights, manufactured probability or raw majority in B2. This conservative rule is a testable design choice, not a proven optimal rule. It can fail due to correlated checker errors or excessive abstention.

Fixed limits supplied to all cells: at most 6 calls, 180000 total input characters, 30000 output characters, 5000 per response; adapter receives 800 output-token cap; 20 seconds per command and 120-second episode deadline checked around calls. No artificial token padding. Actual character costs, runtime and adapter-reported usage are recorded. Provider adapters must implement their model's token limit; characters are not tokens. A command timeout controls the direct child process only. No remote provider integration, live model revision, tokenizer calibration or billed experiment has been run.

`none` means no EXTRA MSAF framing; task/schema/role instructions and any provider's normal safety remain. Q repeats the neutral requirements and adds named motivational references, not theological claims. N/Q length differs and is reported: this is not yet a purified causal estimate of religion alone. For empirical comparison, architecture contrasts keep framing fixed, framing contrasts keep architecture fixed. Full budget/power/model preregistration remains outstanding.

Use `run_episode.py --task task.json --fixture outputs.json --out episode.json`. An optional trusted adapter receives a JSON job on stdin and returns `{output, usage}` on stdout. No keys or API access are requested by this package. Task input permits only `id/question/options/documents`; oracle labels cannot be supplied as extra task fields. Documents have `id/text/origin`; origin is untrusted bibliographic context, not a correctness label. Citations use Unicode-code-point offsets, end-exclusive. Agents have no gate/admin tool in this QA slice.

## Scope of gate guarantees

The trusted constructor owns clock and keys. `execute()` has no `now` argument. Tests replace the clock only at construction. `time.monotonic_ns()` is not affected by wall-clock changes; its readings are not portable timestamps across reboot. Tokens are boot-bound. UTC in audit is informational; lifetime uses the monotonic clock.

The two approvers are synthetic distinct identities/keys, NOT proof that two independent humans approved. Two-person approval is a chosen R3 policy here, not a universal Qur'anic requirement. Real identity verification, UI consent, approver fatigue and collusion remain open.

Versions bind the directly affected resource, including ABA changes, rather than all state. This avoids unrelated invalidation in the single-resource mock. Multi-resource dependency closure is not implemented and must not be assumed.

Every admitted execute attempt is logged. Once audit capacity is exhausted, subsequent requests are rejected with `audit_full`, `audited=false` and a bounded suppressed counter; no unbounded log is appended. This is deliberately fail-closed, not resistance to denial of service. No rotation/export protocol is implemented. Administrative challenge errors are outside the agent-facing execute audit contract. Pending tokens, consumed nonces and effects are bounded by their respective limits. There is no real read-data return or network send, only observable mock effect records.

The hash chain detects changed/reordered/truncated events RELATIVE TO a separately retained checkpoint. This package has no durable independent checkpoint service; a compromised process can rewrite both log and checkpoint. Hashing is neither truth verification nor anonymity. No multi-process, distributed, crash-safe or external-RPC atomicity is claimed. Broker authentication, process isolation, persistent revocation, key custody, ingress byte limits and OS quotas are still assumptions or missing deployment work.

## Mutation evidence

The author's follow-up reports Claude's 24 manual mutations (13 killed / 11 survived). Those exact 24 mutated files were not supplied. `legacy_probe.py` independently constructs SIX specified probes against the frozen original hash; it does not claim to reproduce the 24-mutant tally.

`mutations.py` defines 18 exact, review-driven semantic mutations for the new gate. They include log removal, no-op lock, skipped scope checks, uncharged budgets, weakened approval quorum, no nonce consumption, disabled halt/revoke, missing state version, no audit time/link and ignored audit bound. This targeted set was selected after the review; it is not held-out, exhaustive mutation testing or an overall mutation score. Diffs, mutated-file hashes and individual failure logs are saved.

The two-thread test holds the first execution immediately before commit, observes the second trying to acquire the lock, then releases the first. It checks one actual mock effect and explicit replay rejection, not just the type of lock. A no-op lock permits two effects under the controlled schedule. Ten repeated checks are robustness repetitions, not ten independent security trials. General model checking and broader fuzz/property testing remain unfinished.

## Source and review provenance

This code supersedes the narrow mock design operationally; it does NOT rewrite the archived paper, its appendix hashes, v1.0.0 tag or Zenodo record. PR #5 remains for HUMAN review before merge. No human reviewer has yet been engaged by this package. The literal model label “Claude Sonnet 5” was reported by the user; exact revision/export remains unverified. AI-to-AI agreement is not expert sign-off.

Public review assignments belong in `REVIEW_HANDOFF.md`. Do not mark F-02/F-03 fully resolved: a concrete QA slice now exists, but real model adapters, validated data, external gate integration, preregistration and human method review are absent. The full 47-rule mapping is not validated by these tests.

## Primary technical references (implementation assumptions, not certifications)

- Python clock semantics: https://docs.python.org/3/library/time.html#time.monotonic_ns
- Python locks: https://docs.python.org/3/library/threading.html#lock-objects
- Mutation-testing terminology and surviving mutants: https://mutmut.readthedocs.io/en/latest/ (this package uses its own explicit regression runner, not mutmut)
- RFC 9162 log checkpoints/consistency: https://www.rfc-editor.org/rfc/rfc9162.html (our bounded hash chain does not implement Certificate Transparency)

The repository's existing licensing has not been changed. Separate executable-code licensing still needs the author's explicit decision.
