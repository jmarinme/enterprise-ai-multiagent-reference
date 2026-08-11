# Sprint 09 Validation

## PBI-09-01 — requirement-by-requirement mapping

| # | Requirement | Implementation | Test evidence |
|---|---|---|---|
| 1 | Global conversation memory across all agents | `src/agents/shared/memory.py` (`ConversationMemory`, 15 fields incl. `reference_numbers`, `conversation_summary`) | `tests/unit/agents/shared/test_memory.py` |
| 2 | Slot filling: memory → tool output → entity resolution → ask | `_prefill_from_memory` in `claims_agent.py`/`broker_agent.py`/`commercial_intake_agent.py`, applied before each Agent's own tool-backed workflow | `test_broker_resolved_policy_number_is_reused_by_claims_without_re_asking`, `test_claims_broker_claims_switch_preserves_both_domains_and_resolves_broker_in_one_turn` |
| 3 | Entity resolution (Broker Name→ID, Policy→Customer→Broker, Customer→Policies) | Reuses existing Tools only (`broker_lookup`, `policy_lookup`'s `holder_name`, `customer_lookup`'s `policies`) — memory now carries the *result* forward so it is never re-resolved twice | `test_customer_only_discovery_is_reused_by_commercial_intake`, `test_claims_broker_claims_switch_...` |
| 4 | Natural-language extraction ("ayer", "la semana pasada", "llovió", "se inundó", "en mi casa") | `resolve_relative_date` (nlu.py) extended; `_LOSS_TYPE_KEYWORDS` (claims/extraction.py) extended; "se inundó"/"en mi casa" already worked (pre-existing `inund`/location-phrase extraction) | `tests/unit/agents/shared/test_nlu.py::test_resolve_relative_date_la_semana_pasada`/`_last_week`, `tests/unit/agents/claims/test_extraction.py::test_extracts_weather_loss_type_from_llovio`/`_lluvia_alone`, `test_natural_relative_week_and_weather_phrasing_are_understood_without_structured_input` |
| 5 | Question prioritization (highest-priority missing field first, no redundant multi-question) | Memory pre-fill removes already-known identifiers from ever being asked at all — see D-05 in `decisions.md` for why the existing grouped-question UX itself is preserved | Covered by requirement 2's tests (no re-ask observed) |
| 6 | Conversation summarization (checkmark format) | `src/agents/shared/summary.py::build_progress_summary`, invoked from `claims_agent.py::_maybe_add_progress_summary` once ≥2 core fields are known | `tests/unit/agents/shared/test_summary.py`, `test_conversation_progress_summary_appears_once_enough_fields_are_known` |
| 7 | Intent switching without losing context (Claims↔Broker↔Commercial) | Global memory (this PBI) layered on the pre-existing `carry_forward_other_agent_state` (PBI-05-01) | `test_claims_broker_claims_switch_preserves_both_domains_and_resolves_broker_in_one_turn` |
| 8 | Human, Mexico-appropriate wording ("broker" not "correduría") | 3 strings reworded in `src/agents/broker/state.py`/`workflow.py` | `test_broker_resolved_policy_number_is_reused_by_claims_without_re_asking` (exercises the reworded prompt path); full-suite regression confirms no test depended on the old wording |
| 9 | Deduplication (never repeat an already-answered question) | Memory pre-fill (requirement 2) + each Agent's own pre-existing "already filled fields are never re-asked" state-machine invariant | `test_broker_broker_policy_status_flow_never_repeats_an_already_answered_question` |
| 10 | Tool orchestration restraint (skip a call when info is already known) | `BrokerAgent`'s `broker_id` pre-fill skips `LOOKING_UP_BROKER`/`broker_lookup` entirely when memory already resolved it | `test_claims_broker_claims_switch_...` (Broker resolves policy status in a single turn, no separate policy-number question) |
| 11 | Acceptance tests for the 12 listed regression scenarios | See below | `tests/conversational/test_global_memory_and_multi_domain_orchestration.py` (6 tests) + unit tests |

### Acceptance-scenario coverage (requirement 11's own list)

