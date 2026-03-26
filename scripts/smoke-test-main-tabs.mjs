/**
 * Smoke test for main nav tabs (Clients, Filing Pipeline, Ingestion Hub, Exceptions, Documents)
 * against a running Taxscio API. Uses sample JSON for /validate (Exceptions flow).
 *
 * Usage:
 *   node scripts/smoke-test-main-tabs.mjs
 *   set API_URL=http://127.0.0.1:8000 && node scripts/smoke-test-main-tabs.mjs
 *
 * Prerequisites: uvicorn backend.main:app (NUMIND_API_KEY, DATABASE_URL optional for some routes)
 */

import { readFileSync, existsSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

const API = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

const checks = [];

function ok(name, pass, detail = '') {
    checks.push({ name, pass, detail });
    const icon = pass ? '✓' : '✗';
    console.log(`${icon} ${name}${detail ? ` — ${detail}` : ''}`);
}

async function get(path) {
    const r = await fetch(`${API}${path}`, { headers: { Accept: 'application/json' } });
    const text = await r.text();
    let json = null;
    try {
        json = JSON.parse(text);
    } catch { /* not json */ }
    return { ok: r.ok, status: r.status, json, text: text.slice(0, 500) };
}

async function postJson(path, body) {
    const r = await fetch(`${API}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(body),
    });
    const text = await r.text();
    let json = null;
    try {
        json = JSON.parse(text);
    } catch { /* */ }
    return { ok: r.ok, status: r.status, json, text: text.slice(0, 800) };
}

console.log(`\nTaxscio main-tabs smoke test → ${API}\n`);

// ── Health (all tabs need API) ─────────────────────────────────────────────
{
    const r = await get('/health');
    ok('API health', r.ok, r.ok ? `status ${r.status}` : r.text);
}

// ── Clients tab → GET /clients ───────────────────────────────────────────────
{
    const r = await get('/clients?limit=5');
    const list = Array.isArray(r.json) ? r.json : r.json?.data;
    const count = Array.isArray(list) ? list.length : 0;
    ok(
        'Clients tab (GET /clients)',
        r.ok && Array.isArray(r.json),
        r.ok ? `${count} client(s) in response` : `HTTP ${r.status}`,
    );
}

// ── Filing Pipeline tab → GET /ledger/ledger ─────────────────────────────────
{
    const r = await get('/ledger/ledger');
    const isArray = Array.isArray(r.json);
    ok(
        'Filing Pipeline (GET /ledger/ledger)',
        r.ok && isArray,
        r.ok ? `${isArray ? r.json.length : 0} ledger row(s)` : `HTTP ${r.status} ${r.text?.slice(0, 120)}`,
    );
}

// ── Documents page (nav) → GET /api/events ─────────────────────────────────
{
    const r = await get('/api/events?limit=5');
    const data = r.json?.data ?? r.json;
    const events = data?.events ?? (Array.isArray(data) ? data : null);
    ok(
        'Documents hub events (GET /api/events)',
        r.ok,
        r.ok ? `${events?.length ?? 0} event(s)` : `HTTP ${r.status}`,
    );
}

// ── Exceptions tab → POST /validate with sample W-2 data ─────────────────────
{
    const samplePath = join(ROOT, 'backend', 'sample_data', 'sample_w2_extraction.json');
    if (!existsSync(samplePath)) {
        ok('Exceptions (POST /validate)', false, `missing ${samplePath}`);
    } else {
        const raw = JSON.parse(readFileSync(samplePath, 'utf8'));
        const body = {
            form_type: 'W-2',
            pdf_type: 'digital',
            data: raw,
            filename: 'smoke-test-w2-sample.json',
        };
        const r = await postJson('/validate', body);
        const exc = r.json?.exceptions;
        const n = Array.isArray(exc) ? exc.length : 0;
        ok(
            'Exceptions / validation (POST /validate, sample W-2)',
            r.ok && Array.isArray(exc),
            r.ok ? `${n} exception(s) returned` : `HTTP ${r.status} ${r.text?.slice(0, 200)}`,
        );
    }
}

// ── Ingestion Hub: detect requires multipart file — skip with note ───────────
ok(
    'Ingestion Hub (POST /detect)',
    true,
    'skipped (requires PDF/image upload); test manually in UI',
);

// ── Summary ─────────────────────────────────────────────────────────────────
const failed = checks.filter((c) => !c.pass);
console.log('\n---');
if (failed.length === 0) {
    console.log('All automated checks passed.');
} else {
    console.log(`${failed.length} check(s) failed.`);
}
process.exitCode = failed.length === 0 ? 0 : 1;
