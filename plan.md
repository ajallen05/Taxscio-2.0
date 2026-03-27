# Plan: AI-Only Summary + UI Cleanup

## Goal
Remove rule-based summary fallback logic and use AI summary output only, while removing AI source/model labels from UI.

## Files to modify
- backend/adapters/export_formatter.py
- frontend/src/App.jsx
- plan.md

## Constraints and edge cases
- Keep API response shape stable (`summary` remains an object).
- If AI summary is unavailable, show a neutral unavailable message (not rule-derived narrative).
- Remove all `AI: gemini`/source badges from UI.

## Verification
- Trigger summary generation and confirm backend no longer returns rule-derived summary text.
- Confirm Summary UI no longer shows source/model badges.

## Steps
- [x] Remove rule-derived fallback summary in backend and replace with neutral unavailable summary.
- [x] Remove source/model indicator from Summary UI.
- [x] Verify frontend file has no errors.

# Plan: Client-Level Overall Summary

## Goal
Show an overall narrative summary per selected client (aggregated across all linked documents), instead of showing only one document-level summary string.

## Files to modify
- frontend/src/App.jsx
- plan.md

## Constraints and edge cases
- Keep current summary card wiring intact (single string output to existing UI).
- Include all linked docs for the active client (uploads + ledger rows).
- Handle clients with no docs, partial validation, and missing confidence values.

## Verification
- Confirm summary text changes when switching clients.
- Confirm narrative references aggregate client metrics (doc count, validation/review state, confidence).
- Confirm frontend file has no new errors.

## Steps
- [x] Build aggregate client-level narrative generator from existing `clientDocumentRows` and `clientSummary` state.
- [x] Replace single-doc summary selection logic with aggregate narrative + optional latest AI note.
- [x] Verify frontend diagnostics are clean.

# Plan: Keep client_id, remove payload JSON storage

## Goal
Store only core ledger metadata with `client_id` linkage, and stop persisting large payload JSON blobs in `ledger` and `document_logs`.

## Files to modify
- backend/ledger/models.py
- backend/ledger/schemas.py
- backend/ledger/services.py
- backend/ledger/routes.py
- backend/main.py
- backend/ledger/database.py
- plan.md

## Constraints and edge cases
- Preserve `client_id` matching behavior.
- Keep API contract functional for ledger consumers without payload JSON fields.
- Existing rows with payload JSON should be cleared to reduce storage.

## Verification
- Ensure backend files have no diagnostics errors.
- Confirm ledger API no longer returns payload JSON fields.
- Confirm existing DB rows are scrubbed of payload JSON values.

## Steps
- [x] Remove payload JSON fields from ORM models and API schema.
- [x] Remove payload writes in ledger service and response serialization.
- [x] Clear existing payload JSON values in DB while preserving client_id.
- [x] Validate diagnostics are clean.

# Plan: 1040 Document Checklist panel

## Goal
When a client has uploaded a `1040`, show a checklist panel in the Clients > Documents tab with `Forms | Count | Status | Action`, seeded from previous year client documents, and allow Add/Remove actions with persistence.

## Files to modify
- backend/client_database/models.py
- backend/client_database/schemas.py
- backend/client_database/services.py
- backend/client_database/routes.py
- frontend/src/App.tsx
- plan.md

## Constraints and edge cases
- Show checklist only when selected client has a `1040` document.
- Seed from previous year ledger documents for that client; avoid duplicate rows.
- Remove action with count 1 must ask for confirmation before deleting the form.
- Add action via modal must increment existing forms or create a new row.

## Verification
- Confirm new backend checklist APIs return expected form rows and support add/remove.
- Confirm documents tab renders checklist panel on right side for 1040 clients.
- Confirm add/remove interactions update counts and statuses correctly.

## Steps
- [x] Add client checklist model and API endpoints (list/add/remove + available forms).
- [x] Wire Documents tab UI right-side panel with table columns and status mapping.
- [x] Implement Add Form modal and Remove confirmation modal behavior.
- [x] Run frontend build and check diagnostics.
