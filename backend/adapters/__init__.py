# backend/adapters — thin wrapper classes around each module.
#
# These are the seams for future microservice extraction (skills.md Section 3A).
# The underlying module logic is unchanged.  Each adapter is what the future
# standalone service will call internally; the public API of the adapter class
# becomes the service's HTTP interface.
#
# Extraction order (see CLAUDE.md):
#   Phase 1 → ExportFormatterAdapter (not yet implemented — mostly new code)
#   Phase 2 → GateAdapter + RouterAdapter  (Document Validator)
#   Phase 3 → OCRAdapter + NuExtractAdapter (Extraction Engine)
#   Phase 4 → ValidationAdapter + AutoFixerAdapter + ScorerAdapter (Data Integrity Engine)
