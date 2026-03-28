// @ts-nocheck
/**
 * App.jsx — Taxscio Complete Platform
 * All 12 pages, live APIs connected, static placeholders where no endpoint exists.
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import JSZip from 'jszip';
import ExceptionManager from './ExceptionManager';
import AddClientForm from './AddClientForm';

// ═══════════════════════════════════════════════════════════════════════════
// STATIC DATA
// ═══════════════════════════════════════════════════════════════════════════

const STATIC_CLIENTS = [
    { id: 1, name: 'Sarah Mitchell', type: 'Individual', status: 'processing', time: '2m ago' },
    { id: 2, name: 'Patel LLC', type: 'LLC', status: 'exception', time: '5m ago' },
    { id: 3, name: 'Johnson Family Trust', type: 'Trust', status: 'review', time: '8m ago' },
    { id: 4, name: 'Martinez, David & Ana', type: 'Individual', status: 'filed', time: '12m ago' },
    { id: 5, name: 'Rivera Consulting Group', type: 'Partnership', status: 'processing', time: '14m ago' },
    { id: 6, name: 'Westbrook Holdings LLC', type: 'LLC', status: 'approved', time: '22m ago' },
    { id: 7, name: "Chen, Robert & Lisa", type: 'Individual', status: 'exception', time: '18m ago' },
    { id: 8, name: 'Nakamura, Kenji', type: 'Individual', status: 'approved', time: '25m ago' },
    { id: 9, name: 'Greenfield Ventures', type: 'S-Corp', status: 'processing', time: '30m ago' },
    { id: 10, name: 'Thompson, Angela', type: 'Individual', status: 'pending', time: '1h ago' },
];

/** Dedupe by code:field — same logic as PageExceptions (validation may return overlapping lists). */
function countDedupedExceptions(result) {
    if (!result) return 0;
    const seen = new Set();
    let n = 0;
    for (const arr of [result.exceptions, result.fixable_exceptions, result.review_exceptions]) {
        for (const e of arr || []) {
            const key = `${e?.code}:${e?.field}`;
            if (!seen.has(key)) {
                seen.add(key);
                n += 1;
            }
        }
    }
    return n;
}

function normalizeChecklistFormName(name) {
    return String(name || '').trim().toUpperCase();
}

function normalizeChecklistErrorMessage(err) {
    const raw = String(err?.message || err || '').trim();
    if (!raw) return '';
    if (raw.toLowerCase() === 'not found') return '';
    if (raw.includes('404')) return '';
    return raw;
}

const STATIC_EXCEPTIONS = [
    { id: 'e1', client: 'Patel LLC', form: 'Form 1120-S · Schedule C', severity: 'high', type: '⚡ Data Mismatch', desc: 'Revenue ($1,240,000) differs from QuickBooks P&L ($1,287,500). Variance of $47,500 in Q4.', ai: 'Request Q4 bank reconciliation.', conf: '88%', confCls: 'high' },
    { id: 'e2', client: 'Sarah Mitchell', form: 'Form 1040 · Income', severity: 'high', type: '⚡ Data Mismatch', desc: 'W-2 income ($84,200) ≠ bank deposits ($91,450). Variance: $7,250.', ai: 'Request 1099-NEC — likely unreported contract work.', conf: '72%', confCls: 'med' },
    { id: 'e3', client: "Chen, Robert & Lisa", form: 'Form 1040 · Education', severity: 'medium', type: '📄 Missing Document', desc: '1098-T for dependent expected based on prior year. American Opportunity Credit at risk — $2,500 impact.', ai: 'Generate portal link for 1098-T upload.', conf: '94%', confCls: 'high' },
    { id: 'e4', client: 'Apex Manufacturing', form: 'Form 1120 · R&D Credit', severity: 'medium', type: '🔢 Calculation Variance', desc: 'R&D credit ($182,000) exceeds simplified method ($156,000). May benefit from 4-part test documentation.', ai: 'Switch to regular method — higher credit justified.', conf: '68%', confCls: 'med' },
    { id: 'e5', client: 'Greenfield Ventures', form: 'Form 1120-S · K-1', severity: 'medium', type: '📋 Prior Year Conflict', desc: 'Negative basis for partner J. Greenfield. Distributions ($45,000) exceed basis ($38,200).', ai: 'Reclassify $6,800 excess as capital gain.', conf: '91%', confCls: 'high' },
    { id: 'e6', client: 'Sarah Mitchell', form: 'Form 1040 · Interest', severity: 'low', type: '📄 Missing Document', desc: '1099-INT expected from Chase Bank ($1,240 prior year). No document received.', ai: 'Send automated request via portal.', conf: '91%', confCls: 'high' },
    { id: 'e7', client: 'Rivera Consulting', form: 'Form 1065 · SALT', severity: 'low', type: '🏛 IRS Rule Flag', desc: 'SALT deduction may exceed $10,000 cap. PTE election available — potential savings $8,400.', ai: 'Apply PTE election for SALT workaround.', conf: '79%', confCls: 'med' },
];

const STATIC_KANBAN = {
    'Document Collection': [
        { name: 'Thompson, Angela', form: '1040', right: 'Apr 15', avatar: 'MC' },
        { name: 'Brooks Dental PLLC', form: '1120-S', right: 'Mar 15', rightRed: true, avatar: 'JW' },
        { name: 'Lee, David & Susan', form: '1040', right: 'Apr 15', avatar: 'MC' },
        { name: 'Sanchez, Maria', form: '1040', right: 'Apr 15', avatar: 'AL' },
    ],
    'AI Processing': [
        { name: 'Sarah Mitchell', form: '1040', right: 'Apr 15', conf: '98%', confColor: 'green' },
        { name: 'Rivera Consulting', form: '1065', right: 'Mar 17', rightRed: true, conf: '95%', confColor: 'green' },
        { name: 'Greenfield Ventures', form: '1120-S', right: 'Mar 15', rightRed: true, conf: '87%', confColor: 'amber' },
        { name: 'Park, James', form: '1040', right: 'Apr 15', conf: '96%', confColor: 'green' },
        { name: "O'Brien Realty", form: '1065', right: 'Mar 17', rightRed: true, conf: '92%', confColor: 'green' },
    ],
    'Exception Review': [
        { name: 'Patel LLC', form: '1120-S · Sch C', right: 'Mar 15', rightRed: true, conf: '72%', confColor: 'amber', borderLeft: 'var(--red)' },
        { name: "Chen, Robert & Lisa", form: '1040 · 1098-T', right: 'Apr 15', conf: '—', borderLeft: 'var(--amber)' },
        { name: 'Apex Manufacturing', form: '1120 · R&D', right: 'Apr 15', conf: '68%', confColor: 'amber', borderLeft: 'var(--amber)' },
    ],
    'CPA Review': [
        { name: 'Johnson Family Trust', form: '1041', right: 'Mar 17', rightRed: true, avatar: 'MC' },
        { name: 'Williams, James T.', form: '1040', right: 'Apr 15', avatar: 'JW' },
        { name: 'Bright Horizons Inc', form: '1120', right: 'Apr 15', avatar: 'AL' },
        { name: 'Foster, Kim & Ray', form: '1040', right: 'Apr 15', avatar: 'MC' },
    ],
    'Client Approval': [
        { name: 'Nakamura, Kenji', form: '1040', right: 'Apr 15', note: '✓ Signed', noteColor: 'green' },
        { name: 'Harper, Linda', form: '1040', right: 'Apr 15', note: '⏳ Pending', noteColor: 'amber' },
        { name: 'Cascade Digital LLC', form: '1065', right: 'Mar 17', rightRed: true, note: '⏳ Pending', noteColor: 'amber' },
    ],
    'Ready to E-File': [
        { name: 'Atlas Biotech Inc', form: '1120', right: 'Apr 15', conf: '99%', confColor: 'green', borderLeft: 'var(--green)' },
        { name: 'Gray, Patricia', form: '1040', right: 'Apr 15', conf: '99%', confColor: 'green', borderLeft: 'var(--green)' },
        { name: 'Summit Partners LP', form: '1065', right: 'Mar 17', rightRed: true, conf: '98%', confColor: 'green', borderLeft: 'var(--green)' },
    ],
    'Filed & Confirmed': [
        { name: 'Martinez, David & Ana', form: '1040 · $3,240 refund', right: 'Mar 8', note: '✓ Accepted', noteColor: 'green', faded: true },
        { name: 'Taylor Industries', form: '1120 · $12,480 due', right: 'Mar 6', note: '✓ Accepted', noteColor: 'green', faded: true },
        { name: 'Wong, Michael', form: '1040 · $1,890 refund', right: 'Mar 5', note: '✓ Accepted', noteColor: 'green', faded: true },
    ],
};

const STATIC_PIPELINE_TABLE = [
    { client: 'Thompson, Angela', form: '1040', stage: 'Document Collection', cpa: 'M. Chen', conf: null, due: 'Apr 15', status: 'pending' },
    { client: 'Brooks Dental PLLC', form: '1120-S', stage: 'Document Collection', cpa: 'J. Wu', conf: null, due: 'Mar 15', status: 'pending', dueRed: true },
    { client: 'Sarah Mitchell', form: '1040', stage: 'AI Processing', cpa: 'M. Chen', conf: '98%', confCls: 'high', due: 'Apr 15', status: 'processing' },
    { client: 'Rivera Consulting', form: '1065', stage: 'AI Processing', cpa: 'M. Chen', conf: '95%', confCls: 'high', due: 'Mar 17', status: 'processing', dueRed: true },
    { client: 'Greenfield Ventures', form: '1120-S', stage: 'AI Processing', cpa: 'A. Lee', conf: '87%', confCls: 'med', due: 'Mar 15', status: 'processing', dueRed: true },
    { client: 'Patel LLC', form: '1120-S', stage: 'Exception Review', cpa: 'M. Chen', conf: '72%', confCls: 'med', due: 'Mar 15', status: 'exception', dueRed: true },
    { client: "Chen, Robert & Lisa", form: '1040', stage: 'Exception Review', cpa: 'J. Wu', conf: null, due: 'Apr 15', status: 'exception' },
    { client: 'Johnson Family Trust', form: '1041', stage: 'CPA Review', cpa: 'M. Chen', conf: '96%', confCls: 'high', due: 'Mar 17', status: 'review', dueRed: true },
    { client: 'Williams, James T.', form: '1040', stage: 'CPA Review', cpa: 'J. Wu', conf: '95%', confCls: 'high', due: 'Apr 15', status: 'review' },
    { client: 'Nakamura, Kenji', form: '1040', stage: 'Client Approval', cpa: 'M. Chen', conf: '99%', confCls: 'high', due: 'Apr 15', status: 'approved' },
    { client: 'Atlas Biotech Inc', form: '1120', stage: 'Ready to E-File', cpa: 'A. Lee', conf: '99%', confCls: 'high', due: 'Apr 15', status: 'approved' },
    { client: 'Martinez, David & Ana', form: '1040', stage: 'Filed & Confirmed', cpa: 'M. Chen', conf: '99%', confCls: 'high', due: 'Mar 8', status: 'filed' },
    { client: 'Taylor Industries', form: '1120', stage: 'Filed & Confirmed', cpa: 'J. Wu', conf: '98%', confCls: 'high', due: 'Mar 6', status: 'filed' },
];

const STATIC_DEADLINES = [
    { client: 'Patel LLC', form: '1120-S', date: 'Mar 15, 2026', days: '5 days', cls: 'urgent' },
    { client: 'Johnson Family Trust', form: '1041', date: 'Mar 17, 2026', days: '7 days', cls: 'urgent' },
    { client: 'Rivera Consulting', form: '1065', date: 'Mar 17, 2026', days: '7 days', cls: 'urgent' },
    { client: 'Sarah Mitchell', form: '1040', date: 'Apr 15, 2026', days: '36 days', cls: 'warning' },
    { client: "Chen, Robert & Lisa", form: '1040', date: 'Apr 15, 2026', days: '36 days', cls: 'warning' },
    { client: 'Westbrook Holdings', form: '1120', date: 'Apr 15, 2026', days: '36 days', cls: 'ok' },
];

const STATIC_AGENT_JOBS = [
    { client: 'Sarah Mitchell', task: '1040 Processing', pct: 88, color: 'blue', docs: '14/16', conf: '98%', confCls: 'high', dur: '4m 12s', status: 'processing' },
    { client: 'Rivera Consulting', task: '1065 Extraction', pct: 65, color: 'blue', docs: '8/12', conf: '95%', confCls: 'high', dur: '6m 30s', status: 'processing' },
    { client: 'Greenfield Ventures', task: 'K-1 Matching', pct: 40, color: 'amber', docs: '3/7', conf: '87%', confCls: 'med', dur: '3m 05s', status: 'processing' },
    { client: 'Patel LLC', task: 'P&L Reconciliation', pct: 25, color: 'amber', docs: '2/9', conf: '72%', confCls: 'med', dur: '1m 45s', status: 'review' },
    { client: 'Park, James', task: '1040 Processing', pct: 95, color: 'green', docs: '11/11', conf: '96%', confCls: 'high', dur: '8m 20s', status: 'approved' },
];

const STATIC_FEED_ITEMS = [
    { icon: 'ingest', emoji: '📥', text: <p>Ingesting <strong>W-2</strong> for <strong>Sarah Mitchell</strong> → matching to 2025 return</p>, time: '2 min ago', conf: '98%', confCls: 'high', status: 'processing' },
    { icon: 'exception', emoji: '⚠', text: <p>Exception flagged: Discrepancy in <strong>Schedule C</strong> for <strong>Patel LLC</strong></p>, time: '5 min ago', conf: '72%', confCls: 'med', status: 'exception' },
    { icon: 'ready', emoji: '✓', text: <p>Filing ready for CPA review: <strong>Johnson Family Trust</strong> — Form 1041</p>, time: '8 min ago', conf: '96%', confCls: 'high', status: 'review' },
    { icon: 'filed', emoji: '📄', text: <p>E-filed successfully: <strong>Martinez, David & Ana</strong> — Form 1040, Refund $3,240</p>, time: '12 min ago', conf: '99%', confCls: 'high', status: 'filed' },
    { icon: 'ingest', emoji: '📥', text: <p>Extracting <strong>1099-NEC</strong> (x3) for <strong>Rivera Consulting Group</strong></p>, time: '14 min ago', conf: '95%', confCls: 'high', status: 'processing' },
    { icon: 'exception', emoji: '⚠', text: <p>Missing <strong>1098-T</strong> for dependent — <strong>Chen, Robert & Lisa</strong></p>, time: '18 min ago', conf: '—', confCls: 'low', status: 'exception' },
];

const STATIC_DOCS_TABLE = [
    { file: 'W-2_Employer_Acme.pdf', client: 'Sarah Mitchell', type: 'W-2', pages: '1', date: 'Mar 8', status: 'approved', conf: '98%', confCls: 'high' },
    { file: 'PatelLLC_PnL_2025.csv', client: 'Patel LLC', type: 'P&L', pages: '—', date: 'Mar 8', status: 'processing', conf: null },
    { file: '1098_Mortgage_WF.pdf', client: 'Sarah Mitchell', type: '1098', pages: '1', date: 'Mar 7', status: 'approved', conf: '97%', confCls: 'high' },
    { file: 'K1_Greenfield_2025.pdf', client: 'Greenfield Ventures', type: 'K-1', pages: '3', date: 'Mar 7', status: 'review', conf: '87%', confCls: 'med' },
    { file: 'Rivera_1099NEC_x3.pdf', client: 'Rivera Consulting', type: '1099-NEC', pages: '3', date: 'Mar 7', status: 'approved', conf: '95%', confCls: 'high' },
    { file: 'Johnson_Trust_Docs.pdf', client: 'Johnson Family Trust', type: '1041 Sched', pages: '8', date: 'Mar 6', status: 'approved', conf: '96%', confCls: 'high' },
];

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════

const flattenObject = (obj, prefix = '') =>
    Object.keys(obj || {}).reduce((acc, k) => {
        const pre = prefix ? `${prefix}.` : '';
        if (typeof obj[k] === 'object' && obj[k] !== null && !Array.isArray(obj[k]))
            Object.assign(acc, flattenObject(obj[k], pre + k));
        else if (Array.isArray(obj[k]))
            obj[k].forEach((item, i) => typeof item === 'object' && item !== null
                ? Object.assign(acc, flattenObject(item, `${pre}${k}.${i}`))
                : (acc[`${pre}${k}.${i}`] = item));
        else acc[pre + k] = obj[k];
        return acc;
    }, {});

const isSensitiveKey = (key) => {
    const k = key.toLowerCase();
    return k.includes('ssn') || k.includes('tin') || k.includes('claim_number');
};

const maskValue = (value, key, show) => {
    if (show || !value || !isSensitiveKey(key)) return value;
    const s = String(value).trim();
    const k = key.toLowerCase();
    if (k.includes('tin') || (s.includes('-') && s.length === 10)) return `••-${s.slice(-7)}`;
    if (s.length >= 9 && s.replace(/\D/g, '').length === 9) return `•••-••-${s.replace(/\D/g, '').slice(-4)}`;
    return `••••${s.slice(-4)}`;
};

const formatLabel = (key) => {
    const boxMatch = key.match(/^(box_\d+[a-z]?_)(.*)/);
    if (boxMatch) {
        const badge = boxMatch[1].replace(/_/g, ' ').replace(/box/i, 'Box').trim();
        const display = boxMatch[2].replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        return (
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 10, background: 'var(--surface-2)', border: '1px solid var(--border)', padding: '1px 5px', borderRadius: 3, fontFamily: 'monospace', color: 'var(--text-muted)' }}>[{badge}]</span>
                {display}
            </span>
        );
    }
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

