# Project Review and Remediation Ledger

> Archived snapshot for `e193511`. For later findings and current verification, see [the follow-up review](project-review-2026-09-03-follow-up.md).

Review date: 2026-09-03  
Scope: the complete five-skill image/visualization repository at `e193511`
Baseline: five Agent Skills, the shared Python runtime, prompts/references, tests, diagnostics, installation documents, and GitHub workflows

## Review conclusion

The primary SenseNova generation and editing path is compact and covered by useful offline tests. The main risks are contradictory Agent instructions, review schemas that cannot enforce their advertised gates, and optional runtime branches whose behavior differs from the public CLI contract.

No production API request was made during the review.

## Findings and remediation status

| ID | Priority | Finding | Required outcome | Status |
|---|---|---|---|---|
| R01 | High | Infographic prompt expansion can add unsupported Pro-tips or Key Insights while another rule forbids new information. | Use one fact policy: presentation copy may be condensed, but every factual claim must come from the user. | Complete |
| R02 | High | Infographic review requires an overall score and factual assessment, but its prompt returns neither a score nor fact comparison fields. | Pass expected content into review and use a deterministic weighted scoring schema. | Complete |
| R03 | High | Image imitation review cannot enforce target-content accuracy or detect old-topic semantic residue. | Review the candidate against target content and the rewritten caption; make semantic residue a hard failure. | Complete |
| R04 | High | Image annotation asks the Agent to infer unlabeled chart values exactly from pixels. | Separate visible facts from estimates; never represent inferred values as exact. | Complete |
| R05 | High | Resume instructions both prohibit invention and require expansion; they also encourage fabricated portraits and unusable QR codes. | Permit faithful condensation/translation only; use supplied portraits or abstract anchors; omit unverified QR codes; retain the best verified candidate. | Complete |
| R06 | High | The VLM CLI advertises URL input, but the implementation treats every string as a local path; unknown image types can be mislabeled as PNG. | Support bounded local, Data URL, and HTTP(S) inputs and normalize non-PNG/JPEG formats correctly. | Complete |
| R07 | Medium | The Anthropic Messages adapter encodes the system prompt as a user message and omits an API version header. | Emit the Messages wire format explicitly and cover it with an offline contract test. | Complete |
| R08 | Medium | Several CLI options are silently ignored, and the OpenAI image backend ignores timeout/TLS flags. | Reject unsupported parameters and make supported parameters effective for every backend. | Complete |
| R09 | Medium | Optional image backends do not return the shared provenance fields or use the same save validation guarantees. | Normalize result metadata in the runner and validate saved image bytes. | Complete |
| R10 | Medium | Local/Data URL inputs and downloaded outputs have no explicit byte/pixel ceiling. | Enforce bounded image input and output at the shared image boundary. | Complete |
| R11 | Medium | Default output names can collide within one second, and requested file extensions can disagree with actual image format. | Use unique default names and format-consistent suffixes. | Complete |
| R12 | Medium | CI checks only PR titles; optional adapters and prompt contracts have no automated regression coverage. | Add cross-platform tests, lint, repository-scope checks, and targeted contract tests. | Complete |
| R13 | Medium | The installation Doctor rejects unrelated `sn-*` skills even though coexistence is valid in a host skill directory. | Check that required skills are present; keep exclusivity enforcement only in the repository-scope check. | Complete |
| R14 | Low | The unused package configuration references a missing README and a nonexistent module root; workflow actions are tag-pinned. | Remove the unused broken package declaration and pin workflow actions to immutable revisions. | Complete |

## Remediation evidence

| IDs | Evidence |
|---|---|
| R01-R02 | The infographic workflow now creates a fact ledger, prohibits unsupported enrichment, passes expected facts and labels into one candidate critic, and uses a deterministic weighted score plus hard red-line failures. |
| R03 | Caption rewrite now returns a semantic replacement ledger. A carry-over requires the user's exact quoted request plus a compatibility decision; intentional contradictions require a second exact quote. Missing or invalid evidence becomes both ledger error and semantic residue and cannot pass review. |
| R04 | Image annotation distinguishes exact visible labels from pixel-derived estimates and requires estimates to carry uncertainty or be omitted. |
| R05 | Resume generation permits only faithful condensation/reorganization/translation, uses a portrait only when supplied, omits QR codes, and retains the best fact-verified candidate rather than the last revision. |
| R06, R09-R11 | Shared image utilities now bound, validate, normalize, and atomically save inputs/outputs; URL and Data URL inputs work; supported WebP inputs normalize to PNG; output suffixes match encoded formats; generated default names include collision-resistant entropy. |
| R07 | The Anthropic adapter emits the system prompt at the top level and includes `anthropic-version`; an offline contract test covers both. |
| R08 | Unsupported legacy generation flags fail clearly, timeout/TLS settings reach all image clients, and runner-level result metadata is normalized. |
| R12 | A cross-platform Python 3.9/3.12 workflow runs unit tests, Ruff, and the repository-scope check; targeted prompt, adapter, input-boundary, output, and Doctor tests were added. |
| R13 | The Doctor verifies presence of the five required skills without rejecting unrelated installed skills; repository exclusivity remains a separate check. |
| R14 | The unused broken package declaration was removed, and all GitHub Actions references are pinned to immutable commit SHAs. |

## Baseline verification

- `python -m unittest discover`: 31 tests passed.
- Ruff: passed.
- Offline Doctor with a placeholder key: passed.
- Repository-scope check: passed.
- All five skills passed the skill validator with UTF-8 mode enabled.

## Completion rule

A finding is complete only when its implementation is present, a focused regression check covers the changed behavior where practical, the full offline suite passes, and this ledger records the final evidence.

## Final verification

- `python -m unittest discover`: 41 tests passed.
- Ruff: passed with no automatic fixes.
- Offline Doctor with a placeholder key: passed.
- Repository-scope check: passed.
- All five skills passed the skill validator with UTF-8 mode enabled.
- `git diff --check`: passed.
- No production API request was made during remediation.