| Scenario | Covered by |
|---|---|
| Claims→Broker→Claims | `test_claims_broker_claims_switch_preserves_both_domains_and_resolves_broker_in_one_turn` |
| Broker→Claims→Broker (shape) | `test_broker_resolved_policy_number_is_reused_by_claims_without_re_asking` |
| Policy lookup→Claims | `test_broker_resolved_policy_number_is_reused_by_claims_without_re_asking` |
| Natural dates | `test_nlu.py` (la semana pasada/last week), `test_natural_relative_week_and_weather_phrasing_...` |
| Repeated information / no repeated questions | `test_broker_broker_policy_status_flow_never_repeats_an_already_answered_question` |
| Broker name only | Pre-existing `test_chat_drives_a_full_commission_conversation_end_to_end_through_the_real_api` (unmodified, still green) exercises this path; memory now additionally captures the result (`test_memory.py`) |
| Policy only | `test_broker_resolved_policy_number_is_reused_by_claims_without_re_asking` |
| Customer only | `test_customer_only_discovery_is_reused_by_commercial_intake` |
| Entity resolution | `test_customer_only_discovery_is_reused_by_commercial_intake`, `test_claims_broker_claims_switch_...` |
| Conversation memory | `test_memory.py`, all `_memory(...)` assertions across the acceptance file |
| Multi-intent switching | `test_claims_broker_claims_switch_preserves_both_domains_and_resolves_broker_in_one_turn` |
| No repeated questions | `test_broker_broker_policy_status_flow_never_repeats_an_already_answered_question` |

