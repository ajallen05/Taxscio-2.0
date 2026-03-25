/**
 * ExceptionManager.jsx — Light theme edition
 * Same API calls, same props, same logic as original.
 * Visual design updated to match Taxscio_platform_Light.html
 *
 * API endpoints used (unchanged):
 *   POST ${apiUrl}/apply-fixes
 *   POST ${apiUrl}/revalidate
 */
import { useState, useCallback } from "react";
import { Eye, EyeOff, CheckCircle2, AlertCircle } from "lucide-react";

// ── Severity config ───────────────────────────────────────────────────────────
const SEV = {
    CRITICAL: {
        badge: "bg-red-50 text-red-600 border border-red-100 font-bold",
        row: "border-l-4 border-red-500",
        rowBg: "rgba(220,38,38,0.03)",
        rowBgHover: "rgba(220,38,38,0.06)",
        icon: "⛔",
    },
    BLOCKING: {
        badge: "bg-orange-50 text-orange-600 border border-orange-100 font-semibold",
        row: "border-l-4 border-orange-400",
        rowBg: "rgba(249,115,22,0.03)",
        rowBgHover: "rgba(249,115,22,0.06)",
        icon: "🔶",
    },
    WARNING: {
        badge: "bg-amber-50 text-amber-600 border border-amber-100",
        row: "border-l-4 border-amber-400",
        rowBg: "rgba(217,119,6,0.03)",
        rowBgHover: "rgba(217,119,6,0.06)",
        icon: "⚠️",
    },
    INFO: {
        badge: "bg-blue-50 text-blue-500 border border-blue-100",
        row: "border-l-4 border-blue-300",
        rowBg: "rgba(59,130,246,0.02)",
        rowBgHover: "rgba(59,130,246,0.05)",
        icon: "ℹ️",
    },
};

function SevBadge({ sev }) {
    const s = SEV[sev] || SEV.INFO;
    return (
        <span className={`text-xs px-2 py-0.5 rounded-full ${s.badge}`}>
            {s.icon} {sev}
        </span>
    );
}

