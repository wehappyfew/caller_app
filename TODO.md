# TODO: Generic use cases & personas

Make `caller_app` scenario-agnostic so new call flows (personas, prompts, dynamic variables) can be added without touching core telephony/ElevenLabs plumbing.

## Current state

The pipeline (Twilio outbound → Media Streams → ElevenLabs agent → cost summary) is largely reusable. The **illegal parking / worried citizen** scenario is hardcoded in:

| Area | Files | Coupling |
|------|-------|----------|
| Scenario payload | `app/report_context.py`, `app/config.py` | `CallReportDetails` with `location`, `plate`, `car_color`, `car_brand`; `REPORT_*` env vars |
| CLI | `run_calls.py` | `--location`, `--plate`, `--color`, `--brand` |
| Stream / webhook | `app/main.py` | `report_*` query params, logging |
| Agent init | `app/agent_config.py` | `report_dynamic_variables()`, default `worried_citizen_*` paths |
| Voice pool | `app/agent_profiles.py` | Single pool; prompts point at parking persona only |
| Prompts | `prompts/worried_citizen_*.txt` | `{{report_location}}`, `{{report_plate}}`, etc. |
| Logging | `app/call_log.py` | Hardcoded `report_*` fields |
| Docs | `README.md` | Parking-only examples |

## Goal

- Select a **use case** per call (e.g. `parking_report`, future scenarios).
- Each use case defines: prompts, required dynamic variables, optional CLI flags, agent pool.
- Core code passes a generic **call context** dict into ElevenLabs; no car-specific types in shared modules.

## Proposed layout

```
caller_app/
  use_cases/
    parking_report/
      config.yaml          # or .py module — schema + defaults + agent IDs
      prompts/
        system_female.txt
        system_male.txt
        first_message.txt
    _template/               # copy when adding a new use case
  app/
    call_context.py          # replaces report_context.py (generic stash/pop)
    use_case.py              # load, validate, resolve defaults
```

## Tasks

### Phase 1 — Abstract call context (no behavior change)

- [ ] Add `USE_CASE` env var (default: `parking_report`) and `--use-case` CLI flag.
- [ ] Introduce `app/use_case.py` with a registry; first entry = current parking behavior.
- [ ] Rename/refactor `report_context.py` → `call_context.py`:
  - [ ] Generic `CallContext` (`dict[str, str]` or small dataclass built from schema).
  - [ ] `stash_for_phone` / `pop_for_phone` / `from_stream_params` unchanged in behavior.
- [ ] Move `REPORT_*` defaults out of `config.py` into `use_cases/parking_report/` config.
- [ ] Update `run_calls.py` to resolve context via active use case (keep existing flags working for `parking_report`).
- [ ] Update `main.py`, `agent_config.py`, `call_log.py` to use generic context keys.
- [ ] Verify one parking call end-to-end (same prompts, same dynamic vars, cost summary still works).

### Phase 2 — Use case config file

- [ ] Define schema for `use_cases/<id>/config.yaml`:
  - [ ] `id`, `description`
  - [ ] `prompts` (system_female, system_male, first_message)
  - [ ] `dynamic_variables[]` (`name`, `env`, `cli`, `required`, `description`)
  - [ ] `agent_ids[]` (optional per-use-case pool; fallback to global `ELEVENLABS_AGENT_IDS`)
- [ ] Loader validates required fields before dialing.
- [ ] Support generic `--set key=value` (repeatable) for any variable in the schema.
- [ ] Document ElevenLabs dashboard: dynamic variable names must match use case schema.

### Phase 3 — Prompts & agent profiles

- [ ] Move `prompts/worried_citizen_*.txt` → `use_cases/parking_report/prompts/`.
- [ ] Refactor `agent_profiles.py`:
  - [ ] Voice metadata (name, gender, voice_id) separate from prompt paths.
  - [ ] Prompt paths come from active use case config.
- [ ] Update `sync_agent.py` / startup sync to push prompts from active use case (or sync all registered use cases).
- [ ] Add `use_cases/_template/` with placeholder prompts and config comments.

### Phase 4 — Second use case (proof)

- [ ] Add one non-parking scenario (e.g. simple survey or appointment reminder).
- [ ] Different prompts, different required variables, no car fields.
- [ ] Confirm agent pool can be shared or per-use-case.
- [ ] README section: “Adding a new use case” (copy template, edit config, register, sync agents).

### Phase 5 — Docs & cleanup

- [ ] Update `README.md`: generic architecture, `USE_CASE`, `--set`, env tables per use case.
- [ ] Update `.env.example`: remove parking-only `REPORT_*` or nest under `parking_report` defaults file.
- [ ] Remove dead aliases (`worried_citizen_*` paths in config defaults) once migration is done.
- [ ] Optional: `contacts.csv` column `use_case` to override default per contact.

## Design decisions (to confirm)

- [ ] **Config format**: YAML vs Python modules (`use_cases/parking.py`). YAML is easier for non-devs; Python is simpler to ship first.
- [ ] **Agent pools**: one global pool with persona-specific prompts vs separate `agent_ids` per use case.
- [ ] **Stream params**: prefix (`ctx_report_location`) vs bare names (`report_location`) — bare names match ElevenLabs templates today.
- [ ] **Backward compat**: keep `--location` / `--plate` as aliases for `parking_report` only, or break and document `--set` only.

## Out of scope (for now)

- Multiple use cases in one `run_calls.py` batch run.
- Per-contact use case without explicit flag/column.
- UI for editing use cases.

## Success criteria

1. `USE_CASE=parking_report` behaves exactly as today.
2. Adding a new use case = new folder + config + prompts; no edits to `main.py` / Twilio bridge.
3. Missing required variables block the call with a clear error listing field names.
4. Call logs and cost summary work for any use case.