## Commands executed

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/unit/agents -q` | 184 passed (pre-flight, before new tests added) |
| `.venv/Scripts/python.exe -m pytest -q` (full suite, before this PBI's new tests) | 612 passed, 2 skipped |
| `.venv/Scripts/python.exe -m pytest tests/conversational/test_global_memory_and_multi_domain_orchestration.py tests/unit/agents/shared/test_memory.py tests/unit/agents/shared/test_summary.py tests/unit/agents/shared/test_nlu.py tests/unit/agents/claims/test_extraction.py -q` | 64 passed |
| `.venv/Scripts/python.exe -m pytest -q` (full suite, after this PBI's changes) | **633 passed**, 2 skipped |
| `.venv/Scripts/python.exe -m ruff check <every touched file>` | All checks passed |
| `.venv/Scripts/python.exe -m mypy <every touched src file>` | Success: no issues found in 9 source files |

No Bicep/infrastructure validation was run — none of this PBI's changes touch `ops/bicep/` or
any Azure resource, per its own explicit scope.

## PBI-09-01 Final Conversational Validation (2026-08-10)

Live, realistic multi-turn conversations were driven through the real FastAPI app (`TestClient`,
`MockLLMProvider`, synthetic data — the same pattern every test in this suite already uses, not
a new dependency) covering all 14 scenarios the validation task specified: Broker→commissions→
Claims→Broker; Claims→policy inquiry→Claims; Commercial→Claims→Commercial; policy/customer/
broker-name-only; natural dates (yesterday/last week/two days ago); multi-fact single sentence;
fact correction; multi-intent switching; a 14-turn long conversation; ambiguous entity lookup;
cross-agent reuse; and resuming a prior intent. Transcripts were inspected turn-by-turn for the
task's explicit defect checklist (repeated questions, lost context, wrong entity resolution,
unnecessary identifier requests, robotic wording, natural-date/reuse failures).

### Defects found and fixed

| # | Defect | Root cause | Fix | Regression test |
|---|---|---|---|---|
| 1 | A domain-switch-back message ("Let's continue with my claim from before.") was silently swallowed as the answer to a stale question (e.g. became the `event_location`) | Free-text fallback in each Agent's `extraction.py` blindly attributes any message to `last_asked_field`, with no signal that the message was a routing/resumption phrase rather than an answer | Each Agent's `handle()` now clears `last_asked_field`/`last_asked_group` when `context.current_agent != self.name` (a genuine domain re-entry), before extraction runs — the message is still mined for real facts, never blindly attributed | `test_domain_reentry_does_not_misattribute_the_switch_back_message_as_an_answer`, `..._as_a_customer_name` |
| 2 | "Juan Perez" (no accent) failed to match the synthetic record "Juan Pérez" — the ambiguous-entity disambiguation flow was unreachable | `CustomerLookupTool`/`BrokerLookupTool` compared strings with a plain case-folded substring check, no accent normalization | New `src/common/text_normalization.normalize_for_search` (NFKD-decompose, strip combining marks), used by both lookup Tools | `tests/unit/services/test_lookup_tools_accent_insensitivity.py`, `tests/unit/common/test_text_normalization.py`, `test_ambiguous_customer_name_without_accent_still_resolves_and_disambiguates` |
| 3 | Broker's combined "broker name + period" question repeated verbatim after a bare name answer with no "soy"/"somos" prefix | `_handle_collecting_information` (broker/workflow.py) never set `last_asked_field`, so the free-text fallback that depends on it never activated | Set `last_asked_field=missing[0]` when asking for missing fields, mirroring Claims' own pattern | `test_broker_combined_question_captures_a_bare_broker_name_with_no_prefix` |
| 4 | English relative dates ("yesterday", "two days ago") were entirely unsupported — only Spanish single-day words existed | `_RELATIVE_DATE_WORDS` (nlu.py) had no English entries and no "N days ago" pattern at all | Added `today`/`yesterday`; added `_DAYS_AGO_EN_PATTERN`/`_DAYS_AGO_ES_PATTERN` with a small word-to-number map | `tests/unit/agents/shared/test_nlu.py` (existing file, new cases) |
| 5 | A bare "no" answering the combined injuries+third-parties question only ever resolved `injuries_reported`, forcing a redundant second question | The single-field yes/no fallback in `extract_fields` ran *before* the "combo" check, always claiming the field first | Reordered: the combo check now runs first | `test_bare_no_answers_both_injuries_and_third_parties_from_the_combined_question`, `test_single_yes_no_field_fallback_still_works_outside_the_combo_group` |
| 6 | An opening message packing several facts in one sentence never had its location extracted at all; separately, when it was captured, a trailing unrelated clause joined only by a comma ("...Ciudad de Mexico, no hubo lesionados...") was swept in | Location extraction only ever ran when a *prior* question had specifically been about location; the regex captured to the next period, not the next independent clause | Added an unconditional opportunistic extraction attempt (mirrors how date/policy/loss-type already work); trim the captured phrase at a comma-joined negation clause (`, no`/`, sin`/`, ni`) | `test_opening_message_with_several_facts_extracts_location_without_being_asked`, `test_opening_message_with_several_facts_reuses_the_location_without_re_asking` |
| 7 | Regression introduced by fixing #6: "En realidad, volvamos a mi accidente." (a domain switch-back message) was silently captured as `event_location`, since "en" also starts the common Spanish filler "en realidad" ("actually") — invisible corruption, the visible response still looked correct | Making location extraction unconditional (#6's fix) had no way to distinguish a genuine "en \<place\>" from a discourse idiom starting with the same word | Small, bounded denylist (`_NON_LOCATION_PREPOSITION_FOLLOWERS`) skips the match when the word right after "en"/"at" is a known non-locative filler | `test_en_realidad_filler_phrase_is_never_mistaken_for_a_location`; `test_domain_reentry_does_not_misattribute_the_switch_back_message_as_a_customer_name` now also asserts memory stays clean, not just the visible response |

### Commands executed

| Command | Result |
|---|---|
| Live scenario driver (14 scenarios, `TestClient`) — before fixes | 6 defect classes observed across multiple scenarios |
| Live scenario driver (14 scenarios, `TestClient`) — after first round of fixes | 5/6 clean; re-running surfaced a 7th, new regression from the location-extraction fix itself (`en realidad` filler false positive) |
| Live scenario driver (14 scenarios, `TestClient`) — after all fixes, final rerun | All 14 scenarios clean: no repeated questions, no lost context, correct entity resolution, memory reused correctly |
| `.venv/Scripts/python.exe -m pytest -q` (full suite, after all final-validation fixes) | **649 passed**, 2 skipped |
| `.venv/Scripts/python.exe -m ruff check <every touched file>` | All checks passed |
| `.venv/Scripts/python.exe -m mypy <every touched src file>` | Success: no issues found in 9 source files |

### Remaining conversational limitations (not fixed — out of this validation's scope)

- A bare policy number as the very *first* message ("SYN-POL-1001", no other words) resolves to
  `UNKNOWN`/`FallbackAgent` — no `_CLAIMS_KEYWORDS`/`_BROKER_KEYWORDS` match a bare identifier
  with no surrounding intent language. This is a `src/supervisor/intent.py` routing gap (already
  flagged pre-existing in D-06, `decisions.md`) — Supervisor routing changes are explicitly out
  of scope for this validation task.
- `loss_type` accepts arbitrary free text when no canonical keyword matches (the prompt itself
  offers "otro"/"other" as an explicit catch-all option) — a caller describing what happened in
  their own words, when it doesn't match a keyword, has that description stored verbatim as the
  "type". This is pre-existing, intentional leniency (not a regression), left unchanged.
- After a confirmation decline, *every* incident-detail field (including `contact_phone`, already
  answered earlier) is cleared and must be re-collected — a deliberate, pre-existing "clean
  slate" design, not narrowed to only the field the caller meant to correct. Verified working as
  designed; not narrowed here (would be a behavior change to an existing, tested flow, not a
  defect fix).