// ── Summary bar ───────────────────────────────────────────────────────────────
function SummaryBar({ summary, fixableCount, reviewCount, showSidePdf, setShowSidePdf }) {
    return (
        <div className="flex flex-wrap items-center gap-3 py-3 px-4 rounded-xl border mb-4"
            style={{ background: "#ffffff", borderColor: "#e2e2e5" }}>
            <div className="flex items-center gap-4 flex-1 flex-wrap">
                {summary.critical > 0 && (
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-red-600">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                        {summary.critical} Critical
                    </span>
                )}
                {summary.blocking > 0 && (
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-orange-600">
                        <span className="w-2.5 h-2.5 rounded-full bg-orange-400" />
                        {summary.blocking} Blocking
                    </span>
                )}
                {summary.warning > 0 && (
                    <span className="flex items-center gap-1.5 text-sm text-amber-600 font-medium">
                        <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                        {summary.warning} Warning
                    </span>
                )}
                {summary.info > 0 && (
                    <span className="flex items-center gap-1.5 text-sm text-blue-500 font-medium">
                        <span className="w-2.5 h-2.5 rounded-full bg-blue-400" />
                        {summary.info} Info
                    </span>
                )}
                {summary.total === 0 && (
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-green-600">
                        <span className="w-2.5 h-2.5 rounded-full bg-green-500" />
                        All clear — no exceptions
                    </span>
                )}
            </div>
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
                {fixableCount > 0 && (
                    <span className="bg-green-50 text-green-600 px-2 py-0.5 rounded-full border border-green-100">
                        {fixableCount} auto-fixable
                    </span>
                )}
                {reviewCount > 0 && (
                    <span className="bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full border border-purple-100">
                        {reviewCount} manual review
                    </span>
                )}
                <button
                    onClick={() => setShowSidePdf(!showSidePdf)}
                    className={`ml-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[10px] font-bold uppercase transition-all
            ${showSidePdf
                            ? "bg-blue-50 border-blue-100 text-blue-500 hover:bg-blue-100"
                            : "border-gray-200 text-gray-400 hover:text-gray-600 hover:border-gray-300"
                        }`}
                >
                    {showSidePdf ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {showSidePdf ? "Hide Doc" : "Show Doc"}
                </button>
            </div>
        </div>
    );
}

// ── Unified Exception Row ─────────────────────────────────────────────────────
function ExceptionRow({
    exc, hasAI, isApplied, onApply, onUndo, editValue, onChange, isSaved, onSave,
    onIgnoreClick, isPendingIgnore, onConfirmIgnore, onCancelIgnore, onEscalate
}) {
    const s = SEV[exc.severity] || SEV.INFO;
    const isDirty = editValue !== String(exc.current_value ?? "");

    return (
        <div
            className={`rounded-xl border mb-3 overflow-hidden transition-all duration-200 ${isApplied ? "opacity-40" : "hover:shadow-sm"}`}
            style={{ borderColor: "#e2e2e5", background: isApplied ? "#f8f8f8" : "#ffffff" }}
        >
            <div className={`p-5 ${s.row}`} style={{ background: s.rowBg }}>
                <div className="flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-2">
                            <SevBadge sev={exc.severity} />
                            <code className="text-[10px] uppercase font-bold px-2 py-0.5 rounded font-mono"
                                style={{ background: "#f1f1f3", color: "#5c5c66", border: "1px solid #e2e2e5" }}>
                                {exc.code}
                            </code>
                            {exc.field && (
                                <code className="text-[10px] uppercase font-bold px-2 py-0.5 rounded font-mono"
                                    style={{ background: "rgba(139,92,246,0.06)", color: "#7c3aed", border: "1px solid rgba(139,92,246,0.15)" }}>
                                    {exc.field}
                                </code>
                            )}
                        </div>
                        <p className="text-sm font-medium mb-4" style={{ color: "#111113", lineHeight: 1.5 }}>{exc.description}</p>

                        {/* AI Suggestion Box */}
                        {hasAI && !isApplied && (
                            <div className="flex items-center justify-between p-4 rounded-xl border mb-3"
                                style={{ background: "rgba(22,163,74,0.03)", borderColor: "rgba(22,163,74,0.15)" }}>
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
                                        style={{ background: "rgba(22,163,74,0.1)" }}>
                                        <span className="text-green-600 text-sm">✦</span>
                                    </div>
                                    <div>
                                        <span className="text-[10px] text-green-600 font-bold uppercase tracking-widest block leading-none mb-1">AI Proposed Fix</span>
                                        <span className="text-sm text-green-700 font-bold">{exc.fix_description || `Set to: ${exc.proposed_value}`}</span>
                                    </div>
                                </div>
                                <button onClick={onApply} className="text-xs font-bold uppercase tracking-widest text-white px-5 py-2.5 rounded-lg transition-colors active:scale-95 shadow-sm"
                                    style={{ background: "#16a34a" }}>
                                    Apply Suggestion
                                </button>
                            </div>
                        )}

                        {hasAI && isApplied && (
                            <div className="flex items-center gap-3 p-3 rounded-xl border mb-3"
                                style={{ background: "rgba(22,163,74,0.08)", borderColor: "rgba(22,163,74,0.15)" }}>
                                <span className="text-[10px] font-bold uppercase tracking-widest text-green-600">✓ AI Fix Applied</span>
                                <button onClick={onUndo} className="text-[10px] font-bold uppercase tracking-widest underline underline-offset-4 ml-auto" style={{ color: "#8e8e99" }}>Undo</button>
                            </div>
                        )}

                        {/* Manual Override Input */}
                        {!isApplied && (
                            <div className="rounded-xl p-4 border"
                                style={{ background: "#fafafa", borderColor: "rgba(139,92,246,0.15)" }}>
                                <div className="flex items-center justify-between mb-3">
                                    <span className="text-[10px] text-purple-600 font-bold uppercase tracking-widest">Override Terminal</span>
                                    <span className="text-[10px] text-gray-500 uppercase font-medium">{hasAI ? "Or manually override" : "Manual input required"}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="flex-1 relative">
                                        <input
                                            type="text"
                                            value={editValue}
                                            onChange={(e) => onChange(e.target.value)}
                                            placeholder={exc.current_value != null ? String(exc.current_value) : "Enter override value..."}
                                            className="w-full px-4 py-2.5 rounded-lg border-2 font-mono text-sm focus:outline-none transition-all"
                                            style={{
                                                borderColor: isSaved ? "#16a34a" : isDirty ? "#7c3aed" : "#e2e2e5",
                                                background: isSaved ? "rgba(22,163,74,0.04)" : isDirty ? "rgba(139,92,246,0.04)" : "#ffffff",
                                            }}
                                        />
                                    </div>
                                    <button
                                        onClick={onSave}
                                        disabled={!isDirty}
                                        className="text-[10px] font-bold uppercase tracking-widest px-5 py-3 rounded-lg transition-all active:scale-95 whitespace-nowrap text-white"
                                        style={{
                                            background: isSaved ? "#16a34a" : isDirty ? "#7c3aed" : "#e2e2e5",
                                            color: isDirty || isSaved ? "#fff" : "#8e8e99",
                                            cursor: isDirty || isSaved ? "pointer" : "not-allowed",
                                        }}
                                    >
                                        {isSaved ? "Saved" : "Save Override"}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                    <div className="pt-2 flex flex-col items-end gap-2 shrink-0">
                        {isPendingIgnore ? (
                            <div className="flex flex-col gap-2 items-end">
                                <span className="text-[10px] font-bold uppercase text-amber-600">Dismiss?</span>
                                <div className="flex items-center gap-2">
                                    <button onClick={onConfirmIgnore} className="text-[10px] font-bold uppercase tracking-widest text-white px-3 py-1.5 rounded"
                                        style={{ background: "#dc2626" }}>Yes</button>
                                    <button onClick={onCancelIgnore} className="text-[10px] font-bold uppercase tracking-widest"
                                        style={{ color: "#8e8e99" }}>No</button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <button onClick={() => onEscalate(exc)} className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 px-3 py-2 rounded-lg transition-colors text-red-500 hover:bg-red-50 border border-transparent hover:border-red-100">
                                    <span>↑</span> Escalate
                                </button>
                                <button onClick={onIgnoreClick} className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 px-3 py-2 rounded-lg transition-colors text-gray-400 hover:bg-gray-100 mt-1">
                                    <span>✕</span> Ignore
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

// ── Change log row ────────────────────────────────────────────────────────────
function ChangeLogRow({ change }) {
    return (
        <div className="flex items-center gap-2 text-[10px] py-1.5 border-b last:border-0 uppercase font-bold tracking-widest"
            style={{ borderColor: "#e2e2e5" }}>
            <code className="font-mono px-1.5 py-0.5 rounded border" style={{ color: "#7c3aed", background: "rgba(139,92,246,0.06)", borderColor: "rgba(139,92,246,0.15)" }}>
                {change.field}
            </code>
            <span style={{ color: "#8e8e99" }}>original</span>
            <code className="font-mono line-through opacity-50 text-red-500">{change.original == null ? "null" : String(change.original)}</code>
            <span className="text-amber-500">→</span>
            <code className="font-mono text-green-600">{change.new_value == null ? "null" : String(change.new_value)}</code>
        </div>
    );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ExceptionManager({
    apiUrl,
    formType,
    data,
    fixableExceptions,
    reviewExceptions,
    allExceptions,
    summary,
    showSidePdf,
    setShowSidePdf,
    onResolved,
    ignoredIds,
    setIgnoredIds,
    humanVerifiedFields = [],
}) {
    const [appliedFixes, setAppliedFixes] = useState(new Set());
    const [editedValues, setEditedValues] = useState({});
    const [savedFields, setSavedFields] = useState(new Set());
    const [pendingIgnoreId, setPendingIgnoreId] = useState(null);
    const [showIgnored, setShowIgnored] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState(null);
    const [changeLog, setChangeLog] = useState([]);
    const [hasSubmitted, setHasSubmitted] = useState(false);
    const [showInfoExceptions, setShowInfoExceptions] = useState(false);

    const infoExceptions = (allExceptions || []).filter(e => e.severity === "INFO");
    const getExcId = (e) => `${e.code}:${e.field || "document"}`;

    const activeFixable = (fixableExceptions || []).filter(e => !ignoredIds.has(getExcId(e)));
    const activeReview = (reviewExceptions || []).filter(e => !ignoredIds.has(getExcId(e)));
    const structuralExceptions = (allExceptions || []).filter(
        e => !e.field && e.severity !== "INFO" && !ignoredIds.has(getExcId(e))
    );
    const ignoredExceptions = (allExceptions || []).filter(e => ignoredIds.has(getExcId(e)));

    const handleApplyFix = useCallback((exc) => {
        setAppliedFixes(prev => new Set([...prev, exc.code + ":" + exc.field]));
    }, []);

    const handleUndoFix = useCallback((exc) => {
        setAppliedFixes(prev => { const n = new Set(prev); n.delete(exc.code + ":" + exc.field); return n; });
    }, []);

    const handleIgnoreClick = useCallback((exc) => { setPendingIgnoreId(getExcId(exc)); }, []);
    const handleConfirmIgnore = useCallback(() => {
        if (pendingIgnoreId) { setIgnoredIds(prev => new Set([...prev, pendingIgnoreId])); setPendingIgnoreId(null); }
    }, [pendingIgnoreId, setIgnoredIds]);
    const handleCancelIgnore = useCallback(() => { setPendingIgnoreId(null); }, []);
    const handleUndoIgnore = useCallback((id) => {
        setIgnoredIds(prev => { const n = new Set(prev); n.delete(id); return n; });
    }, [setIgnoredIds]);
    const handleEscalate = useCallback(async (exc) => {
        try {
            await fetch(`${apiUrl}/ledger/escalate-exception`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    document_id: data.document_id || "unknown",
                    client_name: data.name_on_return || data.taxpayer_name || "unknown",
                    document_type: formType,
                    exception_code: exc.code,
                    exception_field: exc.field,
                    severity: exc.severity,
                    description: exc.description,
                    payload: data
                })
            });
            // Auto hide the escalated exception locally:
            setIgnoredIds(prev => new Set([...prev, getExcId(exc)]));
        } catch (e) {
            console.error("Escalation failed", e);
        }
    }, [apiUrl, formType, data, setIgnoredIds]);

    const handleApplyAllFixes = useCallback(() => {
        setAppliedFixes(new Set(fixableExceptions.map(e => e.code + ":" + e.field)));
    }, [fixableExceptions]);
    const handleEditChange = useCallback((field, value) => {
        setEditedValues(prev => ({ ...prev, [field]: value }));
        setSavedFields(prev => { const n = new Set(prev); n.delete(field); return n; });
    }, []);
    const handleSaveField = useCallback((field) => {
        setSavedFields(prev => new Set([...prev, field]));
    }, []);

    const buildFixes = useCallback(() => {
        const fixes = [];
        for (const exc of fixableExceptions) {
            if (appliedFixes.has(exc.code + ":" + exc.field))
                fixes.push({ field: exc.field, new_value: exc.proposed_value });
        }
        for (const field in editedValues) fixes.push({ field, new_value: editedValues[field] });
        return fixes;
    }, [fixableExceptions, appliedFixes, editedValues]);

    const handleSubmit = useCallback(async () => {
        const fixes = buildFixes();
        if (!fixes.length) return;
        setIsSubmitting(true);
        setSubmitError(null);
        const sessionId = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('taxio_session_id') : null;
        try {
            const h_keys = [...(humanVerifiedFields || []), ...Array.from(savedFields)];
            const res = await fetch(`${apiUrl}/apply-fixes`, {
                method: "POST", 
                headers: { 
                    "Content-Type": "application/json",
                    ...(sessionId ? { "X-Session-ID": sessionId } : {})
                },
                body: JSON.stringify({ 
                    form_type: formType, 
                    data, 
                    fixes, 
                    pdf_type: summary.pdf_type || "scanned", 
                    human_verified_fields: h_keys 
                }),
            });
            const updated = await res.json();
            if (!res.ok) { setSubmitError(updated.error || "Server error."); return; }
            setChangeLog(fixes.map(f => ({ field: f.field, original: data[f.field], new_value: f.new_value })));
            setHasSubmitted(true);
            setAppliedFixes(new Set()); setSavedFields(new Set()); setEditedValues({});
            if (onResolved) onResolved(updated);
        } catch (err) {
            setSubmitError(err.message);
        } finally { setIsSubmitting(false); }
    }, [apiUrl, formType, data, buildFixes, onResolved, summary.pdf_type, humanVerifiedFields]);

    const handleRevalidate = useCallback(async () => {
        setIsSubmitting(true); setSubmitError(null);
        const sessionId = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('taxio_session_id') : null;
        try {
            const h_keys = [...(humanVerifiedFields || []), ...Array.from(savedFields)];
            const res = await fetch(`${apiUrl}/revalidate`, {
                method: "POST", 
                headers: { 
                    "Content-Type": "application/json",
                    ...(sessionId ? { "X-Session-ID": sessionId } : {})
                },
                body: JSON.stringify({ 
                    form_type: formType, 
                    data, 
                    pdf_type: summary.pdf_type || "scanned", 
                    human_verified_fields: h_keys 
                }),
            });
            const updated = await res.json();
            if (!res.ok) { setSubmitError(updated.error || "Revalidation failed."); return; }
            if (onResolved) onResolved(updated);
        } catch (err) { setSubmitError(err.message); }
        finally { setIsSubmitting(false); }
    }, [apiUrl, formType, data, onResolved, summary.pdf_type, humanVerifiedFields]);

    const appliedCount = appliedFixes.size;
    const manualCount = Object.keys(editedValues).length;
    const totalPending = appliedCount + manualCount;

    return (
        <div className="space-y-4">
            <SummaryBar summary={summary} fixableCount={fixableExceptions.length} reviewCount={reviewExceptions.length} showSidePdf={showSidePdf} setShowSidePdf={setShowSidePdf} />

            {/* Change log */}
            {hasSubmitted && changeLog.length > 0 && (
                <div className="rounded-xl border p-4" style={{ background: "rgba(22,163,74,0.04)", borderColor: "rgba(22,163,74,0.18)" }}>
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-green-600 font-bold text-[10px] uppercase tracking-widest">
                            ✓ {changeLog.length} fix{changeLog.length !== 1 ? "es" : ""} applied & re-validated
                        </span>
                        <button onClick={() => setHasSubmitted(false)} className="text-[10px] font-bold uppercase tracking-widest ml-auto" style={{ color: "#8e8e99" }}>Dismiss</button>
                    </div>
                    <div className="mt-1 space-y-1">{changeLog.map((c, i) => <ChangeLogRow key={i} change={c} />)}</div>
                </div>
            )}

            {/* Error */}
            {submitError && (
                <div className="rounded-xl border p-4 text-xs font-medium text-red-600" style={{ background: "rgba(220,38,38,0.04)", borderColor: "rgba(220,38,38,0.15)" }}>
                    ⚠️ {submitError}
                </div>
            )}

            {/* Auto-fixable section */}
            {activeFixable.length > 0 && (
                <div className="rounded-xl border overflow-hidden" style={{ background: "#fff", borderColor: "rgba(22,163,74,0.2)" }}>
                    <div className="flex items-center justify-between px-4 py-3 border-b" style={{ background: "rgba(22,163,74,0.04)", borderColor: "rgba(22,163,74,0.15)" }}>
                        <div className="flex items-center gap-2">
                            <span className="text-green-600 font-bold text-[10px] uppercase tracking-widest">⚡ AI Suggestion Available</span>
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: "rgba(22,163,74,0.08)", color: "#16a34a", border: "1px solid rgba(22,163,74,0.18)" }}>
                                {activeFixable.length}
                            </span>
                            <span className="text-[10px] hidden sm:inline" style={{ color: "#8e8e99" }}>— Algorithmic corrections available</span>
                        </div>
                        <button
                            onClick={handleApplyAllFixes}
                            disabled={appliedFixes.size === activeFixable.length}
                            className="text-[10px] font-bold uppercase tracking-widest px-3 py-1.5 rounded-lg transition-all text-white"
                            style={{ background: appliedFixes.size === activeFixable.length ? "#e2e2e5" : "#16a34a", color: appliedFixes.size === activeFixable.length ? "#8e8e99" : "#fff", cursor: appliedFixes.size === activeFixable.length ? "not-allowed" : "pointer" }}
                        >Apply All Suggestions</button>
                    </div>
                    <div className="p-3">
                        {activeFixable.map((exc, i) => {
                            const key = exc.code + ":" + exc.field;
                            return (
                                <ExceptionRow key={i} exc={exc}
                                    hasAI={true}
                                    isApplied={appliedFixes.has(key)} isPendingIgnore={pendingIgnoreId === getExcId(exc)}
                                    onApply={() => handleApplyFix(exc)} onUndo={() => handleUndoFix(exc)}
                                    editValue={editedValues[exc.field] ?? String(exc.current_value ?? "")}
                                    isSaved={savedFields.has(exc.field)}
                                    onChange={(v) => handleEditChange(exc.field, v)} onSave={() => handleSaveField(exc.field)}
                                    onEscalate={handleEscalate}
                                    onIgnoreClick={() => handleIgnoreClick(exc)}
                                    onConfirmIgnore={handleConfirmIgnore} onCancelIgnore={handleCancelIgnore}
                                />
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Manual review section */}
            {activeReview.length > 0 && (
                <div className="rounded-xl border overflow-hidden" style={{ background: "#fff", borderColor: "rgba(139,92,246,0.2)" }}>
                    <div className="flex items-center gap-2 px-4 py-3 border-b" style={{ background: "rgba(139,92,246,0.04)", borderColor: "rgba(139,92,246,0.15)" }}>
                        <span className="text-purple-600 font-bold text-[10px] uppercase tracking-widest">✏️ Manual Review Required</span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: "rgba(139,92,246,0.08)", color: "#7c3aed", border: "1px solid rgba(139,92,246,0.18)" }}>
                            {activeReview.length}
                        </span>
                        <span className="text-[10px] hidden sm:inline" style={{ color: "#8e8e99" }}>— Human verification strongly required (No AI Fixes Found)</span>
                    </div>
                    <div className="p-3">
                        {activeReview.map((exc, i) => (
                            <ExceptionRow key={i} exc={exc}
                                hasAI={false}
                                editValue={editedValues[exc.field] ?? String(exc.current_value ?? "")}
                                isSaved={savedFields.has(exc.field)} isPendingIgnore={pendingIgnoreId === getExcId(exc)}
                                onChange={(v) => handleEditChange(exc.field, v)} onSave={() => handleSaveField(exc.field)}
                                onEscalate={handleEscalate}
                                onIgnoreClick={() => handleIgnoreClick(exc)}
                                onConfirmIgnore={handleConfirmIgnore} onCancelIgnore={handleCancelIgnore}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Structural exceptions */}
            {structuralExceptions.length > 0 && (
                <div className="rounded-xl border overflow-hidden" style={{ background: "#fff", borderColor: "#e2e2e5" }}>
                    <div className="flex items-center gap-2 px-4 py-3 border-b" style={{ background: "#f8f8f8", borderColor: "#e2e2e5" }}>
                        <span className="text-gray-600 font-bold text-[10px] uppercase tracking-widest">🏗 Document Issues</span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: "#f1f1f3", color: "#5c5c66", border: "1px solid #e2e2e5" }}>
                            {structuralExceptions.length}
                        </span>
                    </div>
                    <div className="p-3 space-y-3">
                        {structuralExceptions.map((exc, i) => {
                            const s = SEV[exc.severity] || SEV.INFO;
                            return (
                                <div key={i} className={`rounded-xl p-4 relative group ${s.row}`}
                                    style={{ background: s.rowBg, border: "1px solid #e2e2e5" }}>
                                    <button
                                        onClick={() => handleIgnoreClick(exc)}
                                        className="absolute top-3 right-3 text-[10px] font-bold uppercase opacity-0 group-hover:opacity-100 transition-opacity"
                                        style={{ color: "#8e8e99" }}
                                    >Ignore</button>
                                    {pendingIgnoreId === getExcId(exc) && (
                                        <div className="absolute top-10 right-3 bg-white border rounded-lg shadow-lg p-3 z-20 flex flex-col gap-2 items-end"
                                            style={{ borderColor: "#e2e2e5" }}>
                                            <span className="text-[10px] font-bold uppercase text-amber-600">Confirm?</span>
                                            <div className="flex gap-2">
                                                <button onClick={handleConfirmIgnore} className="text-[9px] font-bold uppercase text-white px-2 py-1 rounded" style={{ background: "#dc2626" }}>Yes</button>
                                                <button onClick={handleCancelIgnore} className="text-[9px] font-bold uppercase" style={{ color: "#8e8e99" }}>Cancel</button>
                                            </div>
                                        </div>
                                    )}
                                    <div className="flex items-center gap-2 mb-2">
                                        <SevBadge sev={exc.severity} />
                                        <code className="text-[10px] uppercase font-bold px-2 py-0.5 rounded font-mono"
                                            style={{ background: "#f1f1f3", color: "#5c5c66", border: "1px solid #e2e2e5" }}>{exc.code}</code>
                                    </div>
                                    <p className="text-sm" style={{ color: "#5c5c66", lineHeight: 1.5 }}>{exc.description}</p>
                                    <div className="mt-3 text-[10px] font-bold uppercase tracking-widest flex items-center gap-2">
                                        <span style={{ color: "#d97706" }}>Required Action:</span>
                                        <span style={{ color: "#5c5c66" }}>{exc.handling}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Submit bar */}
            {(fixableExceptions.length > 0 || reviewExceptions.length > 0) && (
                <div className="sticky bottom-0 border-t rounded-b-xl px-5 py-4 flex items-center justify-between gap-4 z-10"
                    style={{ background: "rgba(255,255,255,0.95)", backdropFilter: "blur(8px)", borderColor: "#e2e2e5", boxShadow: "0 -4px 12px rgba(0,0,0,0.05)" }}>
                    <div>
                        <div className="text-[10px] font-bold uppercase tracking-widest" style={{ color: totalPending > 0 ? "#d97706" : "#8e8e99" }}>
                            {totalPending > 0 ? "Ready to Re-validate" : "Pending Corrections"}
                        </div>
                        <div className="text-xs mt-0.5" style={{ color: "#5c5c66" }}>
                            {totalPending === 0 ? "Select fixes above to begin correction loop." :
                                <span><span style={{ color: "#111113" }}>{totalPending}</span> update{totalPending !== 1 ? "s" : ""} staged{appliedCount > 0 ? ` — ${appliedCount} auto` : ""}{manualCount > 0 ? ` — ${manualCount} manual` : ""}</span>}
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button onClick={handleRevalidate} disabled={isSubmitting}
                            className="text-[10px] font-bold uppercase tracking-widest px-4 py-2 rounded-lg border transition-all"
                            style={{ borderColor: "#e2e2e5", color: "#5c5c66" }}>Reset</button>
                        <button
                            onClick={handleSubmit}
                            disabled={totalPending === 0 || isSubmitting}
                            className="text-[10px] font-bold uppercase tracking-widest px-6 py-2.5 rounded-lg transition-all flex items-center gap-2 text-white"
                            style={{ background: totalPending > 0 && !isSubmitting ? "#111113" : "#e2e2e5", color: totalPending > 0 ? "#fff" : "#8e8e99", cursor: totalPending > 0 ? "pointer" : "not-allowed" }}
                        >
                            {isSubmitting ? <><div className="w-3 h-3 border-2 border-gray-300 border-t-white rounded-full animate-spin" />Processing</> :
                                `Apply Changes${totalPending > 0 ? ` (${totalPending})` : ""}`}
                        </button>
                    </div>
                </div>
            )}

            {/* INFO exceptions (collapsed) */}
            {infoExceptions.length > 0 && (
                <div className="rounded-xl border overflow-hidden" style={{ borderColor: "#e2e2e5" }}>
                    <button onClick={() => setShowInfoExceptions(v => !v)}
                        className="w-full flex items-center justify-between px-4 py-3 text-left transition-colors"
                        style={{ background: "#f8f8f8" }}
                        onMouseEnter={e => e.currentTarget.style.background = "#f1f1f3"}
                        onMouseLeave={e => e.currentTarget.style.background = "#f8f8f8"}>
                        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#5c5c66" }}>
                            ℹ️ {infoExceptions.length} Quality Notice{infoExceptions.length !== 1 ? "s" : ""}
                        </span>
                        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#8e8e99" }}>
                            {showInfoExceptions ? "Hide" : "View"}
                        </span>
                    </button>
                    {showInfoExceptions && (
                        <div className="p-4 space-y-2 border-t" style={{ borderColor: "#e2e2e5" }}>
                            {infoExceptions.map((exc, i) => (
                                <div key={i} className="text-xs p-3 rounded-lg border flex items-start gap-3"
                                    style={{ background: "#f8f8f8", borderColor: "#e2e2e5", color: "#5c5c66" }}>
                                    <code className="font-bold text-[10px] uppercase shrink-0" style={{ color: "#8e8e99" }}>{exc.code}</code>
                                    <span style={{ lineHeight: 1.5 }}>{exc.description}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Ignored exceptions */}
            {ignoredExceptions.length > 0 && (
                <div className="rounded-xl border overflow-hidden" style={{ borderColor: "#e2e2e5" }}>
                    <button onClick={() => setShowIgnored(v => !v)}
                        className="w-full flex items-center justify-between px-4 py-3 text-left transition-colors"
                        style={{ background: "#f8f8f8" }}
                        onMouseEnter={e => e.currentTarget.style.background = "#f1f1f3"}
                        onMouseLeave={e => e.currentTarget.style.background = "#f8f8f8"}>
                        <span className="text-[10px] font-bold italic uppercase tracking-widest" style={{ color: "#8e8e99" }}>
                            🚫 {ignoredExceptions.length} Ignored Exception{ignoredExceptions.length !== 1 ? "s" : ""}
                        </span>
                        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#8e8e99" }}>
                            {showIgnored ? "Hide" : "View"}
                        </span>
                    </button>
                    {showIgnored && (
                        <div className="p-4 space-y-2 border-t" style={{ borderColor: "#e2e2e5" }}>
                            {ignoredExceptions.map((exc, i) => (
                                <div key={i} className="text-xs p-3 rounded-lg border flex items-center justify-between gap-3"
                                    style={{ background: "#fafafa", borderColor: "#e2e2e5" }}>
                                    <div className="flex items-center gap-3">
                                        <code className="font-bold text-[10px] uppercase shrink-0" style={{ color: "#c8c8cc" }}>{exc.code}</code>
                                        <span className="line-through opacity-50" style={{ color: "#5c5c66" }}>{exc.description}</span>
                                    </div>
                                    <button onClick={() => handleUndoIgnore(getExcId(exc))}
                                        className="text-[10px] font-bold uppercase text-amber-600 hover:text-amber-700 shrink-0">
                                        Restore
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}