const syntaxHighlight = (obj) => {
    const s = JSON.stringify(obj, null, 2);
    return s.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, m => {
        let cls = 'color:#b45309';
        if (/^"/.test(m) && /:$/.test(m)) cls = 'color:#7c3aed';
        else if (/true/.test(m)) cls = 'color:#16a34a';
        else if (/false/.test(m)) cls = 'color:#dc2626';
        else if (/null/.test(m)) cls = 'color:#8e8e99';
        else if (!/^"/.test(m)) cls = 'color:#2563eb';
        return `<span style="${cls}">${m}</span>`;
    });
};

function renderValue(val, key, path, fileName, showSensitive, onEdit) {
    const display = maskValue(val, key, showSensitive);
    let style = { fontFamily: 'monospace', fontSize: 12, color: '#d97706' };
    let dispStr = String(display ?? '');
    if (val === null) { style = { ...style, color: 'var(--text-muted)', fontStyle: 'italic' }; dispStr = '—'; }
    else if (typeof val === 'number') { style.color = '#2563eb'; dispStr = val.toLocaleString('en-US', { maximumFractionDigits: 2 }); }
    else if (typeof val === 'boolean') { style.color = val ? 'var(--green)' : 'var(--text-muted)'; dispStr = val ? 'YES' : ''; }
    return (
        <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
            <input style={{ ...style, background: 'transparent', border: 'none', outline: 'none', textAlign: 'right', cursor: 'text', padding: '2px 4px', borderRadius: 4, width: '100%', transition: 'background .15s' }}
                onFocus={e => e.target.style.background = 'var(--surface-2)'}
                onBlur={e => e.target.style.background = 'transparent'}
                value={dispStr}
                onChange={e => onEdit && onEdit(fileName, path, e.target.value)} />
        </div>
    );
}

function renderObjectFields(obj, prefix, fileName, showSensitive, onEdit) {
    if (!obj || typeof obj !== 'object') return null;
    return Object.keys(obj).map(key => {
        const val = obj[key];
        const path = prefix ? `${prefix}.${key}` : key;
        if (typeof val === 'object' && val !== null && !Array.isArray(val)) {
            return (
                <div key={path} style={{ marginTop: 10, marginLeft: 12, padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'rgba(0,0,0,0.01)' }}>
                    <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '.05em' }}>{formatLabel(key)}</div>
                    {renderObjectFields(val, path, fileName, showSensitive, onEdit)}
                </div>
            );
        }
        if (Array.isArray(val)) {
            if (!val.length) return null;
            if (typeof val[0] === 'object' && val[0] !== null) {
                const cols = Object.keys(val[0]);
                return (
                    <div key={path} style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                        <div style={{ padding: '7px 12px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', fontSize: 12, fontWeight: 600 }}>{formatLabel(key)}</div>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead><tr>{['#', ...cols].map(c => <th key={c} style={{ padding: '7px 12px', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textAlign: 'left', borderBottom: '1px solid var(--border)' }}>{c === '#' ? '#' : formatLabel(c)}</th>)}</tr></thead>
                            <tbody>{val.map((item, idx) => <tr key={idx} style={{ borderBottom: '1px solid var(--border)' }}><td style={{ padding: '7px 12px', color: 'var(--text-muted)', fontSize: 11 }}>{idx + 1}</td>{cols.map(c => <td key={c} style={{ padding: '7px 12px' }}>{renderValue(item[c], c, `${path}.${idx}.${c}`, fileName, showSensitive, onEdit)}</td>)}</tr>)}</tbody>
                        </table>
                    </div>
                );
            }
            return (
                <div key={path} className="field-row">
                    <span className="field-name">{formatLabel(key)}</span>
                    <span style={{ flex: 1, fontFamily: 'monospace', fontSize: 12 }}>{val.map(String).join(', ')}</span>
                </div>
            );
        }
        return (
            <div key={path} className="field-row">
                <span className="field-name">{formatLabel(key)}</span>
                {renderValue(val, key, path, fileName, showSensitive, onEdit)}
            </div>
        );
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// SMALL REUSABLE COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════

function StatusPill({ status }) {
    const map = { processing: 'Processing', review: 'Reviewing', approved: 'Complete', filed: 'Filed', exception: 'Exception', pending: 'Awaiting' };
    return <span className={`status-pill ${status}`}>{map[status] || status}</span>;
}

function ConfBadge({ val, cls }) {
    if (!val) return <span className="confidence-badge">—</span>;
    return <span className={`confidence-badge ${cls || ''}`}>{val}</span>;
}

function Toggle({ defaultChecked }) {
    const [on, setOn] = useState(!!defaultChecked);
    return (
        <label className="toggle" onClick={() => setOn(!on)}>
            <input type="checkbox" checked={on} onChange={() => { }} />
            <div className="toggle-track" />
            <div className="toggle-thumb" />
        </label>
    );
}

function Slider({ defaultValue, min = 50, max = 100 }) {
    const [val, setVal] = useState(defaultValue);
    return (
        <div className="slider-row">
            <input type="range" className="slider" min={min} max={max} value={val} onChange={e => setVal(e.target.value)} />
            <span className="slider-value">{val}%</span>
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// NAV ICONS
// ═══════════════════════════════════════════════════════════════════════════

const NAV_ICONS = {
    dashboard: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>,
    clients: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" /></svg>,
    pipeline: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" /><line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" /><line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" /><line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" /><line x1="17" y1="16" x2="23" y2="16" /></svg>,
    exceptions: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>,
    documents: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14,2 14,8 20,8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>,
    agent: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></svg>,
    ingestion: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polyline points="16,16 12,12 8,16" /><line x1="12" y1="12" x2="12" y2="21" /><path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3" /></svg>,
    airules: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2z" /><circle cx="12" cy="12" r="3" /></svg>,
    reports: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>,
    integrations: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2" y="2" width="20" height="8" rx="2" /><rect x="2" y="14" width="20" height="8" rx="2" /><line x1="6" y1="6" x2="6.01" y2="6" /><line x1="6" y1="18" x2="6.01" y2="18" /></svg>,
    organization: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 21h18" /><path d="M5 21V7l8-4v18" /><path d="M19 21V11l-6-4" /><path d="M9 9h1" /><path d="M9 13h1" /><path d="M9 17h1" /></svg>,
    identity: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /><path d="M16 11h6M19 8v6" /></svg>,
    settings: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" /></svg>,
};

const PAGE_TITLES = {
    dashboard: 'Dashboard', clients: 'Client Workspace', pipeline: 'Filing Pipeline',
    exceptions: 'Exceptions & Review Queue', documents: 'Document Hub', agent: 'AI Agent Console',
    ingestion: 'Ingestion Hub', airules: 'AI Rules & Configuration', reports: 'Reports & Analytics',
    identity: 'Identity', integrations: 'Integrations', organization: 'Organization', settings: 'Settings',
};

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS — derive pipeline stage from file status + result
// ═══════════════════════════════════════════════════════════════════════════
function getStageFromFile(f, result) {
    if (f.status === 'queued') return 'Queued';
    if (f.status === 'processing') return 'AI Processing';
    if (f.status === 'error') return f.isGate ? 'Gate Rejected' : 'Error';
    if (f.status === 'completed') {
        const excs = result?.exceptions || [];
        const hasFixable = (result?.fixable_exceptions || []).length > 0;
        const hasReview = (result?.review_exceptions || []).length > 0;
        if (excs.length > 0 || hasFixable || hasReview) return 'Exception Review';
        if (result?.needs_review) return 'CPA Review';
        return 'Complete';
    }
    return '—';
}

function getStatusFromFile(f, result) {
    if (f.status === 'queued') return 'pending';
    if (f.status === 'processing') return 'processing';
    if (f.status === 'error') return 'exception';
    if (f.status === 'completed') {
        const excs = (result?.exceptions || []).length + (result?.fixable_exceptions || []).length + (result?.review_exceptions || []).length;
        if (excs > 0) return 'exception';
        return 'approved';
    }
    return 'pending';
}

function confClass(v) {
    if (v === null || v === undefined) return '';
    const p = Math.round(v * 100);
    return p >= 90 ? 'high' : p >= 75 ? 'med' : 'low';
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: DASHBOARD  (live KPIs + live activity feed + live processing card)
// ═══════════════════════════════════════════════════════════════════════════
function PageDashboard({ stats, events, files, results }) {
    // Build a "live processing" ticker from files state
    const activeFiles = files.filter(f => f.status === 'processing' || f.status === 'queued');
    const completedFiles = files.filter(f => f.status === 'completed');
    const errorFiles = files.filter(f => f.status === 'error');
    const totalExceptions = Object.values(results).reduce((n, r) =>
        n + (r?.exceptions?.length || 0) + (r?.fixable_exceptions?.length || 0), 0);

    // Build feed from real events, fall back to static
    const feedItems = events.slice(0, 6).map((e, i) => {
        const isDone = e.type === 'COMPLETE' || e.type === 'SUCCESS';
        const isErr = e.type === 'ERROR' || e.type === 'EXCEPTION';
        return {
            key: i,
            icon: isDone ? 'ready' : isErr ? 'exception' : 'ingest',
            emoji: isDone ? '✓' : isErr ? '⚠' : '📥',
            text: <p>{e.detail || e.type}</p>,
            time: e.timestamp
                ? new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : '—',
            conf: null, confCls: '',
            status: isDone ? 'approved' : isErr ? 'exception' : 'processing',
        };
    });

    const kpis = [
        { label: 'Active Sessions', value: stats.active_sessions ?? 0 },
        { label: 'Events Logged', value: stats.events_logged ?? 0 },
        { label: 'Total Sessions', value: stats.total_sessions ?? 0 },
        { label: 'AI Actions Logged', value: stats.agent_actions_logged ?? 0 },
    ];

    // Stage counts from live files
    const stageCounts = {
        Queued: files.filter(f => f.status === 'queued').length,
        Processing: files.filter(f => f.status === 'processing').length,
        'Exception Review': Object.values(results).filter(r => (r?.exceptions?.length || 0) + (r?.fixable_exceptions?.length || 0) > 0).length,
        Complete: completedFiles.filter(f => {
            const r = results[f.file.name];
            return !((r?.exceptions?.length || 0) + (r?.fixable_exceptions?.length || 0));
        }).length,
    };

    return (
        <>
            {/* KPI row */}
            <div className="kpi-grid">
                {kpis.map((k, i) => (
                    <div key={i} className="kpi-card">
                        <div className="kpi-label">{k.label}</div>
                        <div className="kpi-value">{k.value}</div>
                        <div className="kpi-sub" style={{ color: 'var(--text-muted)' }}>Live from /api/stats</div>
                    </div>
                ))}
            </div>

            {/* Live Processing Banner — shown only when files are active */}
            {files.length > 0 && (
                <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px 20px', marginBottom: 20 }}>
                    <div className="dash-section-title" style={{ marginBottom: 14 }}>
                        <span className="dot" />  Live Processing Status
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: activeFiles.length ? 16 : 0 }}>
                        {[
                            ['📂', 'Uploaded', files.length, null],
                            ['⚙️', 'Processing', activeFiles.length, activeFiles.length > 0 ? '#2563eb' : null],
                            ['✅', 'Complete', completedFiles.length, completedFiles.length > 0 ? 'var(--green)' : null],
                            ['⚠️', 'Exceptions', totalExceptions, totalExceptions > 0 ? 'var(--red)' : null],
                        ].map(([icon, label, count, color]) => (
                            <div key={label} style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '12px 14px', textAlign: 'center', border: '1px solid var(--border)' }}>
                                <div style={{ fontSize: 18, marginBottom: 4 }}>{icon}</div>
                                <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, color: color || 'var(--text-primary)' }}>{count}</div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
                            </div>
                        ))}
                    </div>

                    {/* Per-file stage rows */}
                    {files.map((f, i) => {
                        const r = results[f.file.name];
                        const stage = getStageFromFile(f, r);
                        const status = getStatusFromFile(f, r);
                        const pct = r?.document_confidence !== undefined ? Math.round(r.document_confidence * 100) : null;
                        const stages = ['Queued', 'AI Processing', 'Exception Review', 'CPA Review', 'Complete'];
                        const stageIdx = stages.indexOf(stage);
                        return (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderTop: '1px solid var(--border)' }}>
                                <div style={{ width: 200, flexShrink: 0, fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.file.name}</div>
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                        {stages.map((s, si) => (
                                            <React.Fragment key={s}>
                                                <div style={{
                                                    height: 6, flex: 1, borderRadius: 3,
                                                    background: si < stageIdx ? 'var(--green)'
                                                        : si === stageIdx ? (status === 'exception' ? 'var(--red)' : status === 'processing' ? '#3b82f6' : 'var(--green)')
                                                            : 'var(--surface-3)',
                                                    transition: 'background .4s ease',
                                                }} />
                                                {si < stages.length - 1 && <div style={{ width: 3, flexShrink: 0 }} />}
                                            </React.Fragment>
                                        ))}
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                                        {stages.map((s, si) => (
                                            <div key={s} style={{ fontSize: 9, color: si === stageIdx ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: si === stageIdx ? 600 : 400, flex: 1, textAlign: si === 0 ? 'left' : si === stages.length - 1 ? 'right' : 'center' }}>{s}</div>
                                        ))}
                                    </div>
                                </div>
                                <div style={{ width: 80, flexShrink: 0, textAlign: 'right' }}>
                                    <StatusPill status={status} />
                                </div>
                                {pct !== null && (
                                    <div style={{ width: 36, flexShrink: 0, textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, color: pct >= 90 ? 'var(--green)' : pct >= 75 ? 'var(--amber)' : 'var(--red)' }}>
                                        {pct}%
                                    </div>
                                )}
                                {f.form_type && (
                                    <div style={{ width: 70, flexShrink: 0, fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)', textAlign: 'right' }}>{f.form_type}</div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            <div className="dash-split">
                {/* Activity feed */}
                <div>
                    <div className="dash-section-title"><span className="dot" /> AI Activity Feed</div>
                    <div className="feed-card">
                        {feedItems.length > 0 ? feedItems.map((item, i) => (
                            <div key={item.key ?? i} className="feed-item">
                                <div className={`feed-icon ${item.icon}`}>{item.emoji}</div>
                                <div className="feed-text">
                                    {item.text}
                                    <div className="feed-meta">
                                        <span className="feed-time">{item.time}</span>
                                        {item.conf && <ConfBadge val={item.conf} cls={item.confCls} />}
                                        <StatusPill status={item.status} />
                                    </div>
                                </div>
                            </div>
                        )) : (
                            <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                                <div style={{ fontSize: 24, marginBottom: 8, opacity: .4 }}>📭</div>
                                <div style={{ fontSize: 13 }}>No activity yet</div>
                                <div style={{ fontSize: 12, marginTop: 4 }}>Upload a document from Ingestion Hub to begin</div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right panel */}
                <div>
                    <div className="dash-section-title">Filing Pipeline</div>
                    <div className="donut-card">
                        <div className="donut-wrapper">
                            <svg className="donut-svg" viewBox="0 0 36 36">
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#e2e2e5" strokeWidth="3" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#3b82f6" strokeWidth="3" strokeDasharray="12 88" strokeDashoffset="25" strokeLinecap="round" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#8b5cf6" strokeWidth="3" strokeDasharray="18 82" strokeDashoffset="13" strokeLinecap="round" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#d97706" strokeWidth="3" strokeDasharray="15 85" strokeDashoffset="-5" strokeLinecap="round" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#16a34a" strokeWidth="3" strokeDasharray="20 80" strokeDashoffset="-20" strokeLinecap="round" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#6366f1" strokeWidth="3" strokeDasharray="25 75" strokeDashoffset="-40" strokeLinecap="round" />
                                <circle cx="18" cy="18" r="14" fill="none" stroke="#71717a" strokeWidth="3" strokeDasharray="10 90" strokeDashoffset="-65" strokeLinecap="round" />
                                <text x="18" y="17" textAnchor="middle" fill="#111113" fontFamily="Inter" fontWeight="700" fontSize="6">{files.length}</text>
                                <text x="18" y="22" textAnchor="middle" fill="#8e8e99" fontFamily="Inter" fontSize="2.8">total docs</text>
                            </svg>
                            <div className="donut-legend">
                                {files.length > 0 ? (
                                    Object.entries({
                                        Queued: [stageCounts['Queued'], '#71717a'],
                                        Processing: [stageCounts['Processing'], '#3b82f6'],
                                        'Exception': [Object.values(results).filter(r => (r?.exceptions?.length || 0) + (r?.fixable_exceptions?.length || 0) > 0).length, '#d97706'],
                                        Complete: [stageCounts['Complete'], '#16a34a'],
                                    }).map(([l, [n, c]]) => (
                                        <div key={l} className="legend-item"><div className="legend-dot" style={{ background: c }} />{l}<span>{n}</span></div>
                                    ))
                                ) : (
                                    [['#71717a', 'Ingesting', 0], ['#3b82f6', 'Processing', 0], ['#d97706', 'CPA Review', 0], ['#16a34a', 'Ready to File', 0]].map(([c, l, n]) => (
                                        <div key={l} className="legend-item"><div className="legend-dot" style={{ background: c }} />{l}<span>{n}</span></div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                    <div className="deadlines-card mt-16">
                        <div className="dash-section-title" style={{ marginBottom: 10 }}>Upcoming Deadlines</div>
                        <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                            No deadline data available
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: CLIENTS
// ═══════════════════════════════════════════════════════════════════════════
const CLIENT_DETAIL_TABS = [
    { id: 'summary', label: 'Summary' },
    { id: 'details', label: 'Details' },
    { id: 'documents', label: 'Documents' },
    { id: 'notes', label: 'Notes' },
    { id: 'engagement', label: 'Engagement' },
    { id: 'billing', label: 'Billing' },
    { id: 'activity', label: 'Activity' },
];

function PageClients({ lastExtraction, apiUrl, onUpload, files, results, setResults, checklistReloadTrigger }) {
    const [activeClient, setActiveClient] = useState(0);
    const [activeTab, setActiveTab] = useState('summary');
    const [filter, setFilter] = useState('All');
    const [clients, setClients] = useState(STATIC_CLIENTS);
    const [clientsLoading, setClientsLoading] = useState(true);
    const [ledgerRows, setLedgerRows] = useState([]);
    const [ledgerError, setLedgerError] = useState(null);
    const [selectedDocKey, setSelectedDocKey] = useState(null);
    const [selectedTaxYear, setSelectedTaxYear] = useState(new Date().getFullYear());
    const [checklistRows, setChecklistRows] = useState([]);
    const [checklistPreviousYear, setChecklistPreviousYear] = useState<number | null>(null);
    const [checklistLoading, setChecklistLoading] = useState(false);
    const [checklistError, setChecklistError] = useState('');
    const [showAddFormModal, setShowAddFormModal] = useState(false);
    const [showRemoveModal, setShowRemoveModal] = useState(false);
    const [pendingRemoveForm, setPendingRemoveForm] = useState(null);
    const [availableForms, setAvailableForms] = useState([]);
    const [newFormName, setNewFormName] = useState('');

    // Fetch clients from API on mount
    useEffect(() => {
        const fetchClients = async () => {
            try {
                const res = await fetch(`${apiUrl}/clients?limit=100`);
                if (res.ok) {
                    const data = await res.json();
                    // Map API clients to display format
                    const mappedClients = data.map((c, idx) => ({
                        id: c.id || idx,
                        name: c.entity_type?.toUpperCase() === 'INDIVIDUAL' 
                            ? `${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Unnamed'
                            : c.business_name || c.trust_name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Unnamed',
                        type: c.entity_type || 'Individual',
                        status: 'processing',
                        time: 'just now',
                        fullData: c
                    }));
                    // Combine API clients with static ones (API first)
                    setClients([...mappedClients, ...STATIC_CLIENTS.slice(0, Math.max(0, STATIC_CLIENTS.length - mappedClients.length))]);
                } else {
                    setClients(STATIC_CLIENTS);
                }
            } catch (err) {
                console.error('Failed to fetch clients:', err);
                setClients(STATIC_CLIENTS);
            } finally {
                setClientsLoading(false);
            }
        };
        fetchClients();
    }, [apiUrl]);

    // Same ledger feed as Filing Pipeline — documents often appear here before/without local identity match
    useEffect(() => {
        const base = apiUrl || 'http://localhost:8000';
        let cancelled = false;
        async function fetchLedger() {
            try {
                const res = await fetch(`${base.replace(/\/$/, '')}/ledger/ledger`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                if (!cancelled) {
                    setLedgerRows(Array.isArray(data) ? data : []);
                    setLedgerError(null);
                }
            } catch (e) {
                if (!cancelled) setLedgerError(e.message || 'unreachable');
            }
        }
        fetchLedger();
        const t = setInterval(fetchLedger, 10000);
        return () => { cancelled = true; clearInterval(t); };
    }, [apiUrl]);

    const client = clients[activeClient] || STATIC_CLIENTS[0];

    const clientFiles = useMemo(
        () => files.filter((f) => fileMatchesClient(f, results[f.file.name], client)),
        [files, results, client, activeClient],
    );

    const engagementExtraction = useMemo(() => {
        if (extractionMatchesClient(lastExtraction, client)) return lastExtraction;
        for (let i = files.length - 1; i >= 0; i -= 1) {
            const f = files[i];
            if (f.status !== 'completed') continue;
            const r = results[f.file.name];
            if (r && fileMatchesClient(f, r, client)) return r;
        }
        return null;
    }, [lastExtraction, client, files, results, activeClient]);

    const hasEngagementExceptions = countDedupedExceptions(engagementExtraction) > 0;

    const engagementFileName = useMemo(() => {
        if (!engagementExtraction) return null;
        for (const [fileName, r] of Object.entries(results || {})) {
            if (r === engagementExtraction) return fileName;
        }
        for (let i = files.length - 1; i >= 0; i -= 1) {
            const f = files[i];
            const r = results[f.file.name];
            if (r && r.document_id && engagementExtraction.document_id && r.document_id === engagementExtraction.document_id) {
                return f.file.name;
            }
        }
        return null;
    }, [engagementExtraction, results, files]);

    const clientExceptionTotal = useMemo(
        () => clientFiles.reduce((n, f) => n + countDedupedExceptions(results[f.file.name]), 0),
        [clientFiles, results],
    );

    /** Upload rows + ledger rows for this client (deduped by document_id). */
    const clientDocumentRows = useMemo(() => {
        const rows = [];
        const seenLedgerIds = new Set();

        clientFiles.forEach((f) => {
            const r = results[f.file.name];
            if (r?.document_id) seenLedgerIds.add(r.document_id);
            const exc = countDedupedExceptions(r);
            // Extract tax year from the result data if available
            const extractedYear = r?.data?.tax_year || r?.extracted_fields?.tax_year || null;
            rows.push({
                key: `up:${f.file.name}`,
                kind: 'upload',
                label: f.file.name,
                form: f.form_type || r?.form_type || '—',
                taxYear: extractedYear ? parseInt(extractedYear, 10) : null,
                file: f,
                result: r,
                stage: null,
                ledgerStatus: null,
                exceptions: exc,
                validation: r?.validation_complete
                    ? 'Validated'
                    : (r?.form_type && (exc > 0 || r?.needs_review))
                        ? 'Needs review'
                        : r?.form_type
                            ? 'Pending'
                            : '—',
            });
        });

        ledgerRows.forEach((rec) => {
            if (!ledgerClientNameMatches(client, rec.client_name)) return;
            const docId = rec.document_id;
            if (docId && seenLedgerIds.has(docId)) return;
            const pct = rec.confidence_score != null ? Math.round(rec.confidence_score * 100) : null;
            rows.push({
                key: `ld:${docId || `${rec.client_name}:${rec.document_type}:${rec.stage}`}`,
                kind: 'ledger',
                label: docId ? `${docId}` : (rec.description || 'Document'),
                form: rec.document_type || '—',
                taxYear: rec.tax_year || null,
                file: null,
                result: null,
                stage: rec.stage || '—',
                ledgerStatus: rec.status || '—',
                conf: pct,
                exceptions: null,
                validation: rec.status === 'VALIDATED' ? 'Validated' : 'Pending validation',
                auditTrail: Array.isArray(rec.audit_trail) ? rec.audit_trail : [],
            });
            if (docId) seenLedgerIds.add(docId);
        });

        return rows;
    }, [clientFiles, results, ledgerRows, client, activeClient]);

    const clientActivityRows = useMemo(() => {
        const rows = [];

        // From pipeline/ledger audit trail
        clientDocumentRows
            .filter((r) => r.kind === 'ledger')
            .forEach((row) => {
                (row.auditTrail || []).forEach((a, idx) => {
                    const when = a?.time ? new Date(a.time) : null;
                    const rawStatus = (a?.status || '').toString();
                    const rawType = (a?.type || '').toString();
                    let action = 'Pipeline Update';
                    if (rawType === 'exception_escalated') action = 'Exception Escalated';
                    else if (rawStatus === 'VALIDATED') action = 'Validation Completed';
                    else if (rawStatus === 'EXTRACTED') action = 'Document Ingested';
                    else if (rawStatus) action = rawStatus.replace(/_/g, ' ');
                    rows.push({
                        key: `lg:${row.key}:${idx}`,
                        when,
                        date: when ? when.toLocaleString() : '—',
                        action,
                        actor: rawType === 'exception_escalated' ? 'CPA' : 'System',
                        details: `${row.form} · ${row.label}${a?.stage ? ` · ${a.stage}` : ''}`,
                    });
                });
            });

        // From this browser session uploads (helpful when ledger not yet linked)
        clientFiles.forEach((f, idx) => {
            if (!f?.uploadedAt) return;
            rows.push({
                key: `up:${f.file.name}:${idx}`,
                when: null,
                date: `Today ${f.uploadedAt}`,
                action: 'PDF Uploaded',
                actor: 'User',
                details: `${f.file.name}${f.form_type ? ` · ${f.form_type}` : ''}`,
            });
        });

        // Most recent first; unknown dates at end
        rows.sort((a, b) => {
            if (!a.when && !b.when) return 0;
            if (!a.when) return 1;
            if (!b.when) return -1;
            return b.when - a.when;
        });

        return rows.slice(0, 60);
    }, [clientDocumentRows, clientFiles]);

    const clientSummary = useMemo(() => {
        const stageOrder = {
            'Document Collection': 1,
            'AI Processing': 2,
            'Exception Review': 3,
            'CPA Review': 4,
            'Client Approval': 5,
            'Ready to E-File': 6,
            'Filed & Confirmed': 7,
            'Validation': 2,
        };

        let stage = 'Document Collection';
        let stageRank = 0;
        const confVals = [];
        let validatedCount = 0;
        let needsReviewCount = 0;
        let processedCount = 0;
        let uploadedCount = 0;

        clientDocumentRows.forEach((row) => {
            const rowStage = row.kind === 'ledger'
                ? (row.stage || 'Document Collection')
                : getStageFromFile(row.file, row.result);
            const rank = stageOrder[rowStage] || 0;
            if (rank > stageRank) {
                stageRank = rank;
                stage = rowStage;
            }

            if (row.validation === 'Validated') validatedCount += 1;
            if ((row.exceptions || 0) > 0 || row.validation === 'Needs review') needsReviewCount += 1;
            if (row.kind === 'upload') uploadedCount += 1;
            // "Processed" means the document has entered AI/ledger pipeline and is no longer just collected.
            if (row.kind === 'ledger' || rowStage !== 'Document Collection') processedCount += 1;

            if (row.kind === 'upload') {
                const c = row.result?.document_confidence;
                if (typeof c === 'number') confVals.push(Math.round(c * 100));
            } else if (typeof row.conf === 'number') {
                confVals.push(row.conf);
            }
        });

        const avgConfidence = confVals.length
            ? Math.round(confVals.reduce((a, b) => a + b, 0) / confVals.length)
            : null;
        const totalLinkedDocs = clientDocumentRows.length;

        const latest = clientActivityRows[0] || null;
        const overview = totalLinkedDocs === 0
            ? 'No client documents are linked yet.'
            : `${totalLinkedDocs} document(s) linked. Stage: ${stage}. ${clientExceptionTotal} open exception(s).`;

        return {
            overview,
            stage,
            avgConfidence,
            totalLinkedDocs,
            uploadedCount,
            processedCount,
            validatedCount,
            needsReviewCount,
            latestActivity: latest ? `${latest.action} (${latest.date})` : 'No activity yet',
        };
    }, [clientDocumentRows, clientActivityRows, clientExceptionTotal]);

    const has1040Document = useMemo(
        () => clientDocumentRows.some((row) => normalizeChecklistFormName(row.form) === '1040'),
        [clientDocumentRows],
    );

    const loadChecklist = useCallback(async () => {
        if (!client?.fullData?.id) {
            setChecklistRows([]);
            setChecklistError('');
            return;
        }
        setChecklistLoading(true);
        setChecklistError('');
        try {
            const res = await fetch(`${apiUrl}/clients/${client.fullData.id}/document-checklist?tax_year=${selectedTaxYear}`);
            const data = await res.json();
            if (res.status === 404) {
                setChecklistRows([]);
                return;
            }
            if (!res.ok) throw new Error(data?.detail || data?.error || `HTTP ${res.status}`);
            setChecklistRows(Array.isArray(data?.forms) ? data.forms : []);
            setChecklistPreviousYear(data?.previous_year ?? null);
        } catch (err) {
            setChecklistRows([]);
            setChecklistError(normalizeChecklistErrorMessage(err) || 'Failed to load checklist.');
        } finally {
            setChecklistLoading(false);
        }
    // checklistReloadTrigger intentionally included so FDR derive → reload works
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [apiUrl, client?.fullData?.id, selectedTaxYear, checklistReloadTrigger]);

    useEffect(() => {
        loadChecklist();
    }, [loadChecklist]);

    useEffect(() => {
        setChecklistError('');
    }, [activeClient]);

    useEffect(() => {
        if (!showAddFormModal) return;
        fetch(`${apiUrl}/forms`)
            .then((r) => r.json())
            .then((data) => {
                const forms = Array.isArray(data?.forms) ? data.forms : [];
                setAvailableForms(forms.map((f) => normalizeChecklistFormName(f)));
            })
            .catch(() => setAvailableForms([]));
    }, [apiUrl, showAddFormModal]);

    const handleChecklistAdd = useCallback(async (formName) => {
        const form = normalizeChecklistFormName(formName);
        if (!form || !client?.fullData?.id) return;
        try {
            const res = await fetch(`${apiUrl}/clients/${client.fullData.id}/document-checklist/forms?tax_year=${selectedTaxYear}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ form_name: form }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data?.detail || data?.error || 'Failed to add form');
            setChecklistRows(Array.isArray(data?.forms) ? data.forms : []);
            if (data?.previous_year) setChecklistPreviousYear(data.previous_year);
            setShowAddFormModal(false);
            setNewFormName('');
        } catch (err) {
            setChecklistError(normalizeChecklistErrorMessage(err) || 'Failed to add form');
        }
    }, [apiUrl, client?.fullData?.id, selectedTaxYear]);

    const handleChecklistRemove = useCallback(async (row) => {
        if (!client?.fullData?.id || !row?.form_name) return;
        try {
            const encoded = encodeURIComponent(row.form_name);
            const res = await fetch(`${apiUrl}/clients/${client.fullData.id}/document-checklist/forms/${encoded}?tax_year=${selectedTaxYear}`, {
                method: 'DELETE',
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data?.detail || data?.error || 'Failed to remove form');
            setChecklistRows(Array.isArray(data?.forms) ? data.forms : []);
            if (data?.previous_year) setChecklistPreviousYear(data.previous_year);
        } catch (err) {
            setChecklistError(normalizeChecklistErrorMessage(err) || 'Failed to remove form');
        } finally {
            setShowRemoveModal(false);
            setPendingRemoveForm(null);
        }
    }, [apiUrl, client?.fullData?.id, selectedTaxYear]);

    const [clientAISummaryText, setClientAISummaryText] = useState('');
    const [clientAISummaryLoading, setClientAISummaryLoading] = useState(false);

    useEffect(() => {
        if (!client?.name) return;
        const docs = clientDocumentRows;
        const formSet = new Set(docs.map((d) => String(d.form || '').toUpperCase()).filter(Boolean));
        const escalations = clientActivityRows.filter((a) => a.action === 'Exception Escalated').length;
        const completedUploads = clientFiles.filter((f) => f.status === 'completed').length;

        setClientAISummaryText('');
        setClientAISummaryLoading(true);
        const controller = new AbortController();

        fetch(`${apiUrl}/client-summary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: controller.signal,
            body: JSON.stringify({
                client_name: client.name,
                stage: clientSummary.stage,
                total_docs: docs.length,
                validated_count: clientSummary.validatedCount,
                needs_review_count: clientSummary.needsReviewCount,
                avg_confidence: clientSummary.avgConfidence,
                exception_total: clientExceptionTotal,
                escalation_count: escalations,
                form_types: Array.from(formSet),
                completed_uploads: completedUploads,
            }),
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.status === 'ok' && data.summary_text) {
                    setClientAISummaryText(data.summary_text);
                } else {
                    setClientAISummaryText(`Error: ${data.error || 'Could not generate summary.'}`);
                }
            })
            .catch((err) => {
                if (err?.name === 'AbortError') return;
                setClientAISummaryText(`Error: ${err?.message || 'Failed to connect to backend.'}`);
            })
            .finally(() => setClientAISummaryLoading(false));

        return () => controller.abort();
    }, [client.name, clientSummary.stage, clientSummary.validatedCount, clientExceptionTotal]);

    const summaryStepIndex = useMemo(() => {
        const m = {
            'Document Collection': 0,
            'AI Processing': 1,
            'Validation': 1,
            'Exception Review': 2,
            'CPA Review': 2,
            'Client Approval': 3,
            'Ready to E-File': 4,
            'E-File': 4,
            'Filed & Confirmed': 5,
            'Confirmed': 5,
        };
        return m[clientSummary.stage] ?? 0;
    }, [clientSummary.stage]);

    const selectedDocumentRow = useMemo(
        () => clientDocumentRows.find((r) => r.key === selectedDocKey) || null,
        [clientDocumentRows, selectedDocKey],
    );

    const selectedDocumentJson = useMemo(() => {
        if (!selectedDocumentRow) return null;
        if (selectedDocumentRow.kind === 'upload') {
            const r = selectedDocumentRow.result || {};
            return r.data || r.extracted_fields || {};
        }
        return null;
    }, [selectedDocumentRow]);

    useEffect(() => {
        setSelectedDocKey(null);
    }, [activeClient]);

    // When 'Add Client' is selected show the form panel instead of the detail view
    if (filter === 'Add Client') {
        return (
            <div className="client-split" style={{ flex: 1, height: '100%', overflow: 'hidden', minWidth: 0 }}>
                {/* Left: client list (static) */}
                <div className="client-list">
                    <div className="client-list-header">
                        <input type="text" placeholder="Search clients…" />
                        <div className="filter-chips" style={{ marginTop: 10 }}>
                            {['All', 'Active', 'Enquiry', 'Add Client'].map(f => (
                                <span key={f} className={`filter-chip${filter === f ? ' active' : ''}`} onClick={() => setFilter(f)}>{f}</span>
                            ))}
                        </div>
                    </div>
                    {clients.map((c, i) => (
                        <div key={c.id} className={`client-card${activeClient === i ? ' active' : ''}`}
                            onClick={() => { setActiveClient(i); setFilter('All'); setActiveTab('summary'); }}>
                            <div className="client-card-name">{c.name} <span className="entity-badge">{c.type}</span></div>
                            <div className="client-card-meta"><StatusPill status={c.status} /><span>{c.time}</span></div>
                        </div>
                    ))}
                </div>

                {/* Right: Add Client form */}
                <div className="client-detail" style={{ overflowY: 'auto' }}>
                    <div className="client-header" style={{ marginBottom: 0 }}>
                        <h2 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{
                                width: 32, height: 32, borderRadius: '50%', background: 'rgba(99,102,241,.15)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: 16,
                            }}>+</span>
                            Add New Client
                        </h2>
                        <div className="client-header-actions">
                            <button className="btn btn-primary" type="submit" form="add-client-form">Save Client</button>
                        </div>
                    </div>

                    {/* Divider */}
                    <div style={{ height: 1, background: 'var(--border)', margin: '16px 0' }} />

                    <AddClientForm
                        apiUrl={apiUrl}
                        onSuccess={async () => {
                            // Refresh the client list after adding a new client
                            setClientsLoading(true);
                            try {
                                const res = await fetch(`${apiUrl}/clients?limit=100`);
                                if (res.ok) {
                                    const data = await res.json();
                                    const mappedClients = data.map((c, idx) => ({
                                        id: c.id || idx,
                                        name: c.entity_type?.toUpperCase() === 'INDIVIDUAL' 
                                            ? `${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Unnamed'
                                            : c.business_name || c.trust_name || `${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Unnamed',
                                        type: c.entity_type || 'Individual',
                                        status: 'processing',
                                        time: 'just now',
                                        fullData: c
                                    }));
                                    setClients(mappedClients);
                                    setActiveClient(Math.max(0, mappedClients.length - 1));
                                }
                            } catch (err) {
                                console.error('Failed to refresh clients:', err);
                            } finally {
                                setClientsLoading(false);
                                setFilter('All');
                            }
                        }}
                        onCancel={() => setFilter('All')}
                    />
                </div>
            </div>
        );
    }

    return (
        <div className="client-split" style={{ flex: 1, height: '100%', overflow: 'hidden', minWidth: 0 }}>
            <div className="client-list">
                <div className="client-list-header">
                    <input type="text" placeholder="Search clients…" />
                    <div className="filter-chips" style={{ marginTop: 10 }}>
                        {['All', 'Active', 'Enquiry', 'Add Client'].map(f => (
                            <span key={f} className={`filter-chip${filter === f ? ' active' : ''}`} onClick={() => setFilter(f)}>{f}</span>
                        ))}
                    </div>
                </div>
                {clients.map((c, i) => (
                    <div key={c.id} className={`client-card${activeClient === i ? ' active' : ''}`} onClick={() => { setActiveClient(i); setActiveTab('summary'); }}>
                        <div className="client-card-name">{c.name} <span className="entity-badge">{c.type}</span></div>
                        <div className="client-card-meta"><StatusPill status={c.status} /><span>{c.time}</span></div>
                    </div>
                ))}

            </div>
            <div className="client-detail">
                <div className="client-header">
                    <h2>{client.name} <span className="entity-badge" style={{ fontSize: 12 }}>{client.type}</span></h2>
                    <div className="client-header-actions">
                        <select style={{ fontSize: 12 }} value={`TY ${selectedTaxYear}`} onChange={(e) => setSelectedTaxYear(Number(String(e.target.value).replace('TY ', '')))}>
                            {[selectedTaxYear, selectedTaxYear - 1, selectedTaxYear - 2].map((y) => (
                                <option key={y} value={`TY ${y}`}>{`TY ${y}`}</option>
                            ))}
                        </select>
                        <button className="btn btn-secondary">Generate Portal Link</button>
                        <button className="btn btn-primary">Begin CPA Review</button>
                    </div>
                </div>
                <div className="tab-bar">
                    {CLIENT_DETAIL_TABS.map(({ id, label }) => (
                        <div key={id} className={`tab-item${activeTab === id ? ' active' : ''}`} onClick={() => setActiveTab(id)}>
                            {label}
                        </div>
                    ))}
                </div>
                {activeTab === 'summary' && (
                    <div>
                        <div className="stepper">
                            {['Document Collection', 'AI Processing', 'CPA Review', 'Client Approval', 'E-File', 'Confirmed'].map((s, i) => (
                                <React.Fragment key={s}>
                                    <div className={`step${i < summaryStepIndex ? ' completed' : i === summaryStepIndex ? ' current' : ''}`}>
                                        <div className="step-dot">{i < summaryStepIndex ? '✓' : i + 1}</div>
                                        <div className="step-label">{s}</div>
                                    </div>
                                    {i < 5 && <div className={`step-line${i < summaryStepIndex ? ' done' : ''}`} />}
                                </React.Fragment>
                            ))}
                        </div>
                        <div className="key-figures">
                            {[['Documents Linked', clientSummary.totalLinkedDocs, null, ''], ['Processed', clientSummary.processedCount, 'green', ''], ['Exceptions', clientExceptionTotal, 'red', '']].map(([l, v, c, s]) => (
                                <div key={l} className="key-fig">
                                    <div className="key-fig-label">{l}</div>
                                    <div className="key-fig-value" style={c ? { color: `var(--${c})` } : {}}>{v}</div>
                                    <div className="key-fig-sub">{s}</div>
                                </div>
                            ))}
                        </div>
                        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                            {[
                                ['Current Stage', clientSummary.stage],
                                ['Average Confidence', clientSummary.avgConfidence !== null ? `${clientSummary.avgConfidence}%` : '—'],
                                ['Validated Documents', String(clientSummary.validatedCount)],
                                ['Needs Review', String(clientSummary.needsReviewCount)],
                                ['Latest Activity', clientSummary.latestActivity],
                            ].map(([label, value]) => (
                                <div key={label} style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 12 }}>
                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 6 }}>{label}</div>
                                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 600 }}>{value}</div>
                                </div>
                            ))}
                        </div>
                        <div style={{ marginTop: 16, background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 14 }}>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                                Summary
                                {clientAISummaryLoading && <span style={{ fontSize: 10, color: 'var(--amber)', fontWeight: 600, animation: 'pulse 1.5s infinite' }}>✦ Generating…</span>}
                            </div>
                            {clientAISummaryLoading && !clientAISummaryText ? (
                                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>AI is generating summary…</div>
                            ) : clientAISummaryText ? (
                                <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                                    {clientAISummaryText.split('\n').map((line, i) => {
                                        const trimmed = line.trim();
                                        if (!trimmed) return null;
                                        // Render **bold title** line
                                        if (trimmed.startsWith('**') && trimmed.endsWith('**')) {
                                            return <div key={i} style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 8 }}>{trimmed.replace(/\*\*/g, '')}</div>;
                                        }
                                        // Render bullet lines (• or -)
                                        if (trimmed.startsWith('•') || trimmed.startsWith('-')) {
                                            return <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 4 }}><span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>•</span><span>{trimmed.replace(/^[•\-]\s*/, '')}</span></div>;
                                        }
                                        return <div key={i} style={{ marginBottom: 4 }}>{trimmed}</div>;
                                    })}
                                </div>
                            ) : null}
                        </div>
                    </div>
                )}
                {activeTab === 'details' && (
                    <div style={{ padding: '20px' }}>
                        {client.fullData ? (
                            <div>
                                {/* Personal/Business Info Section */}
                                <div style={{ marginBottom: 24 }}>
                                    <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '.05em' }}>Client Information</h3>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px 24px', background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
                                        {/* Entity Type */}
                                        <div>
                                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Entity Type</div>
                                            <div style={{ fontSize: 13, fontWeight: 500 }}>{client.fullData.entity_type || client.type || '—'}</div>
                                        </div>

                                        {/* Name Fields */}
                                        {client.fullData.first_name && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>First Name</div>
                                                <div style={{ fontSize: 13 }}>{client.fullData.first_name}</div>
                                            </div>
                                        )}
                                        {client.fullData.last_name && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Last Name</div>
                                                <div style={{ fontSize: 13 }}>{client.fullData.last_name}</div>
                                            </div>
                                        )}
                                        {client.fullData.business_name && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Business Name</div>
                                                <div style={{ fontSize: 13 }}>{client.fullData.business_name}</div>
                                            </div>
                                        )}

                                        {/* Contact Information */}
                                        {client.fullData.email && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Email</div>
                                                <div style={{ fontSize: 13 }}><a href={`mailto:${client.fullData.email}`} style={{ color: '#3b82f6', textDecoration: 'none' }}>{client.fullData.email}</a></div>
                                            </div>
                                        )}
                                        {client.fullData.phone && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Phone</div>
                                                <div style={{ fontSize: 13 }}><a href={`tel:${client.fullData.phone}`} style={{ color: '#3b82f6', textDecoration: 'none' }}>{client.fullData.phone}</a></div>
                                            </div>
                                        )}

                                        {/* Tax Identification */}
                                        {client.fullData.tax_id && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Tax ID</div>
                                                <div style={{ fontSize: 13, fontFamily: 'monospace' }}>••-{client.fullData.tax_id.slice(-7)}</div>
                                            </div>
                                        )}
                                        {client.fullData.ssn && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>SSN</div>
                                                <div style={{ fontSize: 13, fontFamily: 'monospace' }}>•••-••-{client.fullData.ssn.replace(/\D/g, '').slice(-4)}</div>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Address Information Section */}
                                <div style={{ marginBottom: 24 }}>
                                    <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '.05em' }}>Address</h3>
                                    <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px 24px' }}>
                                            {client.fullData.address_line1 && (
                                                <div style={{ gridColumn: '1 / -1' }}>
                                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Street Address</div>
                                                    <div style={{ fontSize: 13 }}>
                                                        {client.fullData.address_line1}
                                                        {client.fullData.address_line2 && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{client.fullData.address_line2}</div>}
                                                    </div>
                                                </div>
                                            )}
                                            {client.fullData.city && (
                                                <div>
                                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>City</div>
                                                    <div style={{ fontSize: 13 }}>{client.fullData.city}</div>
                                                </div>
                                            )}
                                            {client.fullData.state && (
                                                <div>
                                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>State</div>
                                                    <div style={{ fontSize: 13 }}>{client.fullData.state}</div>
                                                </div>
                                            )}
                                            {client.fullData.zip_code && (
                                                <div>
                                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>ZIP Code</div>
                                                    <div style={{ fontSize: 13 }}>{client.fullData.zip_code}</div>
                                                </div>
                                            )}
                                            {client.fullData.country && (
                                                <div>
                                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Country</div>
                                                    <div style={{ fontSize: 13 }}>{client.fullData.country}</div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Profile & Status Section */}
                                <div>
                                    <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '.05em' }}>Profile & Status</h3>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px 24px', background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
                                        {client.fullData.lifecycle_stage && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Lifecycle Stage</div>
                                                <div style={{ fontSize: 13 }}>{client.fullData.lifecycle_stage}</div>
                                            </div>
                                        )}
                                        {client.fullData.risk_profile && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Risk Profile</div>
                                                <div style={{ fontSize: 13, color: client.fullData.risk_profile === 'HIGH' ? 'var(--red)' : client.fullData.risk_profile === 'MEDIUM' ? 'var(--amber)' : 'var(--green)' }}>{client.fullData.risk_profile}</div>
                                            </div>
                                        )}
                                        {client.fullData.industry && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Industry</div>
                                                <div style={{ fontSize: 13 }}>{client.fullData.industry}</div>
                                            </div>
                                        )}
                                        {client.fullData.preferred_currency && (
                                            <div>
                                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Preferred Currency</div>
                                                <div style={{ fontSize: 13 }}>{client.fullData.preferred_currency}</div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                                <div style={{ fontSize: 24, marginBottom: 8, opacity: .4 }}>ℹ️</div>
                                No client details available.
                            </div>
                        )}
                    </div>
                )}
                {activeTab === 'documents' && (
                    <div style={{ display: 'flex', gap: 18, alignItems: 'flex-start', minWidth: 0 }}>
                        <div style={{ flex: 1, minWidth: 0, overflowX: 'auto' }}>
                        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 12px', lineHeight: 1.5 }}>
                            Includes <strong>this browser&apos;s uploads</strong> matched by extracted name/TIN, plus <strong>filing pipeline / ledger</strong> rows where the ledger client name matches this record.
                            {ledgerError && (
                                <span style={{ color: 'var(--amber)', marginLeft: 8 }}>(Ledger API: {ledgerError})</span>
                            )}
                        </p>
                        <table className="data-table">
                            <thead><tr><th>Document</th><th>Type</th><th>Status</th><th>Confidence</th><th>Exceptions</th><th>Validation</th><th>Stage</th></tr></thead>
                            <tbody>
                                {clientDocumentRows.length > 0 ? clientDocumentRows.map((row) => {
                                    const hasExtractedJson = row.kind === 'upload' && !!(row.result?.data || row.result?.extracted_fields);
                                    const is1040Row = normalizeChecklistFormName(row.form) === '1040';
                                    const isClickable = hasExtractedJson || is1040Row;
                                    return (
                                    <tr
                                        key={row.key}
                                        onClick={() => {
                                            if (!isClickable) return;
                                            const nextKey = selectedDocKey === row.key ? null : row.key;
                                            setSelectedDocKey(nextKey);
                                            // When opening a 1040 row, snap the checklist year to that 1040's tax year
                                            if (nextKey && is1040Row && row.taxYear) {
                                                setSelectedTaxYear(row.taxYear);
                                            }
                                        }}
                                        style={{
                                            cursor: isClickable ? 'pointer' : 'default',
                                            background: selectedDocKey === row.key
                                                ? is1040Row ? 'rgba(59,130,246,.08)' : 'var(--surface-1)'
                                                : undefined,
                                        }}
                                        title={is1040Row ? 'Click to open Document Checklist' : hasExtractedJson ? 'Click to view extracted JSON' : ''}
                                    >
                                        <td style={{ fontWeight: 500, maxWidth: 220 }} title={row.label}>{row.label}</td>
                                        <td className="mono">{row.form}</td>
                                        <td>
                                            {row.kind === 'upload'
                                                ? <StatusPill status={getStatusFromFile(row.file, row.result)} />
                                                : (
                                                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{row.ledgerStatus}</span>
                                                )}
                                        </td>
                                        <td>
                                            {row.kind === 'upload' ? (
                                                <span className={`confidence-badge ${confClass(row.result?.document_confidence)}`}>
                                                    {row.result?.document_confidence != null ? `${Math.round(row.result.document_confidence * 100)}%` : '—'}
                                                </span>
                                            ) : (
                                                <span className={`confidence-badge ${row.conf != null ? confClass(row.conf / 100) : ''}`}>{row.conf != null ? `${row.conf}%` : '—'}</span>
                                            )}
                                        </td>
                                        <td style={{ fontWeight: 600, color: row.exceptions > 0 ? 'var(--red)' : 'var(--text-muted)', fontSize: 13 }}>
                                            {row.exceptions !== null && row.exceptions !== undefined ? row.exceptions : '—'}
                                        </td>
                                        <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{row.validation}</td>
                                        <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{row.kind === 'ledger' ? (row.stage || '—') : '—'}</td>
                                    </tr>
                                    );
                                }) : (
                                    <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)', fontSize: 12 }}>No documents for this client yet. Confirm the client name matches the ledger, or upload in Ingestion Hub.</td></tr>
                                )}
                            </tbody>
                        </table>
                        {selectedDocumentJson && (
                            <div style={{ marginTop: 16 }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                                    <div style={{ fontSize: 13, fontWeight: 700 }}>
                                        Extracted Document JSON — {selectedDocumentRow?.label}
                                    </div>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        style={{ fontSize: 11 }}
                                        onClick={() => setSelectedDocKey(null)}
                                    >
                                        Close
                                    </button>
                                </div>
                                <pre
                                    style={{
                                        margin: 0,
                                        padding: 14,
                                        maxHeight: 360,
                                        overflow: 'auto',
                                        fontSize: 12,
                                        lineHeight: 1.5,
                                        background: 'var(--surface-1)',
                                        border: '1px solid var(--border)',
                                        borderRadius: 'var(--radius)',
                                        fontFamily: 'var(--font-mono)',
                                    }}
                                >
                                    {JSON.stringify(selectedDocumentJson, null, 2)}
                                </pre>
                            </div>
                        )}
                        </div>
                        {client?.fullData?.id && selectedDocumentRow && normalizeChecklistFormName(selectedDocumentRow.form) === '1040' && (
                            <div style={{ width: 440, flex: '0 0 440px', minWidth: 440, position: 'relative', zIndex: 2, background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 14, boxShadow: '0 1px 2px rgba(15,23,42,.04)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                                    <div style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em', fontWeight: 700 }}>
                                        Document Checklist — TY {selectedTaxYear}
                                    </div>
                                    <button className="btn btn-secondary" style={{ fontSize: 11 }} onClick={() => setShowAddFormModal(true)}>Add Form</button>
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.35 }}>
                                    {has1040Document
                                        ? 'FDR-derived from 1040. Confirmed = line value present. Inferred = probable. Ask = needs confirmation.'
                                        : 'Upload and associate a 1040 to auto-derive required forms, or add manually.'}
                                </div>
                                <div style={{ overflowX: 'auto' }}>
                                <table className="data-table" style={{ marginBottom: 0, minWidth: 380 }}>
                                    <thead>
                                        <tr>
                                            <th>Forms</th>
                                            <th style={{ textAlign: 'center' }}>Count</th>
                                            <th>Status</th>
                                            <th>Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {checklistLoading ? (
                                            <tr><td colSpan={4} style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 18 }}>Loading checklist...</td></tr>
                                        ) : checklistRows.length === 0 ? (
                                            <tr><td colSpan={4} style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 18 }}>
                                                {has1040Document
                                                    ? 'Upload detected but checklist not yet derived. Re-associate the 1040 to auto-populate, or use Add Form.'
                                                    : 'No forms yet. Upload a 1040 in Ingestion Hub and associate it with this client to auto-populate, or use Add Form.'}
                                            </td></tr>
                                        ) : checklistRows
                                            .filter(row => {
                                                // Never show the return form itself in the supporting-docs checklist
                                                const n = (row.form_name || '').toUpperCase();
                                                return !['1040','1040-SR','1040-NR','1040-NR-EZ','1040-X','1040-ES','1040-V'].includes(n);
                                            })
                                            .map((row) => {
                                            // Confidence dot: green = deterministic, amber = inferred, grey = unresolvable/manual
                                            const dotColor = row.confidence === 'deterministic'
                                                ? '#10b981'
                                                : row.confidence === 'inferred'
                                                    ? '#f59e0b'
                                                    : '#9ca3af';
                                            const dotTitle = row.confidence === 'deterministic'
                                                ? `Confirmed — ${row.trigger_line} = ${row.trigger_value}`
                                                : row.confidence === 'inferred'
                                                    ? `Inferred — ${row.trigger_line} = ${row.trigger_value}`
                                                    : row.confidence === 'unresolvable'
                                                        ? 'Needs client confirmation'
                                                        : 'Manually added';
                                            const pyCount = row.prior_year_count || 0;
                                            const pyYear  = checklistPreviousYear;
                                            return (
                                            <tr key={row.form_name}>
                                                <td style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <span
                                                        title={dotTitle}
                                                        style={{
                                                            width: 7, height: 7, borderRadius: '50%',
                                                            background: dotColor, flexShrink: 0,
                                                            cursor: 'default',
                                                        }}
                                                    />
                                                    <span className="mono" style={{ fontWeight: 500 }}>{row.form_name}</span>
                                                    {pyCount > 0 && pyYear && (
                                                        <span title={`Filed ${pyCount}× in ${pyYear}`} style={{
                                                            fontSize: 9, fontWeight: 700, padding: '1px 5px',
                                                            borderRadius: 4, background: 'rgba(156,163,175,.18)',
                                                            color: 'var(--text-muted)', letterSpacing: '.02em',
                                                            whiteSpace: 'nowrap',
                                                        }}>
                                                            {pyYear}↑{pyCount > 1 ? `×${pyCount}` : ''}
                                                        </span>
                                                    )}
                                                </td>
                                                <td style={{ textAlign: 'center', fontWeight: 700, fontSize: 13 }}>
                                                    {row.count ?? 1}
                                                </td>
                                                <td>
                                                    <span
                                                        style={{
                                                            fontSize: 11,
                                                            fontWeight: 700,
                                                            display: 'inline-flex',
                                                            alignItems: 'center',
                                                            padding: '3px 8px',
                                                            borderRadius: 999,
                                                            border: '1px solid var(--border)',
                                                            background: row.status === 'Error'
                                                                ? 'rgba(239,68,68,.12)'
                                                                : row.status === 'Pending'
                                                                    ? 'rgba(156,163,175,.14)'
                                                                    : row.status === 'Partial'
                                                                        ? 'rgba(245,158,11,.15)'
                                                                        : 'rgba(16,185,129,.15)',
                                                            color: row.status === 'Error'
                                                                ? 'var(--red)'
                                                                : row.status === 'Pending'
                                                                    ? 'var(--text-muted)'
                                                                    : row.status === 'Partial'
                                                                        ? 'var(--amber)'
                                                                        : 'var(--green)',
                                                        }}
                                                    >
                                                        {row.status}
                                                    </span>
                                                </td>
                                                <td style={{ display: 'flex', gap: 6, whiteSpace: 'nowrap' }}>
                                                    <button className="btn btn-primary" style={{ fontSize: 11, padding: '4px 9px' }} onClick={() => handleChecklistAdd(row.form_name)}>Add</button>
                                                    <button
                                                        className="btn btn-secondary"
                                                        style={{ fontSize: 11, padding: '4px 9px', color: 'var(--red)', borderColor: 'rgba(239,68,68,.35)' }}
                                                        onClick={() => {
                                                            if ((row.count || 1) <= 1) {
                                                                setPendingRemoveForm(row);
                                                                setShowRemoveModal(true);
                                                            } else {
                                                                handleChecklistRemove(row);
                                                            }
                                                        }}
                                                    >
                                                        Remove
                                                    </button>
                                                </td>
                                            </tr>
                                        );
                                        })}
                                    </tbody>
                                </table>
                                </div>
                                {checklistError && (
                                    <div style={{ marginTop: 10, fontSize: 11, color: 'var(--red)', background: 'rgba(239,68,68,.08)', border: '1px solid rgba(239,68,68,.25)', borderRadius: 8, padding: '6px 8px' }}>
                                        {checklistError}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
                {activeTab === 'notes' && (
                    <div>
                        <textarea style={{ width: '100%', minHeight: 200, resize: 'vertical', fontSize: 13, lineHeight: 1.6, padding: 16, background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', outline: 'none' }} defaultValue="Add notes about this client…" />
                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}><button className="btn btn-primary">Save Notes</button></div>
                    </div>
                )}
                {activeTab === 'engagement' && (
                    <div>
                        {!engagementExtraction ? (
                            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                                <div style={{ fontSize: 24, marginBottom: 8, opacity: .4 }}>📄</div>
                                <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>No extraction for this client yet</div>
                                <div style={{ maxWidth: 420, margin: '0 auto', lineHeight: 1.5 }}>
                                    Engagement shows validation from <strong>Ingestion Hub</strong> when the extracted name or TIN matches this client.
                                    Upload their forms there, or check that the client name in your database matches the return.
                                </div>
                            </div>
                        ) : hasEngagementExceptions ? (
                            <ExceptionManager
                                apiUrl={apiUrl} formType={engagementExtraction?.form_type || 'Unknown'}
                                data={engagementExtraction?.data || {}}
                                fixableExceptions={engagementExtraction?.fixable_exceptions || []}
                                reviewExceptions={engagementExtraction?.review_exceptions || []}
                                allExceptions={engagementExtraction?.exceptions || []} summary={engagementExtraction?.summary || {}}
                                humanVerifiedFields={engagementExtraction?.human_verified_fields || []}
                                showSidePdf={false} setShowSidePdf={() => { }}
                                onResolved={(updated) => {
                                    if (!setResults || !engagementFileName || !updated || typeof updated !== 'object') return;
                                    setResults(prev => ({
                                        ...prev,
                                        [engagementFileName]: {
                                            ...(prev[engagementFileName] || {}),
                                            ...updated,
                                        },
                                    }));
                                }}
                                ignoredIds={engagementExtraction?.ignoredIds || new Set()}
                                setIgnoredIds={(fn) => {
                                    if (!setResults || !engagementFileName) return;
                                    setResults(prev => {
                                        const cur = prev[engagementFileName] || {};
                                        const next = typeof fn === 'function'
                                            ? fn(cur.ignoredIds || new Set())
                                            : fn;
                                        return {
                                            ...prev,
                                            [engagementFileName]: { ...cur, ignoredIds: next },
                                        };
                                    });
                                }}
                            />
                        ) : (
                            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                                <div style={{ fontSize: 24, marginBottom: 8, opacity: .4 }}>✅</div>
                                No exceptions found for this client&apos;s documents.
                            </div>
                        )}
                    </div>
                )}
                {activeTab === 'billing' && (
                    <div style={{ padding: '20px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16, marginBottom: 20 }}>
                            {[
                                ['Engagement fee', '—', 'Per return / scope'],
                                ['Hours (YTD)', '—', 'Billable vs actual'],
                                ['Outstanding', '$0.00', 'Invoices not paid'],
                            ].map(([label, value, sub]) => (
                                <div key={label} style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 16 }}>
                                    <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 8 }}>{label}</div>
                                    <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
                                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>
                                </div>
                            ))}
                        </div>
                        <table className="data-table">
                            <thead><tr><th>Invoice</th><th>Period</th><th>Amount</th><th>Status</th></tr></thead>
                            <tbody>
                                <tr><td colSpan={4} style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)', fontSize: 13 }}>No invoices linked to this client yet.</td></tr>
                            </tbody>
                        </table>
                    </div>
                )}
                {activeTab === 'activity' && (
                    <div>
                        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 12px' }}>
                            Activity includes ledger/pipeline audit events and uploads from this browser session.
                            Password/account events are not available in the current backend yet.
                        </p>
                        <table className="data-table">
                            <thead><tr><th>Date</th><th>Action</th><th>Actor</th><th>Details</th></tr></thead>
                            <tbody>
                                {clientActivityRows.length > 0 ? clientActivityRows.map((row) => (
                                    <tr key={row.key}>
                                        <td className="mono">{row.date}</td>
                                        <td>{row.action}</td>
                                        <td>{row.actor}</td>
                                        <td style={{ color: 'var(--text-muted)' }}>{row.details}</td>
                                    </tr>
                                )) : (
                                    <tr>
                                        <td colSpan={4} style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)', fontSize: 12 }}>
                                            No activity history found for this client yet.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
            {showAddFormModal && (() => {
                const existingForms = new Set(checklistRows.map(r => normalizeChecklistFormName(r.form_name)));
                const searchVal = newFormName.trim().toUpperCase();
                const filtered = availableForms.filter(f =>
                    !searchVal || f.toUpperCase().includes(searchVal)
                );
                return (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(17,24,39,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}
                    onClick={(e) => { if (e.target === e.currentTarget) { setShowAddFormModal(false); setNewFormName(''); } }}>
                    <div style={{ width: 420, maxWidth: '92vw', background: 'var(--surface-0)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20, display: 'flex', flexDirection: 'column', maxHeight: '80vh' }}>
                        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Add Form</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                            Select a form to add. If it already exists in the checklist, its count will increase.
                        </div>
                        {/* Search */}
                        <input
                            autoFocus
                            value={newFormName}
                            onChange={(e) => setNewFormName(e.target.value)}
                            placeholder="Search or type a form name…"
                            style={{ width: '100%', fontSize: 12, padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--surface-1)', color: 'var(--text-primary)', marginBottom: 8, boxSizing: 'border-box' }}
                        />
                        {/* Form list */}
                        <div style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8, background: 'var(--surface-1)' }}>
                            {filtered.length === 0 && searchVal ? (
                                /* typed a custom name not in the list — offer to add it */
                                <div
                                    onClick={() => handleChecklistAdd(newFormName)}
                                    style={{ padding: '10px 14px', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-primary)' }}
                                    onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-2)'}
                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                >
                                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{searchVal}</span>
                                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>— add as new form</span>
                                </div>
                            ) : (
                                filtered.map((f) => {
                                    const alreadyIn = existingForms.has(normalizeChecklistFormName(f));
                                    return (
                                        <div
                                            key={f}
                                            onClick={() => handleChecklistAdd(f)}
                                            style={{ padding: '10px 14px', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border)' }}
                                            onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-2)'}
                                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                        >
                                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{f}</span>
                                            {alreadyIn && (
                                                <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--surface-3)', borderRadius: 4, padding: '2px 6px' }}>
                                                    in checklist — will increment
                                                </span>
                                            )}
                                        </div>
                                    );
                                })
                            )}
                        </div>
                        <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => { setShowAddFormModal(false); setNewFormName(''); }}>Cancel</button>
                        </div>
                    </div>
                </div>
                );
            })()}
            {showRemoveModal && pendingRemoveForm && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(17,24,39,.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
                    <div style={{ width: 420, maxWidth: '92vw', background: 'var(--surface-0)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 24 }}>
                        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>Remove Form</div>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20, lineHeight: 1.5 }}>
                            You are removing <strong style={{ fontFamily: 'var(--font-mono)' }}>{pendingRemoveForm.form_name}</strong> from your check-list!<br />Please confirm.
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                            <button className="btn btn-secondary" style={{ minWidth: 64 }} onClick={() => { setShowRemoveModal(false); setPendingRemoveForm(null); }}>No</button>
                            <button className="btn btn-primary" style={{ minWidth: 64, background: 'var(--red)', borderColor: 'var(--red)' }} onClick={() => handleChecklistRemove(pendingRemoveForm)}>Yes</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// CLIENT IDENTITY HELPERS
// ═══════════════════════════════════════════════════════════════════════════

function extractFromFlatObject(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
    const clientSuffixes = ['name_on_return', 'taxpayer_name', 'employee_name', 'partner_name',
        'beneficiary_name', 'shareholder_name', 'client_name', 'payee_name', 'filer_name',
        'recipient_name', 'transferor_name'];
    const entitySuffixes = ['business_name', 'company_name', 'entity_name', 'employer_name',
        'payer_name', 'trustee_or_payer_name'];
    const tinFields = ['employee_ssn', 'recipient_tin', 'payer_tin', 'tax_id'];
    let name = null; let tin = null;

    for (const [k, v] of Object.entries(data)) {
        if (!v || typeof v !== 'string') continue;
        const kl = k.toLowerCase();
        if (!name && (kl === 'name' || clientSuffixes.some(s => kl.endsWith(s)))) name = v.trim();
        else if (!name && entitySuffixes.some(s => kl.endsWith(s))) name = v.trim();
        if (!tin && tinFields.some(s => kl === s)) tin = v.trim();
    }
    if (!name) {
        for (const p of ['taxpayer', 'employee', 'client', 'recipient']) {
            const first = data[`${p}_first_name`] || data[`box_0_${p}_first_name`];
            const last = data[`${p}_last_name`] || data[`box_0_${p}_last_name`];
            if (first && last && typeof first === 'string' && typeof last === 'string') {
                name = `${first.trim()} ${last.trim()}`;
                break;
            }
        }
    }
    return (name || tin) ? { name, tin } : null;
}

/** Extract taxpayer / business identity; walks nested extraction dicts (common for 1040 / schedules). */
function extractClientIdentity(data, depth = 0) {
    if (!data || typeof data !== 'object' || depth > 6) return null;
    const flat = extractFromFlatObject(data);
    if (flat) return flat;
    if (Array.isArray(data)) {
        for (const item of data) {
            const id = extractClientIdentity(item, depth + 1);
            if (id) return id;
        }
        return null;
    }
    for (const v of Object.values(data)) {
        if (v && typeof v === 'object') {
            const id = extractClientIdentity(v, depth + 1);
            if (id) return id;
        }
    }
    return null;
}

function _normClientStr(s) {
    return (s || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

/** Match extracted identity to the client row (DB + static list). */
function clientIdentityMatchesClient(id, client) {
    if (!client || !id || (!id.name && !id.tin)) return false;
    const fd = client.fullData;
    if (id.tin && fd?.tax_id) {
        const a = id.tin.replace(/\D/g, '');
        const b = (fd.tax_id || '').replace(/\D/g, '');
        if (a.length >= 4 && b.length >= 4 && a === b) return true;
    }
    if (id.tin && fd?.ssn) {
        const a = id.tin.replace(/\D/g, '');
        const b = (fd.ssn || '').replace(/\D/g, '');
        if (a.length >= 4 && b.length >= 4 && a === b) return true;
    }
    if (id.name) {
        const n = _normClientStr(id.name);
        if (_normClientStr(client.name) === n) return true;
        if (fd?.business_name && _normClientStr(fd.business_name) === n) return true;
        if (fd?.trust_name && _normClientStr(fd.trust_name) === n) return true;
        if (String(fd?.entity_type || '').toUpperCase() === 'INDIVIDUAL') {
            const full = _normClientStr(`${fd.first_name || ''} ${fd.last_name || ''}`);
            if (full && full === n) return true;
        }
    }
    return false;
}

function extractionMatchesClient(extraction, client) {
    if (!extraction) return false;
    const data = extraction.data || extraction.extracted_fields;
    return clientIdentityMatchesClient(extractClientIdentity(data), client);
}

function fileMatchesClient(file, result, client) {
    // Explicit association wins — set when the user picks/creates a client in the modal
    if (result?.matchedClientId && client?.id && result.matchedClientId === client.id) return true;
    const data = result?.data || result?.extracted_fields;
    return clientIdentityMatchesClient(extractClientIdentity(data), client);
}

/** Match pipeline/ledger client_name string to the selected client row. */
function ledgerClientNameMatches(client, ledgerClientName) {
    if (!client || !ledgerClientName) return false;
    const ln = _normClientStr(String(ledgerClientName));
    if (!ln) return false;
    if (ln === _normClientStr(client.name)) return true;
    const fd = client.fullData;
    if (fd?.business_name && _normClientStr(fd.business_name) === ln) return true;
    if (fd?.trust_name && _normClientStr(fd.trust_name) === ln) return true;
    if (String(fd?.entity_type || '').toUpperCase() === 'INDIVIDUAL') {
        const full = _normClientStr(`${fd.first_name || ''} ${fd.last_name || ''}`);
        if (full && full === ln) return true;
    }
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// CLIENT MATCH MODAL
// ═══════════════════════════════════════════════════════════════════════════

/** Flatten one level of nested extraction objects so we can search field names easily. */
function flattenExtracted(data) {
    if (!data || typeof data !== 'object') return {};
    const flat = {};
    for (const [k, v] of Object.entries(data)) {
        if (v && typeof v === 'object' && !Array.isArray(v)) {
            for (const [k2, v2] of Object.entries(v)) {
                flat[k2] = v2;
            }
        } else {
            flat[k] = v;
        }
    }
    return flat;
}

/** Pick the first truthy value from a list of field names in obj. */
function pick(obj, ...keys) {
    for (const k of keys) {
        const v = obj[k];
        if (v && typeof v === 'string' && v.trim()) return v.trim();
    }
    return '';
}

/** Build pre-filled initialData for AddClientForm from the raw extracted fields. */
function buildInitialData(identity, extractedData) {
    const d = flattenExtracted(extractedData || {});
    const init = {};

    // ── Name ─────────────────────────────────────────────────────────────────
    if (identity?.name) {
        const parts = identity.name.trim().split(/\s+/);
        init.entity_type  = 'INDIVIDUAL';
        init.first_name   = parts[0] || '';
        init.last_name    = parts.slice(1).join(' ') || '';
    } else {
        // Try to infer entity type from extracted data
        const bizName = pick(d, 'business_name', 'company_name', 'employer_name', 'payer_name', 'entity_name');
        if (bizName) {
            init.entity_type  = 'BUSINESS';
            init.business_name = bizName;
        }
    }

    // ── First / Last names if available as separate fields ───────────────────
    if (!init.first_name) {
        const first = pick(d, 'first_name', 'taxpayer_first_name', 'employee_first_name', 'recipient_first_name');
        const last  = pick(d, 'last_name',  'taxpayer_last_name',  'employee_last_name',  'recipient_last_name');
        if (first || last) {
            init.entity_type = init.entity_type || 'INDIVIDUAL';
            init.first_name  = first;
            init.last_name   = last;
        }
    }

    // ── Tax ID / SSN / TIN ───────────────────────────────────────────────────
    const tin = identity?.tin || pick(d,
        'ssn', 'tax_id', 'taxpayer_ssn', 'employee_ssn', 'recipient_tin',
        'payer_tin', 'recipient_ssn', 'filer_ssn', 'ein'
    );
    if (tin) init.tax_id = tin;

    // ── Contact ──────────────────────────────────────────────────────────────
    const email = pick(d, 'email', 'taxpayer_email', 'employee_email', 'recipient_email');
    if (email) init.email = email;

    const phone = pick(d, 'phone', 'phone_number', 'taxpayer_phone', 'employee_phone', 'recipient_phone');
    if (phone) init.phone = phone;

    // ── Address ──────────────────────────────────────────────────────────────
    const addr1 = pick(d,
        'address', 'address_line1', 'street_address',
        'employee_address', 'taxpayer_address', 'recipient_address',
        'employee_street_address', 'taxpayer_street_address'
    );
    if (addr1) init.address_line1 = addr1;

    const addr2 = pick(d, 'address_line2', 'apt', 'suite');
    if (addr2) init.address_line2 = addr2;

    const city = pick(d, 'city', 'employee_city', 'taxpayer_city', 'recipient_city');
    if (city) init.city = city;

    const state = pick(d, 'state', 'employee_state', 'taxpayer_state', 'recipient_state');
    if (state) init.state = state;

    const zip = pick(d, 'zip', 'zip_code', 'postal_code', 'employee_zip', 'taxpayer_zip', 'recipient_zip');
    if (zip) init.zip_code = zip;

    return init;
}

function ClientMatchModal({ modal, apiUrl, onDismiss, onAssociated }) {
    const [showAddForm, setShowAddForm] = useState(false);
    const { identity, match, formType, extractedData } = modal;

    const initialData = buildInitialData(identity, extractedData);

    const overlayStyle = {
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 9000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
    };
    const boxStyle = {
        background: 'var(--surface-0, #fff)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: 28, maxWidth: showAddForm ? 720 : 460,
        width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,.18)',
        maxHeight: '85vh', overflowY: 'auto',
    };

    return (
        <div style={overlayStyle} onClick={e => { if (e.target === e.currentTarget) onDismiss(); }}>
            <div style={boxStyle}>
                {!showAddForm ? (
                    <>
                        <div style={{ marginBottom: 16 }}>
                            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                                {match ? '✓ Client found in database' : (identity.name || identity.tin) ? 'Client not found' : 'Assign to a client'}
                            </div>
                            {match ? (
                                <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
                                    We found <strong>{identity.name}</strong> in your client database.
                                    Associate this <strong>{formType}</strong> with them?
                                </p>
                            ) : (identity.name || identity.tin) ? (
                                <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
                                    <strong>{identity.name || identity.tin}</strong> is not in your database.
                                    Would you like to add them as a new client?
                                </p>
                            ) : (
                                <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
                                    No client name was detected in this document.
                                    Would you like to add a new client for this <strong>{formType}</strong>?
                                </p>
                            )}
                            {identity.tin && (
                                <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                    TIN/SSN: {identity.tin}
                                </div>
                            )}
                        </div>
                        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                            <button className="btn" onClick={onDismiss}
                                style={{ fontSize: 12, padding: '6px 14px' }}>
                                Skip
                            </button>
                            {match ? (
                                <button className="btn btn-primary" onClick={() => onAssociated(match.id)}
                                    style={{ fontSize: 12, padding: '6px 14px' }}>
                                    Associate
                                </button>
                            ) : (
                                <button className="btn btn-primary" onClick={() => setShowAddForm(true)}
                                    style={{ fontSize: 12, padding: '6px 14px' }}>
                                    Add Client
                                </button>
                            )}
                        </div>
                    </>
                ) : (
                    <>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                            <div style={{ fontWeight: 700, fontSize: 13 }}>
                                Add New Client{identity.name ? ` — ${identity.name}` : ''}
                            </div>
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button
                                    type="button"
                                    className="btn"
                                    onClick={() => setShowAddForm(false)}
                                    style={{ fontSize: 12, padding: '6px 14px' }}
                                >
                                    ← Back
                                </button>
                                <button
                                    type="submit"
                                    form="add-client-form"
                                    className="btn btn-primary"
                                    style={{ fontSize: 12, padding: '6px 14px' }}
                                >
                                    Save Client
                                </button>
                            </div>
                        </div>
                        <AddClientForm
                            apiUrl={apiUrl}
                            initialData={initialData}
                            onSuccess={(newClientData) => {
                                // If we have a new client ID, treat it the same as
                                // "Associate" — triggers FDR derive for 1040 uploads.
                                if (newClientData?.id && onAssociated) {
                                    onAssociated(newClientData.id);
                                } else {
                                    onDismiss();
                                }
                            }}
                            onCancel={() => setShowAddForm(false)}
                        />
                    </>
                )}
            </div>
        </div>
    );
}

function normalizeClientKey(name) {
    if (!name) return '—';
    return name
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

function getClientDisplayName(client) {
    const et = (client?.entity_type || '').toUpperCase();
    if (et === 'INDIVIDUAL') {
        const full = `${client?.first_name || ''} ${client?.last_name || ''}`.trim();
        if (full) return full;
    }
    return (
        client?.business_name
        || client?.trust_name
        || `${client?.first_name || ''} ${client?.last_name || ''}`.trim()
        || 'Unknown'
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: FILING PIPELINE  (live from files + results)
// ═══════════════════════════════════════════════════════════════════════════

function PagePipeline({ files, results, apiUrl }) {
    const [view, setView] = useState('table');
    const [typeFilter, setTypeFilter] = useState('All Types');
    const [ledgerRows, setLedgerRows] = useState([]);
    const [ledgerError, setLedgerError] = useState(null);
    const [expandedClients, setExpandedClients] = useState(new Set());
    const [lifecycleStageByClient, setLifecycleStageByClient] = useState({});

    const toggleClient = (name) => setExpandedClients(prev => {
        const s = new Set(prev);
        s.has(name) ? s.delete(name) : s.add(name);
        return s;
    });

    // ── Poll the ledger endpoint every 10 s ───────────────────────────────
    useEffect(() => {
        const base = apiUrl !== undefined ? apiUrl : 'http://localhost:8000';

        function mapStatus(s) {
            if (!s) return 'pending';
            const u = s.toUpperCase();
            if (u === 'EXTRACTED' || u === 'VALIDATED') return 'approved';
            if (u === 'RECEIVED') return 'processing';
            if (u === 'ERROR') return 'exception';
            return 'processing';
        }

        async function fetchLedger() {
            try {
                const res = await fetch(`${base}/ledger/ledger`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                const rows = data.map(rec => {
                    const pct = rec.confidence_score != null ? Math.round(rec.confidence_score * 100) : null;
                    const uploadCount = rec.upload_count || 1;
                    const version = rec.version || 1;
                    return {
                        name: rec.client_name || rec.document_id,
                        form: rec.document_type || '—',
                        stage: rec.stage || 'AI Processing',
                        status: mapStatus(rec.status),
                        conf: pct,
                        confCls: confClass(rec.confidence_score),
                        cpa: rec.cpa || '—',
                        due_date: rec.due_date || '—',
                        document_id: rec.document_id,
                        uploadCount: uploadCount,
                        version: version,
                        fromLedger: true,
                        borderLeft: mapStatus(rec.status) === 'exception' ? 'var(--red)'
                            : mapStatus(rec.status) === 'approved' ? 'var(--green)' : null,
                    };
                });
                setLedgerRows(rows);
                setLedgerError(null);
            } catch (err) {
                setLedgerError(err.message);
            }
        }

        fetchLedger();
        const interval = setInterval(fetchLedger, 10000);
        return () => clearInterval(interval);
    }, [apiUrl]);

    // Fetch client lifecycle stages for parent rows.
    useEffect(() => {
        const base = apiUrl !== undefined ? apiUrl : 'http://localhost:8000';
        let cancelled = false;

        async function fetchClients() {
            try {
                const res = await fetch(`${base}/clients?limit=500`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                const byName = {};
                (Array.isArray(data) ? data : []).forEach((client) => {
                    const name = getClientDisplayName(client);
                    byName[normalizeClientKey(name)] = client?.lifecycle_stage || '';
                });
                if (!cancelled) setLifecycleStageByClient(byName);
            } catch {
                if (!cancelled) setLifecycleStageByClient({});
            }
        }

        fetchClients();
        return () => { cancelled = true; };
    }, [apiUrl]);

    // Build live rows from uploaded files
    const liveRows = files.map(f => {
        const r = results[f.file.name];
        const formType = f.form_type || r?.form_type || '—';
        const stage = getStageFromFile(f, r);
        const status = getStatusFromFile(f, r);
        const pct = r?.document_confidence !== undefined ? Math.round(r.document_confidence * 100) : null;

        // Extract client name from data
        let clientName = f.file.name;
        if (r?.extracted_fields || r?.data) {
            const findName = (d) => {
                if (!d || typeof d !== 'object' || Array.isArray(d)) return null;
                const clientSuffixes = ['name_on_return', 'taxpayer_name', 'employee_name', 'partner_name', 'beneficiary_name', 'shareholder_name', 'client_name', 'payee_name', 'filer_name', 'recipient_name', 'transferor_name'];
                const entitySuffixes = ['business_name', 'company_name', 'entity_name', 'employer_name', 'payer_name', 'trustee_or_payer_name'];

                // Priority 1: Direct Client/Taxpayer names
                for (const [key, val] of Object.entries(d)) {
                    if (val && typeof val === 'string' && val.trim()) {
                        const k = key.toLowerCase();
                        if (k === 'name' || clientSuffixes.some(s => k.endsWith(s))) return val.trim();
                    }
                }
                // Priority 2: Combined First/Last
                for (const p of ['taxpayer', 'employee', 'client']) {
                    let first = null, last = null;
                    for (const k of Object.keys(d)) {
                        if (k.toLowerCase().endsWith(`${p}_first_name`)) first = d[k];
                        if (k.toLowerCase().endsWith(`${p}_last_name`)) last = d[k];
                    }
                    if (first && last && typeof first === 'string' && typeof last === 'string' && first.trim() && last.trim()) {
                        return `${first.trim()} ${last.trim()}`;
                    }
                }
                // Priority 3: Entity/Secondary names
                for (const [key, val] of Object.entries(d)) {
                    if (val && typeof val === 'string' && val.trim()) {
                        const k = key.toLowerCase();
                        if (entitySuffixes.some(s => k.endsWith(s))) return val.trim();
                    }
                }
                for (const val of Object.values(d)) {
                    if (val && typeof val === 'object' && !Array.isArray(val)) {
                        const res = findName(val);
                        if (res) return res;
                    }
                }
                return null;
            };
            const extractedName = findName(r.extracted_fields || r.data);
            if (extractedName) clientName = extractedName;
        }

        return {
            name: clientName, form: formType, stage, status,
            conf: pct, confCls: confClass(r?.document_confidence),
            cpa: '—', due_date: '—', fromLedger: false,
            document_id: r?.document_id,
            uploadCount: 1,
            version: 1,
            borderLeft: status === 'exception' ? 'var(--red)' : status === 'approved' ? 'var(--green)' : null,
        };
    });

    // Deduplicate: ledger rows take precedence, then live rows not already in ledger
    // Match based on document_id (if available) or name (as fallback)
    const ledgerIds = new Set(ledgerRows.map(r => r.document_id).filter(Boolean));
    const ledgerNamesNorm = new Set(ledgerRows.map(r => normalizeClientKey(r.name)));

    const deduped = [
        ...ledgerRows,
        ...liveRows.filter(r => {
            if (r.document_id && ledgerIds.has(r.document_id)) return false;
            if (ledgerNamesNorm.has(normalizeClientKey(r.name))) return false;
            return true;
        }),
    ];

    // Merge into kanban columns
    const stageToCol = {
        'Document Collection': 'Document Collection',
        'Document Submission': 'Document Collection',
        'Queued': 'Document Collection',
        'AI Processing': 'AI Processing',
        'Exception Review': 'Exception Review',
        'CPA Review': 'CPA Review',
        'Client Approval': 'Client Approval',
        'Complete': 'Filed & Confirmed',
        'Filed & Confirmed': 'Filed & Confirmed',
        'Error': 'Exception Review',
        'Gate Rejected': 'Exception Review',
    };

    const kanbanCols = ['Document Collection', 'AI Processing', 'Exception Review', 'CPA Review', 'Client Approval', 'Ready to E-File', 'Filed & Confirmed'];
    const liveKanban = {};
    deduped.forEach(r => {
        const col = stageToCol[r.stage] || 'AI Processing';
        if (!liveKanban[col]) liveKanban[col] = [];
        liveKanban[col].push(r);
    });
    const finalKanban = {};
    kanbanCols.forEach(col => { finalKanban[col] = liveKanban[col] || []; });

    // Filter
    const filtered = deduped.filter(r => typeFilter === 'All Types' || r.form.includes(typeFilter));

    return (
        <div>
            <div className="pipeline-header">
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700 }}>
                    Filing Pipeline
                    {ledgerRows.length > 0 && (
                        <span style={{ marginLeft: 10, fontSize: 11, fontWeight: 500, background: 'rgba(59,130,246,.12)', color: '#3b82f6', padding: '2px 8px', borderRadius: 10 }}>
                            🗄 {ledgerRows.length} from DB
                        </span>
                    )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    {ledgerError && (
                        <span style={{ fontSize: 11, color: 'var(--red)', opacity: .7 }}>
                            ⚠ DB unreachable
                        </span>
                    )}
                    <div className="filter-chips" style={{ margin: 0 }}>
                        {['All Types', '1040', '1120', '1065', 'W-2', '1099'].map(f => (
                            <span key={f} className={`filter-chip${typeFilter === f ? ' active' : ''}`} onClick={() => setTypeFilter(f)}>{f}</span>
                        ))}
                    </div>
                    <div className="view-toggle">
                        <div className={`view-toggle-btn${view === 'kanban' ? ' active' : ''}`} onClick={() => setView('kanban')}>Board</div>
                        <div className={`view-toggle-btn${view === 'table' ? ' active' : ''}`} onClick={() => setView('table')}>Table</div>
                    </div>
                </div>
            </div>

            {view === 'kanban' && (
                <div className="kanban-board" style={{ height: 'calc(100vh - 48px - 140px)' }}>
                    {Object.entries(finalKanban).map(([col, cards]) => (
                        <div key={col} className="kanban-col">
                            <div className="kanban-col-header">{col} <span className="count">{cards.length}</span></div>
                            <div className="kanban-cards">
                                {cards.map((c, i) => (
                                    <div key={i} className="kanban-card" style={{ ...(c.borderLeft ? { borderLeft: `3px solid ${c.borderLeft}` } : {}), ...(c.faded ? { opacity: .65 } : {}) }}>
                                        <div className="kanban-card-name">
                                            {c.fromLedger && <span style={{ fontSize: 9, opacity: .6, marginRight: 4 }}>🗄</span>}
                                            {c.name || c.client || '—'}
                                        </div>
                                        <div className="kanban-card-form">{c.form}</div>
                                        <div className="kanban-card-footer">
                                            {c.conf !== null && c.conf !== undefined
                                                ? <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: c.conf >= 90 ? 'var(--green)' : c.conf >= 75 ? 'var(--amber)' : 'var(--red)' }}>{c.conf}%</div>
                                                : c.avatar ? <div className="kanban-card-avatar">{c.avatar}</div>
                                                    : c.note ? <div style={{ fontSize: 11, color: `var(--${c.noteColor})` }}>{c.note}</div>
                                                        : <div />}
                                            {c.stage && <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{c.stage}</div>}
                                            {c.due_date && c.due_date !== '—' && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>📅 {c.due_date}</div>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {view === 'table' && (() => {
                // Group by normalized key but display the original name from the first row
                const _groupMap = {};
                filtered.forEach(row => {
                    const nk = normalizeClientKey(row.name);
                    if (!_groupMap[nk]) {
                        _groupMap[nk] = { displayName: row.name || '—', rows: [] };
                    }
                    _groupMap[nk].rows.push(row);
                });
                const grouped = Object.fromEntries(
                    Object.entries(_groupMap).map(([nk, { displayName, rows }]) => [displayName, rows])
                );

                const clientKeys = Object.keys(grouped);

                return (
                    <table className="data-table">
                        <thead><tr>
                            <th style={{ width: 28 }}></th>
                            <th>Client</th>
                            <th style={{ width: 80, textAlign: 'center' }}># Forms</th>
                            <th>Stage</th>
                            <th>Confidence</th>
                            <th>Status</th>
                        </tr></thead>
                        <tbody>
                            {clientKeys.length > 0 ? clientKeys.map((clientName) => {
                                const rows = grouped[clientName];
                                const isExpanded = expandedClients.has(clientName);
                                const parentStage = lifecycleStageByClient[normalizeClientKey(clientName)] || '—';

                                return (
                                    <React.Fragment key={clientName}>
                                        {/* Parent / client row */}
                                        <tr
                                            onClick={() => toggleClient(clientName)}
                                            style={{ cursor: 'pointer', background: isExpanded ? 'var(--surface-1, rgba(0,0,0,.03))' : undefined }}
                                        >
                                            <td style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 11, userSelect: 'none' }}>
                                                {isExpanded ? '▼' : '▶'}
                                            </td>
                                            <td style={{ fontWeight: 600 }}>
                                                {clientName}
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <span style={{ display: 'inline-block', minWidth: 22, padding: '1px 7px', fontSize: 11, fontWeight: 700, background: 'rgba(99,102,241,.12)', color: '#6366f1', borderRadius: 10 }}>
                                                    {rows.length}
                                                </span>
                                            </td>
                                            <td style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>
                                                {parentStage}
                                            </td>
                                            <td>
                                                <span style={{ color: 'var(--text-muted)' }}>—</span>
                                            </td>
                                            <td>
                                                <span style={{ color: 'var(--text-muted)' }}>—</span>
                                            </td>
                                        </tr>

                                        {/* Child / form rows */}
                                        {isExpanded && rows.map((r, i) => (
                                            <tr key={i} style={{ background: 'var(--surface-1, rgba(0,0,0,.02))' }}>
                                                <td></td>
                                                <td style={{ paddingLeft: 32, fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                                                    <span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{r.form}</span>
                                                    <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }} title="Document version">
                                                        {r.version ?? 1}
                                                    </span>
                                                </td>
                                                <td></td>
                                                <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r.stage}</td>
                                                <td>
                                                    {r.conf != null
                                                        ? <span className={`confidence-badge ${r.confCls || ''}`}>{r.conf}%</span>
                                                        : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                                                </td>
                                                <td><StatusPill status={r.status} /></td>
                                            </tr>
                                        ))}
                                    </React.Fragment>
                                );
                            }) : (
                                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)', fontSize: 13 }}>
                                    {ledgerError
                                        ? `No documents yet. (DB connection error: ${ledgerError})`
                                        : 'No documents in pipeline yet. Upload a form from Ingestion Hub or submit via the ledger API.'}
                                </td></tr>
                            )}
                        </tbody>
                    </table>
                );
            })()}

            {view === 'kanban' && deduped.length === 0 && (
                <div style={{ marginTop: 12, padding: '32px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)' }}>
                    No documents in pipeline yet. Upload a form from Ingestion Hub to see it here.
                </div>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// EXCEPTION CARD  (used for static exceptions fallback)
// ═══════════════════════════════════════════════════════════════════════════
function ExcCard({ exc, apiUrl, onAccept, onOverride }) {
    const [overrideMode, setOverrideMode] = useState(false);
    const [overrideVal, setOverrideVal] = useState('');
    const [accepted, setAccepted] = useState(false);
    if (accepted) return null;
    return (
        <div className="exception-card">
            <div className="exception-header">
                <div>
                    <div className="exception-client">{exc.client || exc.field || 'Unknown'}</div>
                    <div className="exception-form">{exc.form || exc.exception_id || '—'}</div>
                </div>
                <span className={`severity ${exc.severity === 'high' || exc.severity === 'CRITICAL' ? 'high' : exc.severity === 'medium' || exc.severity === 'WARNING' ? 'medium' : 'low'}`}>
                    {exc.severity === 'CRITICAL' ? 'High' : exc.severity === 'WARNING' ? 'Medium' : exc.severity === 'high' ? 'High' : exc.severity === 'medium' ? 'Medium' : 'Low'}
                </span>
            </div>
            <div className="exception-type">{exc.type || exc.code || 'Exception'}</div>
            <div className="exception-desc">{exc.desc || exc.description || exc.message || '—'}</div>
            <div className="exception-ai"><span>✦</span> <strong>AI suggests:</strong> {exc.ai || exc.ai_suggestion || exc.fix_description || '—'} {exc.conf && <span className={`confidence-badge ${exc.confCls || ''}`}>{exc.conf}</span>}</div>
            {!overrideMode ? (
                <div className="exception-actions">
                    <button className="btn btn-success" onClick={() => setAccepted(true)}>Accept AI Suggestion</button>
                    <button className="btn btn-secondary" onClick={() => setOverrideMode(true)}>Override</button>
                </div>
            ) : (
                <div className="exception-actions" style={{ flexDirection: 'column', gap: 8 }}>
                    <input type="text" style={{ width: '100%', padding: '8px 12px', fontSize: 13, border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', outline: 'none' }} placeholder="Enter corrected value…" value={overrideVal} onChange={e => setOverrideVal(e.target.value)} />
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-success" onClick={() => { if (overrideVal.trim()) { if (onOverride) onOverride(exc, overrideVal); setAccepted(true); } }}>Confirm Override</button>
                        <button className="btn btn-secondary" onClick={() => setOverrideMode(false)}>Cancel</button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════════════════
// LIVE EXCEPTION CARD — matches Image 1 card grid layout
// ═══════════════════════════════════════════════════════════════════════════
/**
 * Classify an exception as AUTO (AI can fix deterministically) or
 * MANUAL (correct value does not exist in the system — human must supply it).
 *
 * Returns: "AUTO" | "MANUAL"
 */
/**
 * Classify an exception as AUTO (AI can fix deterministically) or
 * MANUAL (correct value does not exist in the system — human must supply it).
 *
 * Built from the complete Taxscio exception taxonomy (90+ exception types
 * across 15 categories). The rule: AUTO if and only if the correct value
 * can be computed or derived from data already in the system.
 *
 * Returns: "AUTO" | "MANUAL"
 */
function classifyException(exc) {
    const code = (exc.code || exc.exception_id || '').toUpperCase();
    const severity = (exc.severity || '').toUpperCase();

    // ── RULE 1: proposed_value is the ground truth ────────────────────────
    // If the backend computed a concrete value to insert, it's AUTO regardless
    // of the code. If no concrete value exists, Accept AI Suggestion is meaningless.
    const hasProposedValue = (
        exc.proposed_value !== null &&
        exc.proposed_value !== undefined &&
        exc.proposed_value !== '' &&
        exc.proposed_value !== 'undefined'
    ) || (
        exc.auto_fix_value !== null &&
        exc.auto_fix_value !== undefined &&
        exc.auto_fix_value !== '' &&
        exc.auto_fix_value !== 'undefined'
    );

    // ── RULE 2: _source from backend classification is authoritative ──────
    // auto_fixer.py already made this decision. Trust it.
    // BUT: fixable + no proposed_value = MANUAL (the fixer knew the rule
    // but couldn't compute the value)
    if (exc._source === 'fixable') {
        return hasProposedValue ? 'AUTO' : 'MANUAL';
    }
    if (exc._source === 'review') return 'MANUAL';

    // ── RULE 3: CRITICAL severity → always MANUAL ─────────────────────────
    if (severity === 'CRITICAL') return 'MANUAL';

    // ── RULE 4: Exact code matching against real auto_fixer.py codes ──────
    const FIXABLE_CODES = new Set([
        'FLD_ZERO_VS_BLANK',
        'FLD_DASH_SYMBOL',
        'FLD_NA_TEXT',
        'FLD_CHECKBOX_BLANK',
        'FLD_SPECIAL_CHARS',
        'LLM_OVER_NORMALIZATION',
    ]);

    const REVIEW_CODES = new Set([
        'NUM_NEGATIVE_VALUE',
        'NUM_DECIMAL_MISPLACE',
        'NUM_LARGE_OUTLIER',
        'NUM_WITHHOLDING_GT_INC',
        'NUM_DUPLICATE_ENTRY',
        'NUM_SUBTOTAL_MISMATCH',
        'ID_INVALID_SSN',
        'ID_INVALID_TIN',
        'ID_MASKED_SSN',
        'ID_DUPLICATE_DEP_SSN',
        'FORM_INVALID_CODE',
        'FLD_ILLEGIBLE',
        'FLD_ADDRESS_COLLAPSED',
    ]);

    if (FIXABLE_CODES.has(code)) return hasProposedValue ? 'AUTO' : 'MANUAL';
    if (REVIEW_CODES.has(code)) return 'MANUAL';

    // ── RULE 5: proposed_value fallback for unknown codes ─────────────────
    if (hasProposedValue) return 'AUTO';

    // ── RULE 6: default → MANUAL ──────────────────────────────────────────
    return 'MANUAL';
}

/**
 * Client-side field format validator.
 * Runs BEFORE /apply-fixes is called.
 * Returns an error message string on failure, null on pass.
 */
function validateFieldInput(field, value) {
    if (value === null || value === undefined) return null;
    const v = String(value).trim();
    const f = (field || '').toLowerCase();

    if (v === '') return null;

    // ── SSN: XXX-XX-XXXX or 9 raw digits ────────────────────────────
    if (f.includes('ssn') || f === 'employee_ssn' || f === 'recipient_ssn') {
        const digits = v.replace(/\D/g, '');
        if (digits.length !== 9) {
            return 'Enter the SSN in format XXX-XX-XXXX (e.g. 123-45-6789).';
        }
        if (/^0{9}$/.test(digits) || /^1{9}$/.test(digits)) {
            return 'SSN cannot be all the same digit.';
        }
        if (digits.startsWith('9')) {
            return 'SSNs cannot begin with 9 — that is an ITIN format. Use the ITIN field instead.';
        }
        return null;
    }

    // ── ITIN: 9XX-XX-XXXX ───────────────────────────────────────────
    if (f.includes('itin')) {
        const digits = v.replace(/\D/g, '');
        if (digits.length !== 9 || !digits.startsWith('9')) {
            return 'ITIN must be 9 digits starting with 9 (format: 9XX-XX-XXXX).';
        }
        return null;
    }

    // ── EIN / TIN / Payer TIN: XX-XXXXXXX or 9 raw digits ──────────
    if (f.includes('ein') || f.includes('payer_tin') || f.includes('employer_id')
        || f === 'tin' || f.includes('_tin')) {
        const digits = v.replace(/\D/g, '');
        if (digits.length !== 9) {
            return 'Enter the TIN/EIN in format XX-XXXXXXX (e.g. 12-3456789).';
        }
        if (/^0{9}$/.test(digits)) {
            return 'TIN/EIN cannot be all zeros.';
        }
        return null;
    }

    // ── Tax year ─────────────────────────────────────────────────────
    if (f === 'tax_year' || f.includes('tax_year')) {
        const yr = parseInt(v, 10);
        if (isNaN(yr) || String(yr) !== v) {
            return 'Tax year must be a 4-digit number (e.g. 2025)';
        }
        if (yr < 1990 || yr > 2035) {
            return `Tax year ${yr} is outside the valid range (1990–2035)`;
        }
        const currentYear = new Date().getFullYear();
        if (yr < currentYear - 1) {
            return `Tax year ${yr} is more than 1 year prior to ${currentYear}. ` +
                   `If this is an amended return, use Escalate instead.`;
        }
        return null;
    }

    // ── Distribution / box codes ─────────────────────────────────────
    if (f.endsWith('_code') && (f.includes('distribution') || f.includes('box_7'))) {
        // IRS 1099-R Box 7 valid distribution codes
        const VALID_DIST_CODES = new Set([
            '1','2','3','4','5','6','7','8','9',
            'A','B','C','D','E','F','G','H','J',
            'K','L','M','N','P','Q','R','S','T','U','W'
        ]);
        if (!VALID_DIST_CODES.has(v.toUpperCase())) {
            return `'${v}' is not a valid IRS distribution code. ` +
                   `Valid codes: 1-9, A-H, J-N, P-W (excluding I, O, V, X, Y, Z)`;
        }
        return null;
    }

    // ── Currency / monetary amounts ──────────────────────────────────
    // Mirrors backend engine.py NUMERIC_FIELD_SUFFIXES exactly.
    // Suffix matching prevents false positives on distribution_code, date_of_payment, etc.
    const NUMERIC_FIELD_SUFFIXES = [
        '_amount', '_income', '_wages', '_tax', '_withheld',
        '_compensation', '_proceeds', '_gain', '_loss', '_credit',
        '_payment', '_distribution', '_interest', '_dividends',
        '_royalties', '_benefits', '_contributions', '_deduction',
    ];
    const isCurrency = NUMERIC_FIELD_SUFFIXES.some(suffix => f.endsWith(suffix));
    if (isCurrency) {
        const cleaned = v.replace(/[$,\s]/g, '');
        const num = parseFloat(cleaned);
        if (isNaN(num)) {
            return 'Amount must be a number (e.g. 12000.00)';
        }
        if (num < 0) {
            return 'Amount cannot be negative for this field';
        }
        if (num > 99_999_999) {
            return 'Amount exceeds maximum allowed value ($99,999,999)';
        }
        return null;
    }

    // ── Percentages ──────────────────────────────────────────────────
    if (f.includes('rate') || f.includes('percent') || f.includes('pct')) {
        const num = parseFloat(v);
        if (isNaN(num)) return 'Must be a number';
        if (num < 0 || num > 100) return 'Percentage must be between 0 and 100';
        return null;
    }

    // ── ZIP code ─────────────────────────────────────────────────────
    if (f.includes('zip') || f.includes('postal')) {
        if (!/^\d{5}(-\d{4})?$/.test(v)) {
            return 'ZIP code must be 5 digits (e.g. 10022) or 9 digits (e.g. 10022-1234)';
        }
        return null;
    }

    // ── State code ───────────────────────────────────────────────────
    if (f === 'state' || f.endsWith('_state')) {
        if (!/^[A-Z]{2}$/.test(v.toUpperCase())) {
            return 'State must be a 2-letter code (e.g. NY, CA)';
        }
        return null;
    }

    // ── Date fields ──────────────────────────────────────────────────
    if (f.includes('date') || f.includes('_dob') || f.includes('birth')) {
        const d = new Date(v);
        if (isNaN(d.getTime())) {
            return 'Must be a valid date (e.g. 2025-01-15 or 01/15/2025)';
        }
        return null;
    }

    // No rule matched — pass through to backend
    return null;
}

// LIVE EXCEPTION CARD — matches Image 1 card grid layout
// ═══════════════════════════════════════════════════════════════════════════
function LiveExcCard({ exc, formType, filename, apiUrl, documentId: documentIdProp, validationError, isSubmitting, onSubmit, onEscalate }) {
    const [overrideMode, setOverrideMode] = useState(false);
    const [overrideVal, setOverrideVal] = useState('');
    const [error, setError] = useState(null);
    const [escalated, setEscalated] = useState(false);
    const baseApiUrl = (apiUrl || 'http://localhost:8000').replace(/\/$/, '');

    // Reset input state whenever the exception changes (new card or prop update)
    useEffect(() => {
        setOverrideVal('');
        setError(null);
        setOverrideMode(false);
        setEscalated(false);
    }, [exc.field, exc.code]);

    // Normalise severity to high / medium / low
    const rawSev = (exc.severity || '').toUpperCase();
    const sevDisplay = rawSev === 'CRITICAL' || rawSev === 'BLOCKING' ? 'HIGH'
        : rawSev === 'WARNING' ? 'MEDIUM' : 'LOW';
    const sevClass = sevDisplay === 'HIGH' ? 'high' : sevDisplay === 'MEDIUM' ? 'medium' : 'low';

    // Map exception code prefix to a readable type + icon
    const code = (exc.code || exc.exception_id || '');
    const getType = () => {
        const c = code.toUpperCase();
        if (c.startsWith('NUM_')) return ['🔢', 'Calculation Variance'];
        if (c.startsWith('ID_')) return ['🪪', 'Identity Exception'];
        if (c.startsWith('FLD_')) return ['📄', 'Missing Field'];
        if (c.startsWith('OCR_')) return ['🖨️', 'OCR / Format Issue'];
        if (c.startsWith('LLM_') || c.startsWith('LLMD_')) return ['🤖', 'LLM Exception'];
        if (c.startsWith('ENG_')) return ['📋', 'Engagement Issue'];
        if (c.startsWith('CY_')) return ['📅', 'Prior Year Conflict'];
        if (c.startsWith('XDOC_')) return ['🔗', 'Cross-Document'];
        if (c.startsWith('SEC_')) return ['🔒', 'Security Flag'];
        if (c.startsWith('WF_') || c.startsWith('LED_')) return ['⚙️', 'Workflow State'];
        if (c.startsWith('EMAIL_')) return ['📧', 'Email Source'];
        if (c.startsWith('MT_')) return ['🏢', 'Multi-Tenant'];
        if (c.startsWith('DB_')) return ['🗄️', 'Data Schema'];
        if (c.startsWith('STR_')) return ['🏗️', 'Structural'];
        if (c.startsWith('CTX_')) return ['⚖️', 'Tax Logic'];
        return ['⚠️', 'Exception'];
    };
    const [typeIcon, typeLabel] = getType();

    // Field label — clean up snake_case
    const fieldLabel = exc.field
        ? exc.field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
        : null;

    // Client display prioritize name over filename
    const clientLabel = filename.replace(/\.[^/.]+$/, '');

    const handleSubmit = (value) => {
        const val = String(value || '').trim();
        if (!val) return;
        onSubmit(exc.field, val);
    };

    const handleAccept = () => {
        const fixVal = exc.proposed_value ?? exc.auto_fix_value;
        if (fixVal === undefined || fixVal === null || fixVal === '') {
            setError('No AI-proposed value available — enter a value manually.');
            return;
        }
        handleSubmit(String(fixVal));
    };

    const handleOverrideConfirm = () => {
        handleSubmit(overrideVal);
    };

    const handleEscalate = async () => {
        // Remove card immediately — don't wait for API
        if (onEscalate) onEscalate(exc.code, exc.field);

        // Fire API in background for ledger record
        try {
            const baseUrl = (apiUrl || 'http://localhost:8000').replace(/\/$/, '');
            await fetch(`${baseUrl}/ledger/escalate-exception`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_id: documentIdProp || null,
                    client_name: filename,
                    document_type: formType,
                    exception_code: exc.code,
                    exception_field: exc.field,
                    severity: exc.severity || 'WARNING',
                    description: exc.description || exc.message || null,
                    filename,
                }),
            });
        } catch (e) {
            // Silently ignore — card is already removed
            console.warn('[Escalate] API call failed silently:', e?.message);
        }
    };

    const aiText = exc.ai_suggestion || exc.fix_description || exc.edit_hint || exc.handling || '—';
    const confPct = exc.confidence !== undefined ? Math.round(exc.confidence * 100)
        : exc.document_confidence !== undefined ? Math.round(exc.document_confidence * 100)
            : null;
    const confCls = confPct === null ? '' : confPct >= 90 ? 'high' : confPct >= 70 ? 'med' : 'low';

    return (
        <div className="exception-card">
            <div className="exception-header">
                <div>
                    <div className="exception-client">{clientLabel}</div>
                    <div className="exception-form">
                        {formType}{fieldLabel ? ` · ${fieldLabel}` : ''}
                    </div>
                </div>
                <span className={`severity ${sevClass}`}>{sevDisplay}</span>
            </div>

            <div className="exception-type">{typeIcon} {typeLabel}</div>

            <div className="exception-desc">
                {exc.description || exc.message || '—'}
            </div>

            <div className="exception-ai">
                <span>✦</span>
                <strong>AI suggests:</strong>
                {' '}{aiText}
                {confPct !== null && (
                    <span className={`confidence-badge ${confCls}`} style={{ marginLeft: 6 }}>{confPct}%</span>
                )}
            </div>

            {classifyException(exc) === 'AUTO' && !overrideMode && !escalated && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    <button
                        type="button"
                        style={{ background: 'none', border: 'none', cursor: 'pointer',
                                 color: 'var(--text-muted)', fontSize: 11, padding: 0,
                                 textDecoration: 'underline' }}
                        onClick={() => setOverrideMode(true)}
                    >
                        Enter different value instead
                    </button>
                </div>
            )}

            {error && (
                <div style={{ fontSize: 11, color: 'var(--red)', marginBottom: 8 }}>{error}</div>
            )}

            {validationError && (
                <div style={{ fontSize: 11, color: 'var(--red)', marginBottom: 6 }}>✗ {validationError}</div>
            )}

            {(() => {
                const excType = classifyException(exc);

                if (excType === 'AUTO' && !overrideMode) {
                    const proposedVal = exc.proposed_value ?? exc.auto_fix_value;
                    const proposedDisplay = proposedVal !== null && proposedVal !== undefined
                        ? String(proposedVal)
                        : null;

                    return (
                        <div className="exception-actions">
                            <button
                                type="button"
                                className="btn btn-success"
                                onClick={handleAccept}
                                disabled={isSubmitting || escalated}
                                title={proposedDisplay
                                    ? `AI fix: set ${exc.field} → ${proposedDisplay}`
                                    : 'Apply AI suggestion'}
                            >
                                {isSubmitting ? 'Applying…' : `Accept AI Suggestion${proposedDisplay ? ` (→ ${proposedDisplay})` : ''}`}
                            </button>
                            <button
                                type="button"
                                className="btn btn-danger"
                                onClick={handleEscalate}
                                disabled={escalated}
                            >
                                Escalate
                            </button>
                        </div>
                    );
                }

                if (excType === 'MANUAL' && !overrideMode) {
                    const hint = exc.edit_hint
                        || `Enter correct value for ${(exc.field || '').replace(/_/g, ' ')}…`;

                    return (
                        <div className="exception-actions" style={{ flexDirection: 'column', gap: 8 }}>
                            <div style={{
                                fontSize: 11,
                                color: 'var(--amber)',
                                background: 'rgba(217,119,6,.08)',
                                border: '1px solid rgba(217,119,6,.2)',
                                borderRadius: 4,
                                padding: '6px 10px',
                                lineHeight: 1.5,
                            }}>
                                ✎ Human input required — AI cannot determine the correct value for this field.
                            </div>
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                                <input
                                    type="text"
                                    style={{
                                        flex: 1,
                                        padding: '8px 12px',
                                        fontSize: 13,
                                        border: `1px solid ${validationError ? 'var(--red)' : 'var(--border)'}`,
                                        borderRadius: 'var(--radius-sm)',
                                        outline: 'none',
                                        background: 'var(--surface-1)',
                                    }}
                                    placeholder={hint}
                                    value={overrideVal}
                                    onChange={e => setOverrideVal(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && overrideVal.trim() && handleOverrideConfirm()}
                                    autoFocus
                                />
                                <button
                                    className="btn btn-success"
                                    onClick={handleOverrideConfirm}
                                    disabled={isSubmitting || !overrideVal.trim()}
                                >
                                    {isSubmitting ? 'Validating…' : 'Submit'}
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-danger"
                                    onClick={handleEscalate}
                                    disabled={escalated}
                                >
                                    Escalate
                                </button>
                            </div>
                        </div>
                    );
                }

                // AUTO in override mode
                return (
                    <div className="exception-actions" style={{ flexDirection: 'column', gap: 8 }}>
                        <input
                            type="text"
                            style={{
                                width: '100%',
                                padding: '8px 12px',
                                fontSize: 13,
                                border: `1px solid ${validationError ? 'var(--red)' : 'var(--border)'}`,
                                borderRadius: 'var(--radius-sm)',
                                outline: 'none',
                                background: 'var(--surface-1)',
                            }}
                            placeholder={`Enter corrected value for ${fieldLabel || 'this field'}…`}
                            value={overrideVal}
                            onChange={e => setOverrideVal(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleOverrideConfirm()}
                            autoFocus
                        />
                        <div style={{ display: 'flex', gap: 8 }}>
                            <button
                                className="btn btn-success"
                                onClick={handleOverrideConfirm}
                                disabled={isSubmitting || !overrideVal.trim()}
                            >
                                {isSubmitting ? 'Validating…' : 'Confirm Override'}
                            </button>
                            <button
                                className="btn btn-secondary"
                                onClick={() => { setOverrideMode(false); setOverrideVal(''); }}
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                className="btn btn-danger"
                                onClick={handleEscalate}
                                disabled={escalated}
                            >
                                Escalate
                            </button>
                        </div>
                    </div>
                );
            })()}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: EXCEPTIONS  — card grid layout (matches Image 1)
// ═══════════════════════════════════════════════════════════════════════════
function PageExceptions({ files, results, apiUrl, setResults }) {
    const [filterType, setFilterType] = useState('All Types');

    // patchedData[filename] = full form data dict for that file, updated after every /apply-fixes
    const [patchedData, setPatchedData] = useState(() => {
        const initial = {};
        files.filter(f => f.status === 'completed').forEach(f => {
            const r = results[f.file.name] || {};
            const candidate =
                r.extracted_fields ||
                r.data ||
                r.raw_normalized_json ||
                r.formatted_json ||
                {};
            const isNested = Object.values(candidate).some(
                v => v !== null && typeof v === 'object' && !Array.isArray(v)
            );
            if (isNested) {
                const flat = {};
                for (const [k, v] of Object.entries(candidate)) {
                    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
                        Object.assign(flat, v);
                    } else {
                        flat[k] = v;
                    }
                }
                initial[f.file.name] = flat;
            } else {
                initial[f.file.name] = { ...candidate };
            }
        });
        return initial;
    });

    // liveExceptions[filename] = current exception list, replaced wholesale after every /apply-fixes
    const [liveExceptions, setLiveExceptions] = useState(() => {
        const initial = {};
        files.filter(f => f.status === 'completed').forEach(f => {
            const r = results[f.file.name] || {};
            const seen = new Set();
            const deduped = [];
            const dedup = (arr, source) => (arr || []).forEach(exc => {
                const key = `${exc.code || ''}:${exc.field || ''}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    deduped.push({ ...exc, _source: source });
                }
            });
            dedup(r.fixable_exceptions, 'fixable');
            dedup(r.review_exceptions,  'review');
            dedup(r.exceptions,         'exceptions');
            initial[f.file.name] = deduped;
        });
        return initial;
    });

    // submitting[filename] = true while /apply-fixes is in flight for that file
    const [submitting, setSubmitting] = useState({});

    // fieldErrors[filename][field] = inline error string for that card
    const [fieldErrors, setFieldErrors] = useState({});

    const handleCardSubmit = async (filename, field, value, formType) => {
        // Client-side format validation before any network call
        const formatError = validateFieldInput(field, value);
        if (formatError) {
            setFieldErrors(prev => ({
                ...prev,
                [filename]: { ...(prev[filename] || {}), [field]: formatError }
            }));
            return;
        }

        setSubmitting(prev => ({ ...prev, [filename]: true }));
        setFieldErrors(prev => ({
            ...prev,
            [filename]: { ...(prev[filename] || {}), [field]: null }
        }));

        try {
            const currentData = patchedData[filename] || {};
            const newPatchedData = { ...currentData, [field]: value };
            const baseUrl = (apiUrl || 'http://localhost:8000').replace(/\/$/, '');

            // Step 1: validate — pass fixes so the backend applies the CPA's value
            // to the correct extracted-data key (e.g. box_7_distribution_code) via
            // _patch_nested before running the engine. No frontend key-guessing needed.
            const vRes = await fetch(`${baseUrl}/validate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    form_type: formType,
                    data: newPatchedData,
                    fixes: [{ field, new_value: value }],
                    pdf_type: 'digital',
                }),
            });
            if (vRes.ok) {
                const vData = await vRes.json().catch(() => ({}));
                const allVExc = [
                    ...(vData.fixable_exceptions || []),
                    ...(vData.review_exceptions  || []),
                    ...(vData.exceptions         || []),
                ];
                const fLow = (field || '').toLowerCase();
                const failing = allVExc.find(e => (e.field || '').toLowerCase() === fLow);
                if (failing) {
                    const reason = failing.description || failing.edit_hint || failing.code || 'Value did not pass IRS validation rules';
                    setFieldErrors(prev => ({ ...prev, [filename]: { ...(prev[filename] || {}), [field]: reason } }));
                    setSubmitting(prev => ({ ...prev, [filename]: false }));
                    return;
                }
            }

            // Step 2: passed — write permanently
            const body = {
                form_type: formType,
                data: newPatchedData,
                fixes: [{ field, new_value: value }],
                pdf_type: 'digital',
                human_verified_fields: [field],
                document_id: results[filename]?.document_id || undefined,
                context: { filename, document_id: results[filename]?.document_id || undefined },
            };

            const r = await fetch(`${baseUrl}/apply-fixes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            const data = await r.json().catch(() => ({}));

            if (!r.ok) {
                setFieldErrors(prev => ({
                    ...prev,
                    [filename]: {
                        ...(prev[filename] || {}),
                        [field]: data?.error || data?.message || `Save failed (${r.status})`
                    }
                }));
                return;
            }

            // Update patchedData with the confirmed value
            setPatchedData(prev => ({
                ...prev,
                [filename]: { ...(prev[filename] || {}), [field]: value }
            }));

            // Build new exception list from response (deduplicated, classified first)
            const seen = new Set();
            const newExceptions = [];
            const dedup = (arr, source) => (arr || []).forEach(exc => {
                const key = `${exc.code || ''}:${exc.field || ''}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    newExceptions.push({ ...exc, _source: source });
                }
            });
            dedup(data.fixable_exceptions, 'fixable');
            dedup(data.review_exceptions,  'review');
            dedup(data.exceptions,         'exceptions');

            // Replace this file's exception list wholesale
            setLiveExceptions(prev => ({ ...prev, [filename]: newExceptions }));

            // Keep parent results in sync
            if (setResults) {
                setResults(prev => ({
                    ...prev,
                    [filename]: { ...(prev[filename] || {}), ...data }
                }));
            }

            // Check if this field still has an exception — if yes, show inline error
            const fieldLower = (field || '').toLowerCase();
            const stillFailing = newExceptions.find(e =>
                (e.field || '').toLowerCase() === fieldLower
            );
            if (stillFailing) {
                const reason = stillFailing.description
                    || stillFailing.edit_hint
                    || stillFailing.code
                    || 'Value did not pass IRS validation rules';
                setFieldErrors(prev => ({
                    ...prev,
                    [filename]: { ...(prev[filename] || {}), [field]: reason }
                }));
            } else {
                setFieldErrors(prev => ({
                    ...prev,
                    [filename]: { ...(prev[filename] || {}), [field]: null }
                }));
            }

        } catch (e) {
            setFieldErrors(prev => ({
                ...prev,
                [filename]: {
                    ...(prev[filename] || {}),
                    [field]: e?.message || 'Network error'
                }
            }));
        } finally {
            setSubmitting(prev => ({ ...prev, [filename]: false }));
        }
    };

    // Build cards from liveExceptions (ground truth after every submit)
    const allCards = [];
    files.filter(f => f.status === 'completed').forEach(f => {
        const filename = f.file.name;
        const r = results[filename] || {};
        const formType = f.form_type || r.form_type || '—';
        const exceptions = liveExceptions[filename] || [];
        exceptions.forEach(exc => {
            allCards.push({ exc, formType, filename, result: r });
        });
    });

    // Stats — driven by allCards (always accurate)
    const totalExc = allCards.length;
    const affectedForms = new Set(allCards.map(c => c.filename)).size;
    const allConfs = Object.values(results).filter(r => r?.document_confidence).map(r => r.document_confidence);
    const avgConf = allConfs.length ? Math.round(allConfs.reduce((s, v) => s + v, 0) / allConfs.length * 100) : null;

    const filterCards = (card) => {
        if (filterType === 'All Types') return true;
        const code = (card.exc.code || '').toUpperCase();
        if (filterType === 'Data Mismatch') return code.includes('MISMATCH') || code.includes('NEQ') || code.includes('GT') || code.includes('LT') || code.includes('VARIANCE');
        if (filterType === 'Missing Doc') return code.includes('MISSING') || code.includes('ZERO') || code.includes('BLANK') || code.includes('NULL');
        if (filterType === 'Calculation') return code.includes('CALC') || code.includes('MATH') || code.includes('SUM');
        if (filterType === 'IRS Flag') return code.includes('IRS') || code.includes('FLAG') || code.includes('RULE') || code.includes('SALT');
        return true;
    };

    const visible = allCards.filter(filterCards);

    return (
        <div>
            {/* Stats header */}
            <div className="queue-header">
                <div className="queue-stat">
                    <div>
                        <div className="num" style={{ color: 'var(--red)' }}>{totalExc}</div>
                        <div className="label">Open Exceptions</div>
                    </div>
                </div>
                <div className="queue-stat">
                    <div>
                        <div className="num">
                            {avgConf !== null
                                ? <span style={{ color: 'var(--green)' }}>{avgConf}%</span>
                                : '14m'}
                        </div>
                        <div className="label">{avgConf !== null ? 'Avg Confidence' : 'Avg Resolution'}</div>
                    </div>
                </div>
                <div className="queue-stat">
                    <div>
                        <div className="num" style={{ color: 'var(--green)' }}>
                            {affectedForms > 0 ? affectedForms : '89%'}
                        </div>
                        <div className="label">{affectedForms > 0 ? 'Affected Forms' : 'AI Accuracy'}</div>
                    </div>
                </div>
                <div style={{ flex: 1 }} />
                <div className="filter-chips">
                    {['All Types', 'Data Mismatch', 'Missing Doc', 'Calculation', 'IRS Flag'].map(f => (
                        <span
                            key={f}
                            className={`filter-chip${filterType === f ? ' active' : ''}`}
                            onClick={() => setFilterType(f)}
                        >{f}</span>
                    ))}
                </div>
            </div>

            {/* Empty state */}
            {totalExc === 0 ? (
                <div style={{ padding: '48px 20px', textAlign: 'center', color: 'var(--text-muted)', background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)' }}>
                    <div style={{ fontSize: 28, marginBottom: 10, opacity: .4 }}>✅</div>
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>No exceptions found</div>
                    <div style={{ fontSize: 12 }}>
                        {files.length === 0
                            ? 'Upload and process a tax form from Ingestion Hub to see exceptions here.'
                            : 'All uploaded documents passed validation with no exceptions.'}
                    </div>
                </div>
            ) : (
                <>
                    {visible.length === 0 && filterType !== 'All Types' && (
                        <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                            No exceptions match this filter.
                        </div>
                    )}
                    <div className="exception-grid" id="exception-grid-container">
                        {visible.map((card) => (
                            <LiveExcCard
                                key={`${card.filename}-${card.exc.code || 'nocode'}-${card.exc.field || 'nofield'}`}
                                exc={card.exc}
                                formType={card.formType}
                                filename={card.filename}
                                apiUrl={apiUrl}
                                documentId={card.result?.document_id}
                                validationError={fieldErrors[card.filename]?.[card.exc.field] || null}
                                isSubmitting={!!submitting[card.filename]}
                                onSubmit={(field, value) =>
                                    handleCardSubmit(card.filename, field, value, card.formType)
                                }
                                onEscalate={(code, field) => {
                                    setLiveExceptions(prev => ({
                                        ...prev,
                                        [card.filename]: (prev[card.filename] || []).filter(e => {
                                            const eKey = `${e.code || ''}:${e.field || ''}`;
                                            const target = `${code || ''}:${field || ''}`;
                                            return eKey !== target;
                                        })
                                    }));
                                }}
                            />
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: DOCUMENTS  (live from files + results)
// ═══════════════════════════════════════════════════════════════════════════
function PageDocuments({ files, results, events, onDrop, fileInputRef }) {
    const [isDrag, setIsDrag] = useState(false);

    // Build rows: prefer files state, fall back to events, then static
    const liveRows = files.map(f => {
        const r = results[f.file.name];
        const pct = r?.document_confidence !== undefined ? Math.round(r.document_confidence * 100) : null;
        return {
            file: f.file.name,
            type: f.form_type || r?.form_type || '—',
            size: `${(f.file.size / 1024).toFixed(0)} KB`,
            date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
            status: getStatusFromFile(f, r),
            conf: pct !== null ? `${pct}%` : null,
            confCls: confClass(r?.document_confidence),
            stage: getStageFromFile(f, r),
            excCount: (r?.exceptions?.length || 0) + (r?.fixable_exceptions?.length || 0),
        };
    });

    const tableRows = liveRows;

    return (
        <div>
            {/* Summary bar if files exist */}
            {liveRows.length > 0 && (
                <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                    {[
                        ['Total', liveRows.length, null],
                        ['Complete', liveRows.filter(r => r.status === 'approved').length, 'green'],
                        ['Processing', liveRows.filter(r => r.status === 'processing').length, null],
                        ['Exceptions', liveRows.filter(r => r.status === 'exception').length, 'red'],
                    ].map(([label, count, color]) => count > 0 ? (
                        <div key={label} style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, color: color ? `var(--${color})` : 'var(--text-primary)' }}>{count}</span>
                            <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                        </div>
                    ) : null)}
                </div>
            )}

            <table className="data-table">
                <thead>
                    <tr>
                        <th>File Name</th>
                        <th>Form Type</th>
                        <th>Size</th>
                        <th>Uploaded</th>
                        <th>Stage</th>
                        <th>Status</th>
                        <th>Confidence</th>
                        <th>Exceptions</th>
                    </tr>
                </thead>
                <tbody>
                    {tableRows.length > 0 ? tableRows.map((r, i) => (
                        <tr key={i}>
                            <td style={{ fontWeight: 500, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.file}</td>
                            <td className="mono">{r.type}</td>
                            <td className="mono" style={{ color: 'var(--text-muted)' }}>{r.size || '—'}</td>
                            <td className="mono">{r.date}</td>
                            <td style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r.stage || '—'}</td>
                            <td><StatusPill status={r.status} /></td>
                            <td><span className={`confidence-badge ${r.confCls || ''}`}>{r.conf || '—'}</span></td>
                            <td>
                                {r.excCount > 0
                                    ? <span style={{ background: 'var(--red-bg)', color: 'var(--red)', border: '1px solid var(--red-border)', borderRadius: 10, padding: '2px 8px', fontSize: 10, fontWeight: 700 }}>{r.excCount} found</span>
                                    : r.status === 'approved' ? <span style={{ color: 'var(--green)', fontSize: 11 }}>✓ None</span>
                                        : <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>
                                }
                            </td>
                        </tr>
                    )) : (
                        <tr>
                            <td colSpan={8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)', fontSize: 13 }}>
                                <div style={{ fontSize: 24, marginBottom: 8, opacity: .4 }}>📂</div>
                                No documents uploaded yet. Drop a file above to begin.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}

function PageAgent({ stats, logs, files, results }) {
    const [logFilter, setLogFilter] = useState('All');
    const isActive = (stats.active_sessions || 0) > 0;

    const filtered = logFilter === 'All' ? logs
        : logs.filter(l => {
            const a = (l.action || '').toUpperCase();
            if (logFilter === 'Errors') return a.includes('ERROR');
            if (logFilter === 'Warnings') return a.includes('WARN');
            if (logFilter === 'Completed') return a.includes('COMPLETE') || a.includes('SUCCESS');
            return true;
        });

    const logClass = (action) => {
        const a = (action || '').toUpperCase();
        if (a.includes('ERROR')) return 'error';
        if (a.includes('WARN')) return 'warning';
        if (a.includes('COMPLETE') || a.includes('SUCCESS')) return 'success';
        return 'info';
    };

    const displayLogs = filtered.length > 0 ? filtered : [];

    return (
        <div>
            <div className="agent-bar">
                <div className="agent-status">
                    <div className={`agent-dot ${isActive ? 'active' : 'idle'}`} /> {isActive ? 'Processing' : 'Idle'}
                </div>
                <div className="topbar-sep" style={{ height: 20, width: 1, background: 'var(--border)' }} />
                <div className="agent-metric">Active Jobs: <strong>{stats.active_sessions ?? 0}</strong></div>
                <div className="agent-metric">Events Logged: <strong>{stats.events_logged ?? 0}</strong></div>
                <div className="agent-metric">Total Sessions: <strong>{stats.total_sessions ?? 0}</strong></div>
                <div className="agent-metric">AI Actions: <strong>{stats.agent_actions_logged ?? 0}</strong></div>
                <div style={{ flex: 1 }} />
                <button className="btn btn-secondary" style={{ fontSize: 11 }}>Pause Agent</button>
            </div>
            <div className="agent-table-wrap">
                <table className="data-table">
                    <thead><tr><th>File</th><th>Task</th><th>Stage</th><th>Confidence</th><th>Duration</th><th>Status</th></tr></thead>
                    <tbody>
                        {files.length > 0 ? files.map((f, i) => {
                            const r = results[f.file.name];
                            const pct = r?.document_confidence !== undefined ? Math.round(r.document_confidence * 100) : null;
                            const stage = getStageFromFile(f, r);
                            const status = getStatusFromFile(f, r);
                            const progress = status === 'approved' ? 100 : status === 'exception' ? 60 : status === 'processing' ? 40 : 10;
                            const barColor = status === 'approved' ? 'green' : status === 'exception' ? 'amber' : 'blue';
                            return (
                                <tr key={i}>
                                    <td style={{ fontWeight: 500, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.file.name}</td>
                                    <td>{f.form_type || r?.form_type || 'Processing'}</td>
                                    <td style={{ minWidth: 120 }}>
                                        <div className="progress-bar"><div className={`progress-bar-fill ${barColor}`} style={{ width: `${progress}%` }} /></div>
                                        <span className="mono" style={{ fontSize: 10, color: 'var(--text-muted)' }}>{progress}%</span>
                                    </td>
                                    <td><span className={`confidence-badge ${confClass(r?.document_confidence)}`}>{pct !== null ? `${pct}%` : '—'}</span></td>
                                    <td className="mono">—</td>
                                    <td><StatusPill status={status} /></td>
                                </tr>
                            );
                        }) : (
                            <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)', fontSize: 12 }}>No active jobs. Upload a document from Ingestion Hub.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
            <div className="dash-section-title">Agent Log</div>
            <div className="log-filters">
                {['All', 'Errors', 'Warnings', 'Completed'].map(f => (
                    <span key={f} className={`filter-chip${logFilter === f ? ' active' : ''}`} onClick={() => setLogFilter(f)}>{f}</span>
                ))}
            </div>
            <div className="agent-log">
                {displayLogs.slice(-50).map((l, i) => {
                    const ts = l.timestamp ? l.timestamp.split('T')[1]?.split('.')[0] || '' : '';
                    return (
                        <div key={i} className={`log-line ${logClass(l.action)}`}>
                            <span className="timestamp">{ts}</span>[{l.action || 'LOG'}] {l.detail}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: INGESTION HUB
// ═══════════════════════════════════════════════════════════════════════════
function PageIngestion({
    apiUrl, files, results, activeIngestionFile, setActiveIngestionFile,
    extracting, loadingMsg, performExtraction, processFiles, removeFile,
    showSensitive, setShowSensitive, showSidePdf, setShowSidePdf,
    pdfUrl, humanEdits, setHumanEdits, savingReview, setSavingReview,
    handleFieldEdit, sessionId, events, setResults,
}) {
    const [editMode, setEditMode] = useState(false);
    const [editedFields, setEditedFields] = useState({});
    const [activeResultTab, setActiveResultTab] = useState('fields');
    const fileInputRef = useRef(null);
    const dropRef = useRef(null);
    const [isDrag, setIsDrag] = useState(false);
    const [approving, setApproving] = useState(false);
    const [savedSnap, setSavedSnap] = useState(false);  // brief "Saved ✓" feedback

    const activeResult = activeIngestionFile ? results[activeIngestionFile] : null;

    // Helper: save the currently-visible extraction data to local_extraction/
    const saveCurrentSnapshot = async (overrideData?: object) => {
        const data = overrideData || activeResult;
        if (!data || !activeIngestionFile) return;
        try {
            await fetch(`${apiUrl}/save-snapshot`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_id:         (data as any).document_id || undefined,
                    form_type:           (data as any).form_type,
                    filename:            activeIngestionFile,
                    pdf_type:            (data as any).pdf_type || 'digital',
                    data:                (data as any).data || (data as any).extracted_fields || {},
                    exceptions:          (data as any).exceptions || [],
                    document_confidence: (data as any).document_confidence ?? 1.0,
                    field_confidence:    (data as any).field_confidence || {},
                }),
            });
            setSavedSnap(true);
            setTimeout(() => setSavedSnap(false), 2000);
        } catch { /* non-blocking */ }
    };

    // Queue table rows — time from uploadedAt, pages from extract result
    const queueRows = files.map(f => {
        const r = results[f.file.name];
        const pages = r?.total_pages ?? r?.page_count ?? r?.pages ?? '—';
        return {
            file: f.file.name,
            client: '—',
            type: f.form_type || r?.form_type || '—',
            pages,
            time: f.uploadedAt || '—',
            status: f.status === 'queued' ? 'pending' : f.status === 'processing' ? 'processing' : f.status === 'completed' ? 'approved' : 'exception',
            isActive: f.file.name === activeIngestionFile,
        };
    });

    const handleApproveAll = async () => {
        if (!activeResult) return;
        setApproving(true);
        const formType = activeResult.form_type || activeIngestionFile;
        const fields = activeResult.extracted_fields || activeResult.data || {};
        const flat = flattenObject(fields);
        const fixes = Object.entries(flat).map(([field, val]) => ({
            field,
            new_value: val,
        }));
        const humanVerifiedFields = Object.keys(flat);
        try {
            const res = await fetch(`${apiUrl}/apply-fixes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    form_type: formType,
                    data: fields,
                    fixes,
                    pdf_type: activeResult.pdf_type || 'digital',
                    human_verified_fields: humanVerifiedFields,
                    document_id: activeResult?.document_id || undefined,
                    context: { filename: activeIngestionFile, document_id: activeResult?.document_id || undefined },
                }),
            });
            if (res.ok) {
                const updated = await res.json();
                const merged = { ...results[activeIngestionFile], ...updated, validation_complete: true };
                setResults(prev => ({ ...prev, [activeIngestionFile]: merged }));
                // Save the approved state immediately to local_extraction/
                await saveCurrentSnapshot(merged);
            }
        } catch (e) {
            console.error('handleApproveAll failed:', e);
        }
        setApproving(false);
    };

    const handleSaveEdits = async () => {
        if (!activeIngestionFile || !Object.keys(editedFields).length) return;
        const formType = (activeResult?.form_type) || activeIngestionFile;
        const fields   = activeResult?.extracted_fields || activeResult?.data || {};
        const fixes = Object.entries(editedFields).map(([field, val]) => ({
            field,
            new_value: val,
        }));
        try {
            const res = await fetch(`${apiUrl}/apply-fixes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    form_type: formType,
                    data: fields,
                    fixes,
                    pdf_type: activeResult?.pdf_type || 'digital',
                    human_verified_fields: Object.keys(editedFields),
                    document_id: activeResult?.document_id || undefined,
                    context: { filename: activeIngestionFile, document_id: activeResult?.document_id || undefined },
                }),
            });
            if (res.ok) {
                const updated = await res.json();
                const merged = { ...results[activeIngestionFile], ...updated };
                setResults(prev => ({ ...prev, [activeIngestionFile]: merged }));
                // Save edited state immediately to local_extraction/
                await saveCurrentSnapshot(merged);
            }
        } catch (e) {
            console.error('handleSaveEdits failed:', e);
        }
        setEditMode(false);
        setEditedFields({});
    };

    // Render flat field list for extraction panel
    const renderFieldRows = () => {
        if (!activeResult) return null;
        const data = activeResult.extracted_fields || activeResult.data || {};
        const conf = activeResult.field_confidence || {};
        const flat = flattenObject(data);
        return Object.entries(flat).slice(0, 12).map(([key, val]) => {
            const c = conf[key];
            const pct = c !== undefined ? Math.round(c * 100) : null;
            const color = pct === null ? 'var(--text-muted)' : pct >= 90 ? 'var(--green)' : pct >= 70 ? 'var(--amber)' : 'var(--red)';
            const isLow = pct !== null && pct < 80;
            const label = key.split('.').pop().replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            return (
                <div key={key} className={`field-row${isLow ? ' low-conf' : ''}`}>
                    <span className="field-name" style={{ width: 140 }}>{label}</span>
                    {editMode
                        ? <input style={{ flex: 1, fontFamily: 'monospace', fontSize: 12, padding: '2px 6px', border: '1px solid var(--border)', borderRadius: 4, outline: 'none' }}
                            defaultValue={String(val ?? '')}
                            onChange={e => setEditedFields(prev => ({ ...prev, [key]: e.target.value }))} />
                        : <span className="field-value">{maskValue(String(val ?? ''), key, showSensitive)}</span>
                    }
                    <span className="field-conf" style={{ color }}>{pct !== null ? `${pct}%` : '—'}</span>
                </div>
            );
        });
    };

    return (
        <div>
            {/* Upload zone */}
            <div ref={dropRef} className="upload-zone" style={{ cursor: 'pointer', ...(isDrag ? { borderColor: 'var(--border-light)', background: 'rgba(0,0,0,0.02)' } : {}) }}
                onDragOver={e => { e.preventDefault(); setIsDrag(true) }} onDragLeave={() => setIsDrag(false)}
                onDrop={e => { e.preventDefault(); setIsDrag(false); if (e.dataTransfer.files[0]) processFiles(e.dataTransfer.files) }}
                onClick={() => fileInputRef.current?.click()}>
                <input ref={fileInputRef} type="file" accept="application/pdf,image/png,image/jpeg,image/webp" multiple style={{ display: 'none' }}
                    onChange={e => { if (e.target.files[0]) processFiles(e.target.files); e.target.value = ''; }} />
                <div className="upload-zone-icon">☁️</div>
                <div className="upload-zone-text">Drop files to begin AI ingestion</div>
                <div className="upload-zone-sub">PDF, CSV, JPG, PNG — AI auto-detects type, extracts fields, matches to client</div>
            </div>

            {/* File chips if queued */}
            {files.filter(f => f.status === 'queued').length > 0 && (
                <div style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--text-secondary)' }}>Ready ({files.filter(f => f.status === 'queued').length})</span>
                        <button className="btn btn-primary" style={{ fontSize: 11 }} onClick={performExtraction} disabled={extracting}>
                            {extracting ? loadingMsg || 'Processing…' : '→ Run Pipeline'}
                        </button>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {files.map((f, i) => f.status === 'queued' && (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 12px', fontSize: 12 }}>
                                <span style={{ fontWeight: 500 }}>{f.file.name}</span>
                                <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, fontSize: 14, lineHeight: 1 }} onClick={() => removeFile(i)}>✕</button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Split: queue + preview */}
            <div className="ingestion-split">
                {/* Left: queue table */}
                <div>
                    <div className="dash-section-title mb-16">Ingestion Queue</div>
                    <table className="data-table">
                        <thead><tr><th>File</th><th>Client</th><th>Type</th><th>Pages</th><th>Time</th><th>Status</th></tr></thead>
                        <tbody>
                            {queueRows.length > 0 ? queueRows.map((r, i) => (
                                <tr key={i} style={{ background: r.isActive ? 'var(--accent-5)' : '', cursor: 'pointer' }}
                                    onClick={() => { if (r.file !== '—' && results[r.file]) setActiveIngestionFile(r.file); }}>
                                    <td style={{ fontWeight: 500 }}>{r.file}</td><td>{r.client}</td><td className="mono">{r.type}</td>
                                    <td className="mono">{r.pages}</td><td className="mono">{r.time}</td>
                                    <td><StatusPill status={r.status} /></td>
                                </tr>
                            )) : (
                                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)', fontSize: 12 }}>No files uploaded yet</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Right: extraction preview */}
                <div className="extraction-panel">
                    <div className="extraction-title">AI Extraction Preview</div>
                    <div id="extraction-panel-subtitle" style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
                        {activeResult ? `${activeIngestionFile} · ${activeResult.form_type || 'Processing...'}` : 'Waiting for document...'}
                    </div>

                    {activeResult ? (
                        <>
                            {/* Confidence bar */}
                            {activeResult.document_confidence !== undefined && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, padding: '8px 12px', background: 'var(--surface-2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Doc Confidence</span>
                                    <div style={{ flex: 1, height: 4, background: 'var(--surface-3)', borderRadius: 2 }}>
                                        <div style={{ height: 4, borderRadius: 2, background: activeResult.document_confidence >= .9 ? 'var(--green)' : activeResult.document_confidence >= .75 ? 'var(--amber)' : 'var(--red)', width: `${Math.round(activeResult.document_confidence * 100)}%` }} />
                                    </div>
                                    <span style={{ fontSize: 11, fontFamily: 'monospace', fontWeight: 600, color: activeResult.document_confidence >= .9 ? 'var(--green)' : activeResult.document_confidence >= .75 ? 'var(--amber)' : 'var(--red)' }}>{Math.round(activeResult.document_confidence * 100)}%</span>
                                </div>
                            )}

                            {/* Tabs for advanced views */}
                            <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 12 }}>
                                {['fields', 'json', 'csv', 'exceptions'].map(t => (
                                    <button key={t} onClick={() => setActiveResultTab(t)}
                                        style={{ padding: '6px 12px', fontSize: 11, fontWeight: activeResultTab === t ? 600 : 400, color: activeResultTab === t ? 'var(--text-primary)' : 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', borderBottom: activeResultTab === t ? '2px solid var(--text-primary)' : '2px solid transparent', fontFamily: 'Inter', transition: 'color .15s' }}>
                                        {t.charAt(0).toUpperCase() + t.slice(1)}
                                    </button>
                                ))}
                                <div style={{ flex: 1 }} />
                                <button
                                    onClick={() => saveCurrentSnapshot()}
                                    title="Save JSON to local_extraction/"
                                    style={{
                                        padding: '4px 8px', background: savedSnap ? 'rgba(22,163,74,.12)' : 'none',
                                        border: savedSnap ? '1px solid rgba(22,163,74,.3)' : '1px solid transparent',
                                        borderRadius: 'var(--radius-sm)',
                                        cursor: 'pointer', color: savedSnap ? 'var(--green)' : 'var(--text-muted)',
                                        fontSize: 11, fontWeight: 600, transition: 'all .2s',
                                        display: 'flex', alignItems: 'center', gap: 4,
                                    }}>
                                    {savedSnap ? '✓ Saved' : '💾 Save'}
                                </button>
                                <button style={{ padding: '4px 6px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 14 }} onClick={() => setShowSensitive(!showSensitive)} title={showSensitive ? 'Hide sensitive' : 'Show sensitive'}>
                                    {showSensitive ? '🙈' : '👁'}
                                </button>
                            </div>

                            {activeResultTab === 'fields' && (
                                <div>{renderFieldRows()}</div>
                            )}

                            {activeResultTab === 'json' && (
                                <div style={{ background: 'var(--surface-2)', borderRadius: 'var(--radius-sm)', padding: 12, maxHeight: 300, overflowY: 'auto', border: '1px solid var(--border)' }}>
                                    <pre style={{ fontFamily: 'monospace', fontSize: 11, lineHeight: 1.6 }} dangerouslySetInnerHTML={{ __html: syntaxHighlight(activeResult.data || activeResult.extracted_fields || {}) }} />
                                </div>
                            )}

                            {activeResultTab === 'csv' && (
                                <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                        <thead><tr><th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Field</th><th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>Value</th></tr></thead>
                                        <tbody>
                                            {Object.entries(flattenObject(activeResult.data || activeResult.extracted_fields || {})).map(([k, v], i) => (
                                                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                                                    <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>{k}</td>
                                                    <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 11 }}>{String(maskValue(v, k, showSensitive))}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            {activeResultTab === 'exceptions' && (
                                <div>
                                    {(activeResult.exceptions || []).length > 0 ? (
                                        <ExceptionManager
                                            apiUrl={apiUrl}
                                            formType={activeResult.form_type}
                                            data={activeResult.extracted_fields || activeResult.data}
                                            fixableExceptions={activeResult.fixable_exceptions || []}
                                            reviewExceptions={activeResult.review_exceptions || []}
                                            allExceptions={activeResult.exceptions || []}
                                            summary={activeResult.summary || {}}
                                            humanVerifiedFields={activeResult.human_verified_fields || []}
                                            showSidePdf={false}
                                            setShowSidePdf={() => { }}
                                            onResolved={updated => {
                                                if (setResults) {
                                                    // Handle both stateless (raw result) and session (envelope) responses
                                                    const resultData = updated.data && updated.ok ? updated.data : updated;
                                                    setResults(prev => ({
                                                        ...prev,
                                                        [activeIngestionFile]: {
                                                            ...prev[activeIngestionFile],
                                                            ...resultData,
                                                            extracted_fields: resultData.extracted_fields || resultData.data || prev[activeIngestionFile].extracted_fields
                                                        }
                                                    }));
                                                }
                                            }}
                                            ignoredIds={activeResult.ignoredIds || new Set()}
                                            setIgnoredIds={fn => { if (setResults) setResults(prev => { const cur = prev[activeIngestionFile] || {}; const next = typeof fn === 'function' ? fn(cur.ignoredIds || new Set()) : fn; return { ...prev, [activeIngestionFile]: { ...cur, ignoredIds: next } }; }); }}
                                        />
                                    ) : (
                                        <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>No exceptions detected ✓</div>
                                    )}
                                </div>
                            )}

                            {/* Action buttons */}
                            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                                {!editMode ? (
                                    <>
                                        <button className="btn btn-success" style={{ flex: 1 }} onClick={handleApproveAll} disabled={approving}>
                                            {approving ? 'Approving…' : 'Approve All'}
                                        </button>
                                        <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setEditMode(true)}>Edit Fields</button>
                                    </>
                                ) : (
                                    <>
                                        <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleSaveEdits}>Save Changes</button>
                                        <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => { setEditMode(false); setEditedFields({}); }}>Cancel</button>
                                    </>
                                )}
                            </div>
                        </>
                    ) : (
                        <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
                            <div style={{ fontSize: 28, marginBottom: 10, opacity: .3 }}>📋</div>
                            <div style={{ fontSize: 13, marginBottom: 4 }}>No extraction yet</div>
                            <div style={{ fontSize: 12 }}>Upload a document above to see extracted fields</div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: AI RULES
// ═══════════════════════════════════════════════════════════════════════════
function PageAIRules() {
    return (
        <div className="settings-layout">
            <div className="settings-section">
                <h3>AI Behavior</h3>
                <div className="setting-row">
                    <div className="setting-info"><div className="setting-label">Auto-Approval Confidence Threshold</div><div className="setting-desc">Documents above this level are auto-approved without CPA review</div></div>
                    <Slider defaultValue={92} min={50} max={100} />
                </div>
                <div className="setting-row">
                    <div className="setting-info"><div className="setting-label">Exception Flagging Threshold</div><div className="setting-desc">Items below this confidence are flagged for manual review</div></div>
                    <Slider defaultValue={75} min={30} max={95} />
                </div>
                {[['Auto-Approve High-Confidence Items', 'Skip CPA review for items above threshold', false], ['AI Document Matching', 'Auto-match uploads to clients based on content analysis', true], ['Prior Year Variance Detection', 'Auto-flag variances exceeding threshold vs prior year', true], ['Automated Client Notifications', 'AI can send portal requests for missing documents automatically', false]].map(([l, d, c]) => (
                    <div key={l} className="setting-row"><div className="setting-info"><div className="setting-label">{l}</div><div className="setting-desc">{d}</div></div><Toggle defaultChecked={c} /></div>
                ))}
            </div>
            <div className="settings-section">
                <h3>Exception Escalation Rules</h3>
                <div className="setting-row"><div className="setting-info"><div className="setting-label">Auto-Escalate High Severity</div><div className="setting-desc">Automatically escalate exceptions with severity "High" to senior CPA</div></div><Toggle defaultChecked={true} /></div>
                <div className="setting-row"><div className="setting-info"><div className="setting-label">Escalation Timeout</div><div className="setting-desc">Auto-escalate unresolved exceptions after this period</div></div>
                    <select style={{ fontSize: 12 }}><option>24 hours</option><option>48 hours</option><option>72 hours</option><option>1 week</option></select>
                </div>
                <div className="setting-row"><div className="setting-info"><div className="setting-label">IRS Rule Flags</div><div className="setting-desc">Always flag when AI detects potential IRS compliance issues</div></div><Toggle defaultChecked={true} /></div>
            </div>
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: REPORTS
// ═══════════════════════════════════════════════════════════════════════════
function PageReports({ apiUrl, sessionId, results }) {
    const handleExport = async (format = 'json') => {
        const sid = sessionId;
        if (sid) {
            try {
                const r = await fetch(`${apiUrl}/api/export`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json', 'X-Session-ID': sid },
                    body: JSON.stringify({ format }),
                });
                if (r.ok) {
                    const b = await r.blob();
                    const cd = r.headers.get('Content-Disposition');
                    const name = (cd && cd.split('filename=')[1]) || `export.${format}`;
                    const a = Object.assign(document.createElement('a'), {
                        href: URL.createObjectURL(b),
                        download: name,
                    });
                    a.click();
                    URL.revokeObjectURL(a.href);
                    return;
                }
            } catch { /* fall through to client-side export */ }
        }

        if (!results || !Object.keys(results).length) {
            alert('No extracted data to export. Upload and process a document first.');
            return;
        }
        const exportData = {
            exported_at: new Date().toISOString(),
            documents: Object.entries(results).map(([filename, r]) => ({
                filename,
                form_type: r?.form_type,
                data: r?.extracted_fields || r?.data || {},
                exceptions_count: (r?.exceptions?.length || 0) + (r?.fixable_exceptions?.length || 0),
            })),
        };

        if (format === 'csv') {
            const first = exportData.documents[0];
            if (!first) return;
            const flat = Object.entries(first.data || {});
            const csv = ['field,value', ...flat.map(([k, v]) => `${k},${String(v ?? '')}`)].join('\n');
            const b = new Blob([csv], { type: 'text/csv' });
            const a = Object.assign(document.createElement('a'), {
                href: URL.createObjectURL(b),
                download: `taxscio_export.csv`,
            });
            a.click();
            URL.revokeObjectURL(a.href);
        } else {
            const json = JSON.stringify(exportData, null, 2);
            const b = new Blob([json], { type: 'application/json' });
            const a = Object.assign(document.createElement('a'), {
                href: URL.createObjectURL(b),
                download: `taxscio_export.json`,
            });
            a.click();
            URL.revokeObjectURL(a.href);
        }
    };
    const reports = [
        ['📊', 'Filing Summary Report', 'Overview of all filings: completed, in-progress, pending. Includes refund/balance totals and form type breakdown.'],
        ['⚡', 'Exception Analytics', 'Exception frequency by type, resolution time, AI accuracy rate, and trending patterns across clients.'],
        ['🕐', 'Time & Productivity', 'CPA hours by client, task breakdown, AI vs manual processing ratios, and efficiency metrics.'],
        ['👥', 'CPA Workload Report', 'Client distribution across CPAs, active exceptions per assignee, and workload balancing recommendations.'],
        ['💰', 'Revenue & Billing', 'Billing codes by client, estimated vs actual hours, outstanding invoices, and fee schedule compliance.'],
        ['🤖', 'AI Performance Report', 'AI confidence trends, auto-approval rates, false positive/negative analysis, and processing throughput.'],
        ['📅', 'Deadline Compliance', 'Filing deadline adherence, extension tracking, late filing risks, and IRS calendar alignment.'],
        ['🔍', 'Audit Trail Export', 'Immutable log of every AI and human action — filterable by client, date range, action type. Compliance-ready.'],
        ['📈', 'YoY Client Comparison', 'Multi-year income, deduction, and credit trends per client. Spot planning opportunities and anomalies.'],
    ];
    return (
        <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700 }}>Reports & Analytics</div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <select style={{ fontSize: 12 }}><option>TY 2025</option><option>TY 2024</option></select>
                    <button className="btn btn-primary" onClick={handleExport}>Export All Reports</button>
                </div>
            </div>
            <div className="report-grid">
                {reports.map(([icon, title, desc]) => (
                    <div key={title} className="report-card">
                        <div className="report-card-icon">{icon}</div>
                        <div className="report-card-title">{title}</div>
                        <div className="report-card-desc">{desc}</div>
                    </div>
                ))}
            </div>
            <div className="settings-section" style={{ marginTop: 8 }}>
                <h3>Scheduled Reports</h3>
                {[['Weekly Filing Summary', 'Delivered every Monday at 8 AM to firm partners', true], ['Daily Exception Digest', 'Morning summary of open exceptions and AI flags', true], ['Monthly AI Performance Review', 'Accuracy, throughput, and exception analysis for the month', false]].map(([l, d, c]) => (
                    <div key={l} className="setting-row"><div className="setting-info"><div className="setting-label">{l}</div><div className="setting-desc">{d}</div></div><Toggle defaultChecked={c} /></div>
                ))}
            </div>
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: IDENTITY & VERIFICATION
// ═══════════════════════════════════════════════════════════════════════════
function PageIdentity() {
    const [activeTab, setActiveTab] = useState('users');

    return (
        <div>
            <div style={{ marginBottom: 24, paddingBottom: 20, borderBottom: '1px solid var(--border)' }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Identity Management</div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 600 }}>Manage users, teams, and access permissions for your organization.</div>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
                {[['users', 'Users'], ['teams', 'Teams'], ['roles', 'Roles']].map(([tab, label]) => (
                    <div
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        style={{
                            padding: '12px 16px',
                            fontSize: 13,
                            fontWeight: 500,
                            cursor: 'pointer',
                            borderBottom: activeTab === tab ? '2px solid #6366f1' : 'none',
                            color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-muted)',
                            transition: 'all .2s ease',
                        }}
                    >
                        {label}
                    </div>
                ))}
            </div>

            {/* Users Tab */}
            {activeTab === 'users' && (
                <div>
                    <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <div style={{ fontSize: 24, marginBottom: 8, opacity: .4 }}>📋</div>
                        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4, color: 'var(--text-secondary)' }}>Users</div>
                        <div style={{ fontSize: 12 }}>Users section coming soon</div>
                    </div>
                </div>
            )}

            {/* Teams Tab */}
            {activeTab === 'teams' && (
                <div>
                    <div className="settings-section" style={{ border: 'none', background: 'none', padding: 0, marginBottom: 0 }}>
                        <h3 style={{ marginBottom: 16 }}>Team Management</h3>
                        {[['Michael Chen', 'Senior CPA · Admin · 84 active clients'], ['Jessica Wu', 'CPA · Member · 72 active clients'], ['Amanda Lee', 'Staff Accountant · Member · 58 active clients'], ['David Park', 'Tax Intern · Limited · 24 active clients']].map(([name, desc]) => (
                            <div key={name} className="setting-row"><div className="setting-info"><div className="setting-label">{name}</div><div className="setting-desc">{desc}</div></div><button className="btn btn-ghost" style={{ fontSize: 11 }}>Manage</button></div>
                        ))}
                        <div style={{ marginTop: 12 }}><button className="btn btn-secondary">+ Invite Team Member</button></div>
                    </div>
                </div>
            )}

            {/* Roles Tab */}
            {activeTab === 'roles' && (
                <div>
                    <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <div style={{ fontSize: 24, marginBottom: 8, opacity: .4 }}>🔐</div>
                        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4, color: 'var(--text-secondary)' }}>Roles & Permissions</div>
                        <div style={{ fontSize: 12 }}>Roles management coming soon</div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: INTEGRATIONS
// ═══════════════════════════════════════════════════════════════════════════
function PageIntegrations() {
    const [tab, setTab] = useState('connected');
    const connected = [
        ['🏛', 'IRS E-File API', 'Direct electronic filing with IRS. Supports Forms 1040, 1065, 1120, 1120-S, 1041.', 'Last sync: 2 hours ago'],
        ['📗', 'QuickBooks Online', 'Sync client P&L, balance sheets, and transaction data. Auto-import for reconciliation.', '142 clients synced'],
        ['📁', 'Google Drive', 'Monitor shared folders for new client documents. Auto-ingest uploaded files.', '3 folders monitored'],
        ['✍️', 'DocuSign', 'E-signature workflows for Form 8879 and engagement letters. Track signing status.', 'Active'],
    ];
    const available = [
        ['📘', 'Xero', 'Alternative accounting platform. Sync financial data for clients using Xero.'],
        ['📦', 'Dropbox', 'Document source integration. Monitor folders and auto-ingest tax documents.'],
        ['💬', 'Slack', 'Real-time alerts for exceptions, filing confirmations, and deadline reminders.'],
        ['📧', 'Microsoft Outlook', 'Email integration for client communications and document ingestion from attachments.'],
        ['🔗', 'Zapier', 'Connect Taxscio to 5,000+ apps. Automate workflows across your entire tech stack.'],
        ['🏢', 'Salesforce', 'CRM sync for client management, engagement tracking, and sales pipeline.'],
    ];
    return (
        <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700 }}>Integrations</div>
                <button className="btn btn-secondary">Browse Marketplace</button>
            </div>
            <div className="tab-bar" style={{ marginBottom: 24 }}>
                {[['connected', 'Connected Services'], ['available', 'Available Integrations']].map(([id, label]) => (
                    <div key={id} className={`tab-item${tab === id ? ' active' : ''}`} onClick={() => setTab(id)}>{label}</div>
                ))}
            </div>
            {tab === 'connected' && (
                <div className="integ-grid">
                    {connected.map(([ic, t, d, s]) => (
                        <div key={t} className="integ-card"><div className="integ-card-icon">{ic}</div><div className="integ-card-info"><div className="integ-card-title">{t}</div><div className="integ-card-desc">{d}</div><div className="integ-card-status"><span className="status-pill approved">Connected</span><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s}</span></div></div></div>
                    ))}
                </div>
            )}
            {tab === 'available' && (
                <div className="integ-grid">
                    {available.map(([ic, t, d]) => (
                        <div key={t} className="integ-card"><div className="integ-card-icon">{ic}</div><div className="integ-card-info"><div className="integ-card-title">{t}</div><div className="integ-card-desc">{d}</div><div className="integ-card-status"><button className="btn btn-secondary" style={{ fontSize: 11 }}>Connect</button></div></div></div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: ORGANIZATION
// ═══════════════════════════════════════════════════════════════════════════
function PageOrganization() {
    const [tab, setTab] = useState('info');
    return (
        <div className="settings-layout" style={{ maxWidth: 800 }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Organization</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 24 }}>Manage your firm's profile, billing, and subscription details.</div>
            <div className="tab-bar" id="org-tabs">
                {[['info', 'Organization Info'], ['billing', 'Billing Information'], ['plan', 'Plan & Invoices']].map(([id, label]) => (
                    <div key={id} className={`tab-item${tab === id ? ' active' : ''}`} onClick={() => setTab(id)}>{label}</div>
                ))}
            </div>

            {tab === 'info' && (
                <div>
                    <div className="settings-section"><h3>Firm Details</h3>
                        <div className="form-grid">
                            <div className="form-group"><label className="form-label">Firm Name</label><input type="text" className="form-input" defaultValue="Chen & Associates CPAs" /></div>
                            <div className="form-group"><label className="form-label">DBA / Trade Name</label><input type="text" className="form-input" defaultValue="Chen & Associates" placeholder="Optional" /></div>
                            <div className="form-group"><label className="form-label">EIN (Tax ID)</label><input type="text" className="form-input" defaultValue="47-8291034" /></div>
                            <div className="form-group"><label className="form-label">PTIN</label><input type="text" className="form-input" defaultValue="P01234567" /></div>
                            <div className="form-group"><label className="form-label">EFIN</label><input type="text" className="form-input" defaultValue="123456" /></div>
                            <div className="form-group"><label className="form-label">Firm Type</label><select className="form-input"><option>CPA Firm</option><option>Enrolled Agent</option><option>Tax Prep Service</option><option>Accounting Firm</option></select></div>
                        </div>
                    </div>
                    <div className="settings-section"><h3>Contact Information</h3>
                        <div className="form-grid">
                            <div className="form-group"><label className="form-label">Primary Contact</label><input type="text" className="form-input" defaultValue="Michael Chen" /></div>
                            <div className="form-group"><label className="form-label">Email</label><input type="email" className="form-input" defaultValue="mchen@chenassociates.com" /></div>
                            <div className="form-group"><label className="form-label">Phone</label><input type="tel" className="form-input" defaultValue="(212) 555-0147" /></div>
                            <div className="form-group"><label className="form-label">Website</label><input type="url" className="form-input" defaultValue="https://chenassociates.com" /></div>
                        </div>
                    </div>
                    <div className="settings-section"><h3>Office Address</h3>
                        <div className="form-grid">
                            <div className="form-group full"><label className="form-label">Street Address</label><input type="text" className="form-input" defaultValue="450 Park Avenue, Suite 1200" /></div>
                            <div className="form-group"><label className="form-label">City</label><input type="text" className="form-input" defaultValue="New York" /></div>
                            <div className="form-group"><label className="form-label">State</label><select className="form-input"><option>NY</option><option>CA</option><option>TX</option><option>FL</option></select></div>
                            <div className="form-group"><label className="form-label">ZIP Code</label><input type="text" className="form-input" defaultValue="10022" /></div>
                            <div className="form-group"><label className="form-label">Country</label><select className="form-input"><option>United States</option></select></div>
                        </div>
                    </div>
                    <div className="settings-section"><h3>Branding</h3>
                        <div className="form-grid">
                            <div className="form-group"><label className="form-label">Firm Logo</label>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
                                    <div style={{ width: 48, height: 48, borderRadius: 'var(--radius)', background: 'var(--surface-3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700, color: 'var(--text-muted)' }}>C&A</div>
                                    <button className="btn btn-secondary" style={{ fontSize: 11 }}>Upload Logo</button>
                                    <button className="btn btn-ghost" style={{ fontSize: 11 }}>Remove</button>
                                </div>
                            </div>
                            <div className="form-group"><label className="form-label">Timezone</label>
                                <select className="form-input"><option>Eastern Time (ET) — UTC-5</option><option>Central Time (CT) — UTC-6</option><option>Mountain Time (MT) — UTC-7</option><option>Pacific Time (PT) — UTC-8</option></select>
                            </div>
                        </div>
                    </div>
                    <div className="form-actions"><button className="btn btn-secondary">Discard Changes</button><button className="btn btn-primary">Save Organization Info</button></div>
                </div>
            )}

            {tab === 'billing' && (
                <div>
                    <div className="settings-section"><h3>Payment Method</h3>
                        <div style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 20, display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                            <div style={{ width: 48, height: 32, borderRadius: 4, background: 'linear-gradient(135deg,#1a1f71,#2b4acb)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span style={{ color: '#fff', fontSize: 10, fontWeight: 700 }}>VISA</span></div>
                            <div style={{ flex: 1 }}><div style={{ fontSize: 13, fontWeight: 600 }}>Visa ending in 4242</div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Expires 08/2027 · Michael Chen</div></div>
                            <span className="status-pill approved">Default</span>
                            <button className="btn btn-ghost" style={{ fontSize: 11 }}>Edit</button>
                        </div>
                        <button className="btn btn-secondary" style={{ marginBottom: 8 }}>+ Add Payment Method</button>
                    </div>
                    <div className="settings-section"><h3>Billing Contact</h3>
                        <div className="form-grid">
                            <div className="form-group"><label className="form-label">Billing Name</label><input type="text" className="form-input" defaultValue="Chen & Associates CPAs" /></div>
                            <div className="form-group"><label className="form-label">Billing Email</label><input type="email" className="form-input" defaultValue="billing@chenassociates.com" /></div>
                            <div className="form-group"><label className="form-label">Phone</label><input type="tel" className="form-input" defaultValue="(212) 555-0147" /></div>
                            <div className="form-group"><label className="form-label">Tax Exempt</label><select className="form-input"><option>No</option><option>Yes — Upload Certificate</option></select></div>
                        </div>
                    </div>
                    <div className="form-actions"><button className="btn btn-secondary">Discard Changes</button><button className="btn btn-primary">Save Billing Info</button></div>
                </div>
            )}

            {tab === 'plan' && (
                <div>
                    <div className="settings-section"><h3>Current Plan</h3>
                        <div className="plan-cards">
                            {[
                                ['Starter', '$99', '/mo', 'For solo practitioners getting started with AI-powered tax prep.', ['Up to 50 clients', '1 CPA seat', 'AI document ingestion', 'Basic exception handling', 'Email support'], false],
                                ['Professional', '$299', '/mo', 'For growing firms with multiple CPAs and high-volume filing needs.', ['Unlimited clients', '5 CPA seats', 'Advanced AI processing', 'Full exception engine', 'API integrations', 'Priority support'], true],
                                ['Enterprise', 'Custom', '', 'For large firms requiring custom SLAs, dedicated support, and on-prem options.', ['Unlimited everything', 'Unlimited seats', 'Custom AI models', 'Dedicated account manager', 'SSO / SAML', 'On-premise deployment', '99.99% SLA'], false],
                            ].map(([name, price, sub, desc, features, isCurrent]) => (
                                <div key={name} className={`plan-card${isCurrent ? ' current' : ''}`}>
                                    {isCurrent && <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--green)', marginBottom: 8 }}>Current Plan</div>}
                                    <div className="plan-card-name">{name}</div>
                                    <div className="plan-card-price">{price}<span>{sub}</span></div>
                                    <div className="plan-card-desc">{desc}</div>
                                    <ul className="plan-card-features">{features.map(f => <li key={f}>{f}</li>)}</ul>
                                    <button className={`btn ${isCurrent ? 'btn-primary' : 'btn-secondary'}`} style={{ width: '100%', marginTop: 16, justifyContent: 'center', opacity: isCurrent ? .5 : 1, cursor: isCurrent ? 'default' : 'pointer' }}>
                                        {isCurrent ? 'Current Plan' : name === 'Starter' ? 'Downgrade' : 'Contact Sales'}
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="settings-section"><h3>Invoice History</h3>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead><tr>{['Invoice', 'Date', 'Amount', 'Status', 'Action'].map(h => <th key={h} style={{ textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.05em', padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>{h}</th>)}</tr></thead>
                            <tbody>
                                {[['INV-2026-003', 'Mar 1, 2026'], ['INV-2026-002', 'Feb 1, 2026'], ['INV-2026-001', 'Jan 1, 2026'], ['INV-2025-012', 'Dec 1, 2025'], ['INV-2025-011', 'Nov 1, 2025']].map(([inv, date]) => (
                                    <tr key={inv}><td style={{ padding: '10px 12px', fontWeight: 500, fontSize: 13 }}>{inv}</td><td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--text-secondary)' }}>{date}</td><td style={{ padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>$299.00</td><td style={{ padding: '10px 12px' }}><span className="status-pill approved">Paid</span></td><td style={{ padding: '10px 12px' }}><button className="btn btn-ghost" style={{ fontSize: 11 }}>Download PDF</button></td></tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE: SETTINGS
// ═══════════════════════════════════════════════════════════════════════════
function PageSettings({ onNavigate }) {
    const [activeTab, setActiveTab] = useState('storage');

    return (
        <div className="settings-layout">
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Settings</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 24 }}>Manage your personal preferences, team, and security settings.</div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid var(--border)' }}>
                {[['storage', 'Storage & Channels'], ['taxyears', 'Tax Years'], ['notifications', 'Notifications'], ['security', 'Security & Compliance']].map(([tab, label]) => (
                    <div
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        style={{
                            padding: '12px 16px',
                            fontSize: 13,
                            fontWeight: 500,
                            cursor: 'pointer',
                            borderBottom: activeTab === tab ? '2px solid #6366f1' : 'none',
                            color: activeTab === tab ? 'var(--text-primary)' : 'var(--text-muted)',
                            transition: 'all .2s ease',
                        }}
                    >
                        {label}
                    </div>
                ))}
            </div>

            {/* Storage & Channels Tab */}
            {activeTab === 'storage' && (
                <div>
                    <div className="settings-section"><h3>Storage & Channels</h3>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Document Storage</div><div className="setting-desc">Current usage: 2.4 GB of 10 GB</div></div><button className="btn btn-secondary" style={{ fontSize: 11 }}>Manage Storage</button></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Backup Frequency</div><div className="setting-desc">How often to backup client data and documents</div></div><select style={{ fontSize: 12 }}><option>Daily</option><option>Weekly</option><option>Monthly</option></select></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Data Retention</div><div className="setting-desc">How long to retain processed documents and AI logs</div></div><select style={{ fontSize: 12 }}><option>7 years</option><option>5 years</option><option>10 years</option></select></div>
                    </div>
                </div>
            )}

            {/* Tax Years Tab */}
            {activeTab === 'taxyears' && (
                <div>
                    <div className="settings-section"><h3>Tax Years</h3>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Active Tax Years</div><div className="setting-desc">Tax years currently available for filing and processing</div></div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>2025, 2024, 2023</div></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Default Tax Year</div><div className="setting-desc">Default tax year for new client onboarding</div></div><select style={{ fontSize: 12 }}><option>2025</option><option>2024</option><option>2023</option></select></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Archive Old Years</div><div className="setting-desc">Automatically archive tax years older than 3 years</div></div><Toggle defaultChecked={true} /></div>
                    </div>
                </div>
            )}

            {/* Notifications Tab */}
            {activeTab === 'notifications' && (
                <div>
                    <div className="settings-section"><h3>Notifications</h3>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Exception Alerts</div><div className="setting-desc">Notify when AI flags exceptions requiring CPA action</div></div><select style={{ fontSize: 12 }}><option>Email + In-App</option><option>Email Only</option><option>In-App Only</option><option>Off</option></select></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Filing Deadline Reminders</div><div className="setting-desc">Lead time for deadline notifications</div></div><select style={{ fontSize: 12 }}><option>7, 3, 1 days before</option><option>14, 7, 3 days before</option><option>Custom</option></select></div>
                        {[['Client Document Uploads', 'Notify when clients upload documents via portal', true], ['E-File Confirmations', 'Notify when IRS accepts or rejects filings', true], ['Weekly Digest Email', 'Summary of filing activity, exceptions, and upcoming deadlines', true]].map(([l, d, c]) => (
                            <div key={l} className="setting-row"><div className="setting-info"><div className="setting-label">{l}</div><div className="setting-desc">{d}</div></div><Toggle defaultChecked={c} /></div>
                        ))}
                    </div>
                </div>
            )}

            {/* Security & Compliance Tab */}
            {activeTab === 'security' && (
                <div>
                    <div className="settings-section"><h3>Security & Compliance</h3>
                        {[['Two-Factor Authentication', 'Require 2FA for all team members', true]].map(([l, d, c]) => (
                            <div key={l} className="setting-row"><div className="setting-info"><div className="setting-label">{l}</div><div className="setting-desc">{d}</div></div><Toggle defaultChecked={c} /></div>
                        ))}
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Session Timeout</div><div className="setting-desc">Auto-logout after period of inactivity</div></div><select style={{ fontSize: 12 }}><option>30 minutes</option><option>1 hour</option><option>2 hours</option><option>4 hours</option></select></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Audit Trail Retention</div><div className="setting-desc">How long to retain AI decision and action logs</div></div><select style={{ fontSize: 12 }}><option>7 years</option><option>5 years</option><option>10 years</option><option>Indefinite</option></select></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Data Encryption at Rest</div><div className="setting-desc">AES-256 encryption for all stored documents and data</div></div><span className="status-pill approved">Enabled</span></div>
                        <div className="setting-row"><div className="setting-info"><div className="setting-label">Client Portal Password Policy</div><div className="setting-desc">Minimum requirements for client portal access</div></div><select style={{ fontSize: 12 }}><option>Strong (12+ chars, mixed)</option><option>Standard (8+ chars)</option><option>Custom</option></select></div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// NOTIFICATION PANEL
// ═══════════════════════════════════════════════════════════════════════════
function NotifPanel({ open, onClose }) {
    const [tab, setTab] = useState('alerts');
    if (!open) return null;
    return (
        <>
            <div className="notif-overlay open" onClick={onClose} />
            <div className="notif-panel open">
                <div className="notif-header">
                    <h3>Notifications</h3>
                    <button className="btn-ghost" style={{ fontSize: 11 }}>Mark all read</button>
                </div>
                <div className="notif-tabs" id="notif-tabs">
                    {[['alerts', 'Alerts', 3], ['notifications', 'Notifications', 5], ['promotions', 'Promotions', null]].map(([id, label, count]) => (
                        <div key={id} className={`notif-tab${tab === id ? ' active' : ''}`} onClick={() => setTab(id)}>{label}{count && <span className="tab-badge">{count}</span>}</div>
                    ))}
                </div>
                <div className="notif-body">
                    {tab === 'alerts' && (
                        <div className="notif-list active">
                            {[['High-severity exception: Patel LLC Schedule C income discrepancy — $47,500 variance. Requires immediate CPA review.', '5 min ago', true], ['Deadline alert: Brooks Dental PLLC (1120-S) due Mar 15 — still in Document Collection. 5 days remaining.', '12 min ago', true], ['E-file rejected: IRS returned error on test submission for Summit Partners LP — invalid EIN format. Re-verify and resubmit.', '28 min ago', true], ['AI confidence drop: Greenfield Ventures K-1 processing dropped below 75% threshold. Flagged for manual review.', '1 hour ago', false]].map(([text, time, unread], i) => (
                                <div key={i} className={`notif-item${unread ? ' unread' : ''}`}>
                                    <div className="notif-item-content"><div className="notif-item-text" dangerouslySetInnerHTML={{ __html: text }} /><div className="notif-item-time">{time}</div></div>
                                </div>
                            ))}
                        </div>
                    )}
                    {tab === 'notifications' && (
                        <div className="notif-list active">
                            {[['Client upload: Sarah Mitchell uploaded 2 documents via portal — W-2 and bank statements.', '2 min ago', true], ['Filing complete: Martinez, David & Ana — Form 1040 e-filed and accepted. Confirmation #2025-EF-88421.', '12 min ago', true], ['Client approval: Nakamura, Kenji signed Form 8879 — return queued for e-file.', '25 min ago', true], ['AI processing: Park, James — 1040 processing complete. 96% confidence, ready for CPA review.', '32 min ago', false], ['Team update: Jessica Wu completed review of Williams, James T. return. Moved to Client Approval.', '1 hour ago', false]].map(([text, time, unread], i) => (
                                <div key={i} className={`notif-item${unread ? ' unread' : ''}`}>
                                    <div className="notif-item-content"><div className="notif-item-text">{text}</div><div className="notif-item-time">{time}</div></div>
                                </div>
                            ))}
                        </div>
                    )}
                    {tab === 'promotions' && (
                        <div className="notif-list active">
                            {[['✦ New Feature', 'Multi-Year Comparison Panel', 'Compare client returns side-by-side across tax years. Spot trends, anomalies, and planning opportunities instantly.'], ['🚀 Update', 'Batch Actions Now Available', 'Select multiple clients and apply bulk actions: assign CPA, approve filings, send portal links, or export reports in one click.'], ['📊 Webinar', 'AI-Powered Tax Season: Tips for CPAs', 'Join our live webinar on Mar 20 at 2 PM ET. Learn best practices for configuring AI confidence thresholds and exception workflows.']].map(([tag, title, desc], i) => (
                                <div key={i} className="notif-promo">
                                    <div className="notif-promo-tag">{tag}</div>
                                    <div className="notif-promo-title">{title}</div>
                                    <div className="notif-promo-desc">{desc}</div>
                                    <button className="btn btn-secondary" style={{ fontSize: 11 }}>Learn More</button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
                <div className="notif-footer"><a href="#">View All Notifications</a></div>
            </div>
        </>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// PROFILE DROPDOWN
// ═══════════════════════════════════════════════════════════════════════════
function ProfileDropdown({ open, onClose, onNavigate }) {
    const [pwOpen, setPwOpen] = useState(false);
    if (!open && !pwOpen) return null;
    return (
        <>
            {open && <div className="profile-overlay open" onClick={onClose} />}
            {open && (
                <div className="profile-dropdown open">
                    <div className="profile-card">
                        <div className="profile-card-avatar">MC</div>
                        <div className="profile-card-info">
                            <div className="profile-card-name">Michael Chen</div>
                            <div className="profile-card-email">mchen@chenassociates.com</div>
                            <div className="profile-card-role">Senior CPA · Admin</div>
                        </div>
                    </div>
                    <div className="profile-menu">
                        <div className="profile-menu-item" onClick={() => { onClose(); onNavigate('settings'); }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                            Preferences
                        </div>
                        <div className="profile-menu-item" onClick={() => { setPwOpen(true); onClose(); }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" /></svg>
                            Change Password
                        </div>
                        <div className="profile-menu-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3" /></svg>
                            Account Settings
                        </div>
                        <div className="profile-menu-divider" />
                        <div className="profile-menu-item danger">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16,17 21,12 16,7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
                            Log Out
                        </div>
                    </div>
                </div>
            )}
            {pwOpen && (
                <>
                    <div className="profile-overlay open" style={{ zIndex: 1100 }} onClick={() => setPwOpen(false)} />
                    <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: 420, background: 'var(--surface-1)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', boxShadow: '0 24px 64px rgba(0,0,0,.15)', zIndex: 1101, padding: 28 }}>
                        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Change Password</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>Update your account password. You'll be logged out of other devices.</div>
                        {['Current Password', 'New Password', 'Confirm New Password'].map(l => (
                            <div key={l} className="form-group" style={{ marginBottom: 14 }}><label className="form-label">{l}</label><input type="password" className="form-input" placeholder={`Enter ${l.toLowerCase()}`} /></div>
                        ))}
                        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                            <button className="btn btn-secondary" onClick={() => setPwOpen(false)}>Cancel</button>
                            <button className="btn btn-primary">Update Password</button>
                        </div>
                    </div>
                </>
            )}
        </>
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════
export default function App() {
    const isDev = import.meta.env.DEV;
    const apiUrl = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.replace(/\/$/, '') : '';

    // ── Layout state ──────────────────────────────────────────────────────
    const [currentPage, setCurrentPage] = useState('dashboard');
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [notifOpen, setNotifOpen] = useState(false);
    const [profileOpen, setProfileOpen] = useState(false);

    // ── Connection ────────────────────────────────────────────────────────
    const [connStatus, setConnStatus] = useState('connecting');

    // ── Polled data ───────────────────────────────────────────────────────
    const [stats, setStats] = useState({ active_sessions: 0, total_sessions: 0, events_logged: 0, agent_actions_logged: 0 });
    const [logs, setLogs] = useState([]);
    const [events, setEvents] = useState([]);

    // ── Extraction pipeline ───────────────────────────────────────────────
    const [files, setFiles] = useState([]);
    const [results, setResults] = useState({});
    const [activeIngestionFile, setActiveIngestionFile] = useState(null);
    const [extracting, setExtracting] = useState(false);
    const [loadingMsg, setLoadingMsg] = useState('');
    const [showSensitive, setShowSensitive] = useState(false);
    const [showSidePdf, setShowSidePdf] = useState(false);
    const [pdfUrl, setPdfUrl] = useState(null);
    const [humanEdits, setHumanEdits] = useState({});
    const [savingReview, setSavingReview] = useState(false);
    const [globalError, setGlobalError] = useState(null);
    const [clientMatchModal, setClientMatchModal] = useState(null);
    // Incremented after FDR derive completes — PageClients uses this to reload the checklist
    const [checklistReloadTrigger, setChecklistReloadTrigger] = useState(0);

    // Session ID stored in sessionStorage
    const getSessionId = useCallback(() => sessionStorage.getItem('taxio_session_id'), []);
    const setSessionId = useCallback(sid => sessionStorage.setItem('taxio_session_id', sid), []);

    // Most recent single extraction result (for Exceptions page)
    const lastExtraction = activeIngestionFile ? results[activeIngestionFile]
        : Object.keys(results).length > 0 ? results[Object.keys(results)[Object.keys(results).length - 1]]
            : null;

    // Exception count for nav badge (deduped — matches Exceptions queue)
    const exceptionCount = useMemo(() => countDedupedExceptions(lastExtraction), [lastExtraction]);

    // ── Connection check with retry ───────────────────────────────────────
    useEffect(() => {
        let timer;
        const check = async () => {
            try {
                const r = await fetch(`${apiUrl}/health`);
                if (r.ok) {
                    setConnStatus('connected');
                } else {
                    timer = setTimeout(check, 3000);
                }
            }
            catch {
                setConnStatus('error');
                timer = setTimeout(check, 5000); // Retry even on error
            }
        };
        check();
        return () => clearTimeout(timer);
    }, [apiUrl]);

    // ── Polling ───────────────────────────────────────────────────────────
    useEffect(() => {
        if (connStatus !== 'connected') return;
        const pollStats = async () => {
            try {
                const r = await fetch(`${apiUrl}/api/stats`, { credentials: 'include', headers: getSessionId() ? { 'X-Session-ID': getSessionId() } : {} });
                if (r.ok) { const d = await r.json(); if (d.ok) setStats(d.data || {}); }
            } catch { }
        };
        const pollLogs = async () => {
            try {
                const sid = getSessionId();
                const q = sid ? `?session_id=${encodeURIComponent(sid)}` : '';
                const r = await fetch(`${apiUrl}/api/logs${q}`, { credentials: 'include', headers: sid ? { 'X-Session-ID': sid } : {} });
                if (r.ok) { const d = await r.json(); if (d.ok && d.data?.logs) setLogs(d.data.logs); }
            } catch { }
        };
        const pollEvents = async () => {
            try {
                const r = await fetch(`${apiUrl}/api/events?limit=20`, { credentials: 'include' });
                if (r.ok) { const d = await r.json(); if (d.ok && d.data?.events) setEvents(d.data.events); }
            } catch { }
        };
        pollStats(); pollLogs(); pollEvents();
        const si = setInterval(() => { pollStats(); pollLogs(); pollEvents(); }, 5000);
        return () => clearInterval(si);
    }, [connStatus]);

    // ── File processing ───────────────────────────────────────────────────
    const processFiles = useCallback((newFiles) => {
        const allowed = ['application/pdf', 'image/png', 'image/jpeg', 'image/webp'];
        const valid = Array.from(newFiles).filter(f => allowed.includes(f.type));
        if (!valid.length) return;
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const objs = valid.map(f => ({ file: f, status: 'queued', form_type: null, uploadedAt: timeStr }));
        setFiles(prev => [...prev, ...objs]);
        if (!activeIngestionFile) setActiveIngestionFile(valid[0].name);
    }, [activeIngestionFile]);

    const removeFile = useCallback((idx) => {
        setFiles(prev => { const n = [...prev]; n.splice(idx, 1); return n; });
    }, []);

    // ── Extraction pipeline (Group A routes: /detect, /extract, /validate) ─
    const performExtraction = useCallback(async () => {
        const queued = files.filter(f => f.status === 'queued');
        if (!queued.length || connStatus !== 'connected') return;
        setExtracting(true);
        setGlobalError(null);
        const cur = [...files];

        try {
            for (let i = 0; i < cur.length; i++) {
                const item = cur[i];
                if (item.status !== 'queued') continue;

                // Mark processing
                cur[i].status = 'processing';
                setFiles([...cur]);
                setLoadingMsg(`Extracting ${item.file.name}…`);

                try {
                    // Step 1: Detect form type
                    const fd1 = new FormData();
                    fd1.append('file', item.file);
                    const r1 = await fetch(`${apiUrl}/detect`, { method: 'POST', body: fd1 });
                    if (!r1.ok) {
                        const e = await r1.json();
                        throw { status: r1.status, error: e.reason || e.error || 'Detection failed', isGate: r1.status === 422 };
                    }
                    const d1 = await r1.json();
                    const formType = d1.detected?.form_type;
                    cur[i].form_type = formType;

                    // Step 2: Extract fields
                    const fd2 = new FormData();
                    fd2.append('file', item.file);
                    fd2.append('form_type', formType);
                    fd2.append('fields_only', 'true');
                    const r2 = await fetch(`${apiUrl}/extract`, { method: 'POST', body: fd2 });
                    if (!r2.ok) throw { status: r2.status, ...(await r2.json()) };
                    const d2 = await r2.json();

                    // Mark completed immediately so UI updates
                    cur[i].status = 'completed';
                    setFiles([...cur]);
                    setActiveIngestionFile(item.file.name);

                    // Step 3: Validate immediately for this file — exceptions appear right away
                    setLoadingMsg(`Validating ${item.file.name}…`);
                    let finalData = { ...d2, detected: true, extraction_complete: true };
                    try {
                        const r3 = await fetch(`${apiUrl}/validate`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ form_type: formType, pdf_type: d2.pdf_type, data: d2.data, filename: item.file.name }),
                        });
                        if (r3.ok) {
                            const d3 = await r3.json();
                            finalData = { ...finalData, ...d3, validation_complete: true };
                        }
                    } catch { /* validation failed, still show extraction data */ }

                    // Update results with both extraction + validation in one setState
                    setResults(prev => ({ ...prev, [item.file.name]: finalData }));

                    // Auto-save snapshot to local_extraction/ — no button needed
                    fetch(`${apiUrl}/save-snapshot`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            document_id:         finalData.document_id || undefined,
                            form_type:           formType,
                            filename:            item.file.name,
                            pdf_type:            finalData.pdf_type || d2.pdf_type,
                            data:                finalData.data || {},
                            exceptions:          finalData.exceptions || [],
                            document_confidence: finalData.document_confidence ?? 1.0,
                            field_confidence:    finalData.field_confidence || {},
                        }),
                    }).catch(() => {/* non-blocking */});

                    // Client auto-match: always show modal so user can assign or add a client
                    const identity = extractClientIdentity(finalData.data) || { name: null, tin: null };
                    let autoMatch = null;
                    try {
                        const clientsRes = await fetch(`${apiUrl}/clients?limit=500`);
                        if (clientsRes.ok) {
                            const allClients = await clientsRes.json();
                            if (identity.name || identity.tin) {
                                autoMatch = allClients.find(c => {
                                    const fullName = c.entity_type === 'INDIVIDUAL'
                                        ? `${c.first_name || ''} ${c.last_name || ''}`.trim()
                                        : c.business_name || c.trust_name || '';
                                    return (identity.name && fullName.toLowerCase() === identity.name.toLowerCase())
                                        || (identity.tin && c.tax_id === identity.tin);
                                }) || null;
                            }
                        }
                    } catch { /* client DB unavailable — modal still shows with no match */ }
                    // Always open the modal regardless of whether client fetch succeeded
                    setClientMatchModal({ fileName: item.file.name, formType, identity, match: autoMatch, extractedData: finalData.data || {} });

                } catch (err) {
                    cur[i].status = 'error';
                    cur[i].error = err.error || err.message || 'Extraction failed';
                    cur[i].isGate = err.isGate;
                    setFiles([...cur]);
                }
            }
        } catch (e) {
            setGlobalError({ title: 'Processing Error', message: 'An unexpected error occurred.' });
        } finally {
            setExtracting(false);
            setLoadingMsg('');
        }
    }, [files, connStatus, apiUrl]);

    // Auto-extract when files are queued
    useEffect(() => {
        if (files.some(f => f.status === 'queued') && !extracting && connStatus === 'connected') performExtraction();
    }, [files, extracting, connStatus]);

    // Field editing
    const handleFieldEdit = useCallback((fileName, path, newValue) => {
        setResults(prev => {
            const nr = JSON.parse(JSON.stringify(prev));
            let cur = nr[fileName]?.data || nr[fileName]?.extracted_fields;
            if (!cur) return prev;
            const keys = path.split('.');
            const last = keys.pop();
            for (const k of keys) { if (cur[k] !== undefined) cur = cur[k]; else return prev; }
            if (typeof cur[last] === 'number') { const v = Number(newValue); cur[last] = isNaN(v) ? newValue : v; }
            else if (typeof cur[last] === 'boolean') cur[last] = newValue.toLowerCase() === 'true';
            else cur[last] = newValue;
            return nr;
        });
    }, []);

    // Export
    const handleExport = useCallback(async (format = 'json') => {
        try {
            const r = await fetch(`${apiUrl}/ledger/export?format=${format}`, { method: 'GET' });
            if (r.ok) { const b = await r.blob(); const cd = r.headers.get('Content-Disposition'); const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(b), download: (cd && cd.split('filename=')[1]) || `export.${format}` }); a.click(); URL.revokeObjectURL(a.href); }
        } catch { }
    }, [apiUrl]);

    // Document drop for Documents page
    const handleDocDrop = useCallback((fileList) => {
        processFiles(fileList);
        setCurrentPage('ingestion');
    }, [processFiles]);

    const docFileRef = useRef(null);

    // ── Navigate & close panels ───────────────────────────────────────────
    const navigate = (page) => {
        setCurrentPage(page);
        setNotifOpen(false);
        setProfileOpen(false);
    };

    // ── No-content-class pages (custom layouts) ───────────────────────────
    const noContentPad = ['clients'];
    const usePad = !noContentPad.includes(currentPage);

    return (
        <div className="app">
            {/* ── SIDEBAR ──────────────────────────────────────────────────── */}
            <aside className={`sidebar${sidebarCollapsed ? ' collapsed' : ''}`} id="sidebar">
                <div className="sidebar-logo">
                    <div className="collapse-btn" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} title="Toggle sidebar">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></svg>
                    </div>
                    {!sidebarCollapsed && (
                        <img
                            src="/static/logo.png"
                            alt="Taxscio"
                            style={{ height: 28, maxWidth: 160, objectFit: 'contain', objectPosition: 'left center' }}
                        />
                    )}
                </div>
                <nav className="sidebar-nav">
                    <div className="sidebar-section">Main</div>
                    {[['dashboard', 'Dashboard'], ['clients', 'Clients'], ['pipeline', 'Filing Pipeline'], ['ingestion', 'Ingestion Hub'], ['exceptions', 'Exceptions'], ['documents', 'Documents'], ['reports', 'Reports']].map(([id, label]) => (
                        <div key={id} className={`nav-item${currentPage === id ? ' active' : ''}`} data-page={id} onClick={() => navigate(id)}>
                            {NAV_ICONS[id]}
                            <span className="nav-item-label">{label}</span>
                            {id === 'exceptions' && exceptionCount > 0 && <span className="nav-badge" id="exception-nav-badge">{exceptionCount}</span>}
                        </div>
                    ))}
                    {/* AI Engine — hidden from sidebar, pages still accessible programmatically */}
                    <div className="sidebar-section">Manage</div>
                    {[['identity', 'Identity'], ['integrations', 'Integrations'], ['organization', 'Organization'], ['settings', 'Settings']].map(([id, label]) => (
                        <div key={id} className={`nav-item${currentPage === id ? ' active' : ''}`} data-page={id} onClick={() => navigate(id)}>
                            {NAV_ICONS[id]}<span className="nav-item-label">{label}</span>
                        </div>
                    ))}
                </nav>
            </aside>

            {/* ── MAIN AREA ─────────────────────────────────────────────────── */}
            <div className="main-area">
                {/* Topbar */}
                <header className="topbar">
                    <div className="topbar-title" id="topbar-title">{PAGE_TITLES[currentPage] || currentPage}</div>
                    <div className="topbar-sep" />
                    <div className="topbar-breadcrumb">Tax Year 2025 · Filing Season</div>
                    <div className="topbar-spacer" />
                    <div className="topbar-search">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
                        <input type="text" placeholder="Search clients, documents, forms…" />
                        <span className="topbar-shortcut">⌘K</span>
                    </div>
                    {/* Ingestion Hub Status Indicator
                        - Online: Hub active, no jobs running (Green)
                        - Scheduled: Jobs registered for future execution (Teal)
                        - Queued: Jobs waiting in processing queue (Amber)
                        - Processing: Hub actively processing jobs (Blue)
                        - Offline: Hub unavailable (Red)
                    */}
                    {(() => {
                        // Determine hub status based on connection and file processing state
                        let status, statusText, bgColor, textColor;
                        
                        if (connStatus !== 'connected') {
                            // Offline - not connected
                            status = 'offline';
                            statusText = connStatus === 'connecting' ? 'Connecting' : 'Offline';
                            bgColor = 'rgba(239, 68, 68, 0.1)';
                            textColor = '#ef4444';
                        } else {
                            const processingCount = files.filter(f => f.status === 'processing').length;
                            const queuedCount = files.filter(f => f.status === 'queued').length;
                            const scheduledCount = files.filter(f => f.status === 'scheduled').length;
                            
                            if (processingCount > 0) {
                                // Processing - hub actively working
                                status = 'processing';
                                statusText = 'Processing';
                                bgColor = 'rgba(59, 130, 246, 0.1)';
                                textColor = '#3b82f6';
                            } else if (queuedCount > 0) {
                                // Queued - jobs waiting
                                status = 'queued';
                                statusText = 'Queued';
                                bgColor = 'rgba(217, 119, 6, 0.1)';
                                textColor = '#d97706';
                            } else if (scheduledCount > 0) {
                                // Scheduled - jobs registered for future
                                status = 'scheduled';
                                statusText = 'Scheduled';
                                bgColor = 'rgba(0, 184, 148, 0.1)';
                                textColor = '#00b894';
                            } else {
                                // Online - ready, no jobs
                                status = 'online';
                                statusText = 'Online';
                                bgColor = 'rgba(34, 197, 94, 0.1)';
                                textColor = '#22c55e';
                            }
                        }
                        
                        return (
                            <div id="global-stage-pill" style={{
                                padding: '6px 12px',
                                borderRadius: 'var(--radius)',
                                background: bgColor,
                                color: textColor,
                                fontSize: 12,
                                fontWeight: 600,
                                border: `1px solid ${textColor}33`,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                            }}>
                                <span style={{ width: 6, height: 6, borderRadius: '50%', background: textColor }}></span>
                                {statusText}
                            </div>
                        );
                    })()}
                    <button className="topbar-icon" onClick={() => { setNotifOpen(!notifOpen); setProfileOpen(false); }} id="notif-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" /></svg>
                        <span className="notif-dot" />
                    </button>
                    <div className="profile-avatar-btn" onClick={() => { setProfileOpen(!profileOpen); setNotifOpen(false); }}>MC</div>
                </header>

                {/* Panels */}
                <NotifPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
                <ProfileDropdown open={profileOpen} onClose={() => setProfileOpen(false)} onNavigate={navigate} />

                {/* Client match modal — shown after each extraction */}
                {clientMatchModal && (
                    <ClientMatchModal
                        modal={clientMatchModal}
                        apiUrl={apiUrl}
                        onDismiss={() => setClientMatchModal(null)}
                        onAssociated={async (clientId) => {
                            const fileResult = results[clientMatchModal.fileName] || {};

                            // Resolve client name: use extracted identity, or fetch from DB
                            let resolvedClientName = clientMatchModal.identity?.name || '';
                            if (!resolvedClientName) {
                                try {
                                    const cr = await fetch(`${apiUrl}/clients/${clientId}`);
                                    if (cr.ok) {
                                        const cd = await cr.json();
                                        resolvedClientName = cd.entity_type === 'INDIVIDUAL'
                                            ? `${cd.first_name || ''} ${cd.last_name || ''}`.trim()
                                            : cd.business_name || cd.trust_name || '';
                                    }
                                } catch { /* non-blocking */ }
                            }

                            setResults(prev => ({
                                ...prev,
                                [clientMatchModal.fileName]: {
                                    ...prev[clientMatchModal.fileName],
                                    matchedClientId: clientId,
                                    matchedClientName: resolvedClientName,
                                },
                            }));
                            setClientMatchModal(null);

                            // Submit document to ledger so it persists across page refreshes
                            try {
                                const extractedFields = fileResult.data || fileResult.extracted_fields || {};
                                const taxYear = extractedFields?.tax_year
                                    ? (typeof extractedFields.tax_year === 'number'
                                        ? extractedFields.tax_year
                                        : parseInt(extractedFields.tax_year) || new Date().getFullYear())
                                    : new Date().getFullYear();
                                await fetch(`${apiUrl}/ledger/submit`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        client_name:        resolvedClientName || clientMatchModal.fileName,
                                        client_id:          clientId,
                                        document_type:      clientMatchModal.formType || 'Unknown',
                                        provider:           'AI Extraction',
                                        description:        clientMatchModal.fileName,
                                        source:             'Ingestion Hub',
                                        tax_year:           taxYear,
                                        stage:              'Document Submission',
                                        status:             (fileResult.exceptions?.length > 0) ? 'EXCEPTION' : 'VALIDATED',
                                        confidence_score:   fileResult.document_confidence ?? null,
                                        extraction_json_path: fileResult.extraction_json_path || null,
                                    }),
                                });
                            } catch { /* non-blocking — local display already updated */ }

                            // Backfill client_id on any pre-existing ledger rows for this client name
                            if (resolvedClientName) {
                                try {
                                    await fetch(`${apiUrl}/ledger/associate-client`, {
                                        method: 'PATCH',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({
                                            client_id:     clientId,
                                            client_name:   resolvedClientName,
                                            document_type: clientMatchModal.formType || undefined,
                                        }),
                                    });
                                } catch { /* non-blocking */ }
                            }

                            // If this is a 1040, trigger FDR to derive the document checklist
                            if ((clientMatchModal.formType || '').toUpperCase() === '1040') {
                                try {
                                    const extractedFields = fileResult.data || fileResult.extracted_fields || fileResult.raw_normalized_json || {};
                                    const fieldConfidenceMap = fileResult.field_confidence || {};
                                    const docType = (fileResult.pdf_type || 'digital') === 'digital' ? 'digital' : 'scanned';
                                    const taxYear = extractedFields?.tax_year || new Date().getFullYear();
                                    await fetch(`${apiUrl}/clients/${clientId}/document-checklist/derive-from-1040`, {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({
                                            tax_year: typeof taxYear === 'number' ? taxYear : parseInt(taxYear) || new Date().getFullYear(),
                                            extracted_fields: extractedFields,
                                            field_confidence_map: fieldConfidenceMap,
                                            document_type: docType,
                                        }),
                                    });
                                    setChecklistReloadTrigger(t => t + 1);
                                } catch { /* FDR is non-blocking; association still succeeded */ }
                            }
                        }}
                    />
                )}

                {/* Content */}
                <main className={usePad ? 'content' : ''} style={!usePad ? { flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' } : {}}>
                    {globalError && (
                        <div style={{ marginBottom: 16, padding: '12px 16px', background: 'var(--red-bg)', border: '1px solid var(--red-border)', borderRadius: 'var(--radius)', display: 'flex', gap: 10, alignItems: 'center' }}>
                            <span style={{ color: 'var(--red)', fontWeight: 600, fontSize: 13 }}>{globalError.title}: {globalError.message}</span>
                            <button style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--red)', fontSize: 16 }} onClick={() => setGlobalError(null)}>✕</button>
                        </div>
                    )}

                    {currentPage === 'dashboard' && <PageDashboard stats={stats} events={events} files={files} results={results} />}
                    {currentPage === 'clients' && <PageClients lastExtraction={lastExtraction} apiUrl={apiUrl} onUpload={() => navigate('ingestion')} files={files} results={results} setResults={setResults} checklistReloadTrigger={checklistReloadTrigger} />}
                    {currentPage === 'pipeline' && <PagePipeline files={files} results={results} apiUrl={apiUrl} />}
                    {currentPage === 'exceptions' && <PageExceptions files={files} results={results} apiUrl={apiUrl} setResults={setResults} />}
                    {currentPage === 'documents' && <PageDocuments files={files} results={results} events={events} onDrop={handleDocDrop} fileInputRef={docFileRef} />}
                    {currentPage === 'agent' && <PageAgent stats={stats} logs={logs} files={files} results={results} />}
                    {currentPage === 'ingestion' && (
                        <PageIngestion
                            apiUrl={apiUrl}
                            files={files} results={results} setResults={setResults}
                            activeIngestionFile={activeIngestionFile} setActiveIngestionFile={setActiveIngestionFile}
                            extracting={extracting} loadingMsg={loadingMsg}
                            performExtraction={performExtraction} processFiles={processFiles} removeFile={removeFile}
                            showSensitive={showSensitive} setShowSensitive={setShowSensitive}
                            showSidePdf={showSidePdf} setShowSidePdf={setShowSidePdf}
                            pdfUrl={pdfUrl} humanEdits={humanEdits} setHumanEdits={setHumanEdits}
                            savingReview={savingReview} setSavingReview={setSavingReview}
                            handleFieldEdit={handleFieldEdit}
                            sessionId={getSessionId()} events={events}
                        />
                    )}
                    {currentPage === 'airules' && <PageAIRules />}
                    {currentPage === 'reports' && <PageReports apiUrl={apiUrl} sessionId={getSessionId()} results={results} />}
                    {currentPage === 'identity' && <PageIdentity />}
                    {currentPage === 'integrations' && <PageIntegrations />}
                    {currentPage === 'organization' && <PageOrganization />}
                    {currentPage === 'settings' && <PageSettings onNavigate={navigate} />}
                </main>
            </div>

            {/* Hidden file input for Documents page */}
            <input ref={docFileRef} type="file" accept="application/pdf,image/png,image/jpeg,image/webp" multiple style={{ display: 'none' }} onChange={e => { if (e.target.files[0]) { handleDocDrop(e.target.files); e.target.value = ''; } }} />
        </div>
    );
}
