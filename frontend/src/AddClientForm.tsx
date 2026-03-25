/**
 * AddClientForm.jsx
 * Full-featured Add Client form with:
 *  - Dropdowns sourced from /enums/all (enum_master)
 *  - Conditional fields based on entity_type
 *  - Tag input (comma-separated → JSON array)
 *  - Inline validation
 *  - POST to /clients
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';

// ─── Country flag emoji helper ───────────────────────────────────────────────
function countryFlag(code) {
    if (!code || code.length !== 2) return '';
    return code.toUpperCase().replace(/./g, c =>
        String.fromCodePoint(0x1F1E0 - 65 + c.charCodeAt(0))
    );
}

// ─── Generic form field components ───────────────────────────────────────────
function FormSection({ title, icon, children }) {
    return (
        <div style={{
            background: 'var(--surface-1)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            marginBottom: 16,
        }}>
            <div style={{
                padding: '12px 20px',
                background: 'var(--surface-2)',
                borderBottom: '1px solid var(--border)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
            }}>
                <span style={{ fontSize: 14 }}>{icon}</span>
                <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                    {title}
                </span>
            </div>
            <div style={{ padding: '16px 20px', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 20px' }}>
                {children}
            </div>
        </div>
    );
}

function Field({ label, required, error, fullWidth, children }) {
    return (
        <div style={{ gridColumn: fullWidth ? '1 / -1' : undefined }}>
            <label style={{
                display: 'block',
                fontSize: 11,
                fontWeight: 600,
                color: error ? 'var(--red)' : 'var(--text-secondary)',
                marginBottom: 4,
                letterSpacing: '.03em',
                textTransform: 'uppercase',
            }}>
                {label} {required && <span style={{ color: 'var(--red)' }}>*</span>}
            </label>
            {children}
            {error && (
                <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 3, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span>⚠</span> {error}
                </div>
            )}
        </div>
    );
}

const inputStyle = (hasError) => ({
    width: '100%',
    padding: '8px 12px',
    fontSize: 13,
    background: 'var(--surface-2)',
    border: `1px solid ${hasError ? 'var(--red)' : 'var(--border)'}`,
    borderRadius: 'var(--radius)',
    color: 'var(--text-primary)',
    outline: 'none',
    transition: 'border-color .15s, box-shadow .15s',
    boxSizing: 'border-box',
});

function TextInput({ value, onChange, placeholder, error, type = 'text', ...rest }) {
    const [focused, setFocused] = useState(false);
    return (
        <input
            type={type}
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder={placeholder}
            style={{
                ...inputStyle(!!error),
                boxShadow: focused ? `0 0 0 3px ${error ? 'rgba(239,68,68,.15)' : 'rgba(99,102,241,.15)'}` : 'none',
                borderColor: focused ? (error ? 'var(--red)' : '#6366f1') : (error ? 'var(--red)' : 'var(--border)'),
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            {...rest}
        />
    );
}

function SelectInput({ value, onChange, options, placeholder, error }) {
    const [focused, setFocused] = useState(false);
    return (
        <select
            value={value}
            onChange={e => onChange(e.target.value)}
            style={{
                ...inputStyle(!!error),
                cursor: 'pointer',
                boxShadow: focused ? `0 0 0 3px ${error ? 'rgba(239,68,68,.15)' : 'rgba(99,102,241,.15)'}` : 'none',
                borderColor: focused ? (error ? 'var(--red)' : '#6366f1') : (error ? 'var(--red)' : 'var(--border)'),
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
        >
            <option value="">{placeholder || 'Select…'}</option>
            {options.map(opt => (
                <option key={opt.code} value={opt.code}>
                    {opt.label}
                </option>
            ))}
        </select>
    );
}

function TextAreaInput({ value, onChange, placeholder, error, rows = 4 }) {
    const [focused, setFocused] = useState(false);
    return (
        <textarea
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder={placeholder}
            rows={rows}
            style={{
                ...inputStyle(!!error),
                resize: 'vertical',
                lineHeight: 1.6,
                boxShadow: focused ? `0 0 0 3px ${error ? 'rgba(239,68,68,.15)' : 'rgba(99,102,241,.15)'}` : 'none',
                borderColor: focused ? (error ? 'var(--red)' : '#6366f1') : (error ? 'var(--red)' : 'var(--border)'),
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
        />
    );
}

// ─── Tag input ───────────────────────────────────────────────────────────────
function TagInput({ tags, onChange, error }) {
    const [inputVal, setInputVal] = useState('');
    const [focused, setFocused] = useState(false);

    const addTag = useCallback((raw) => {
        const parts = raw.split(',').map(t => t.trim()).filter(Boolean);
        if (!parts.length) return;
        const next = [...new Set([...tags, ...parts])];
        onChange(next);
        setInputVal('');
    }, [tags, onChange]);

    const handleKeyDown = (e) => {
        if (e.key === ',' || e.key === 'Enter') {
            e.preventDefault();
            addTag(inputVal);
        } else if (e.key === 'Backspace' && !inputVal && tags.length) {
            onChange(tags.slice(0, -1));
        }
    };

    return (
        <div style={{
            ...inputStyle(!!error),
            display: 'flex',
            flexWrap: 'wrap',
            gap: 6,
            padding: '6px 10px',
            minHeight: 40,
            alignItems: 'center',
            cursor: 'text',
            boxShadow: focused ? '0 0 0 3px rgba(99,102,241,.15)' : 'none',
            borderColor: focused ? '#6366f1' : (error ? 'var(--red)' : 'var(--border)'),
        }} onClick={(e) => e.currentTarget.querySelector('input')?.focus()}>
            {tags.map(tag => (
                <span key={tag} style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    background: 'rgba(99,102,241,.12)',
                    color: '#6366f1',
                    border: '1px solid rgba(99,102,241,.25)',
                    borderRadius: 20,
                    padding: '2px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: '.03em',
                }}>
                    {tag}
                    <span
                        onClick={() => onChange(tags.filter(t => t !== tag))}
                        style={{ cursor: 'pointer', opacity: .6, marginLeft: 2, fontSize: 13, lineHeight: 1 }}
                    >×</span>
                </span>
            ))}
            <input
                value={inputVal}
                onChange={e => setInputVal(e.target.value)}
                onKeyDown={handleKeyDown}
                onBlur={() => { setFocused(false); if (inputVal) addTag(inputVal); }}
                onFocus={() => setFocused(true)}
                placeholder={tags.length ? '' : 'Type a tag and press comma or Enter…'}
                style={{
                    border: 'none',
                    outline: 'none',
                    background: 'transparent',
                    fontSize: 13,
                    color: 'var(--text-primary)',
                    minWidth: 120,
                    flex: 1,
                }}
            />
        </div>
    );
}

// ─── Validation ───────────────────────────────────────────────────────────────
function validate(form) {
    const errors = {};
    if (!form.entity_type) errors.entity_type = 'Entity type is required';

    const et = form.entity_type?.toUpperCase();
    if (et === 'INDIVIDUAL') {
        if (!form.first_name?.trim()) errors.first_name = 'First name is required';
        if (!form.last_name?.trim())  errors.last_name  = 'Last name is required';
    } else if (et === 'BUSINESS') {
        if (!form.business_name?.trim()) errors.business_name = 'Business name is required';
    } else if (et === 'TRUST') {
        if (!form.trust_name?.trim()) errors.trust_name = 'Trust name is required';
    }

    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
        errors.email = 'Invalid email address';
    }
    if (form.phone && !/^[+\d\s\-().]{6,20}$/.test(form.phone)) {
        errors.phone = 'Invalid phone number';
    }
    return errors;
}

// ─── AddClientForm ─────────────────────────────────────────────────────────────
const EMPTY_FORM = {
    entity_type: '', first_name: '', last_name: '', business_name: '', trust_name: '',
    date_of_birth: '', date_of_incorporation: '',
    email: '', phone: '',
    tax_id: '', country: '', residency_status: '',
    address_line1: '', address_line2: '', city: '', state: '', zip_code: '',
    lifecycle_stage: '', risk_profile: '', source: '',
    notes: '', tags: [],
};

export default function AddClientForm({ apiUrl, onSuccess, onCancel, initialData = {} }) {
    const base = apiUrl || 'http://localhost:8000';
    const [form, setForm] = useState({ ...EMPTY_FORM, ...initialData });
    const [errors, setErrors] = useState({});
    const [enums, setEnums] = useState({});
    const [loading, setLoading] = useState(false);
    const [enumsLoading, setEnumsLoading] = useState(true);
    const [submitError, setSubmitError] = useState('');
    const [submitSuccess, setSubmitSuccess] = useState(false);

    // Load all enums at once
    useEffect(() => {
        setEnumsLoading(true);
        fetch(`${base}/enums/all`)
            .then(r => r.json())
            .then(data => {
                setEnums(data.enums || {});
                setEnumsLoading(false);
            })
            .catch(() => setEnumsLoading(false));
    }, [base]);

    const set = (field) => (value) => {
        setForm(prev => ({ ...prev, [field]: value }));
        if (errors[field]) setErrors(prev => { const e = { ...prev }; delete e[field]; return e; });
    };

    const entityType = form.entity_type?.toUpperCase();
    const isIndividual = entityType === 'INDIVIDUAL';
    const isBusiness   = entityType === 'BUSINESS';
    const isTrust      = entityType === 'TRUST';

    const handleSubmit = async (e) => {
        e.preventDefault();
        const errs = validate(form);
        if (Object.keys(errs).length) { setErrors(errs); return; }

        setLoading(true);
        setSubmitError('');

        const payload = {
            ...form,
            email:   form.email   || null,
            phone:   form.phone   || null,
            tax_id:  form.tax_id  || null,
            country: form.country || null,
            residency_status: form.residency_status || null,
            address_line1: form.address_line1 || null,
            address_line2: form.address_line2 || null,
            city:     form.city     || null,
            state:    form.state    || null,
            zip_code: form.zip_code || null,
            lifecycle_stage: form.lifecycle_stage || null,
            risk_profile:    form.risk_profile    || null,
            source:          form.source          || null,
            notes: form.notes || null,
            tags:  form.tags.length ? form.tags : null,
            // Clear irrelevant entity fields
            first_name:    isIndividual ? form.first_name    : null,
            last_name:     isIndividual ? form.last_name     : null,
            business_name: isBusiness   ? form.business_name : null,
            trust_name:    isTrust      ? form.trust_name    : null,
            date_of_birth:        isIndividual        ? (form.date_of_birth || null) : null,
            date_of_incorporation:(isBusiness||isTrust)? (form.date_of_incorporation || null) : null,
        };

        try {
            const res = await fetch(`${base}/clients`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) {
                const msg = Array.isArray(data?.detail)
                    ? data.detail.map(d => d.msg || JSON.stringify(d)).join('; ')
                    : data?.detail || 'Failed to create client';
                setSubmitError(msg);
            } else {
                setSubmitSuccess(true);
                setTimeout(() => {
                    setSubmitSuccess(false);
                    setForm({ ...EMPTY_FORM });
                    onSuccess && onSuccess(data);
                }, 1800);
            }
        } catch (err) {
            setSubmitError('Network error: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    if (enumsLoading) {
        return (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 24, marginBottom: 12 }}>⟳</div>
                <div style={{ fontSize: 13 }}>Loading form configuration…</div>
            </div>
        );
    }

    const opts = (type) => enums[type] || [];

    return (
        <form id="add-client-form" onSubmit={handleSubmit} style={{ height: '100%', overflowY: 'auto', padding: '4px 0 24px' }}>

            {/* ── Success banner ── */}
            {submitSuccess && (
                <div style={{
                    background: 'rgba(22,163,74,.12)', border: '1px solid rgba(22,163,74,.3)',
                    borderRadius: 'var(--radius)', padding: '12px 16px', marginBottom: 16,
                    display: 'flex', alignItems: 'center', gap: 10, color: 'var(--green)',
                    fontSize: 13, fontWeight: 600,
                }}>
                    <span style={{ fontSize: 18 }}>✅</span>
                    Client created successfully!
                </div>
            )}

            {/* ── Error banner ── */}
            {submitError && (
                <div style={{
                    background: 'rgba(239,68,68,.08)', border: '1px solid rgba(239,68,68,.25)',
                    borderRadius: 'var(--radius)', padding: '12px 16px', marginBottom: 16,
                    display: 'flex', alignItems: 'flex-start', gap: 10, color: 'var(--red)',
                    fontSize: 12, lineHeight: 1.5,
                }}>
                    <span style={{ fontSize: 16, flexShrink: 0 }}>⚠️</span>
                    <div>{submitError}</div>
                    <span onClick={() => setSubmitError('')} style={{ marginLeft: 'auto', cursor: 'pointer', opacity: .6, fontSize: 16 }}>×</span>
                </div>
            )}

            {/* ══ Section 1: Entity Information ══ */}
            <FormSection title="Entity Information" icon="🏢">
                <Field label="Entity Type" required error={errors.entity_type} fullWidth>
                    <SelectInput
                        value={form.entity_type}
                        onChange={set('entity_type')}
                        options={opts('entity_type')}
                        placeholder="Select entity type…"
                        error={errors.entity_type}
                    />
                </Field>

                {/* Individual fields */}
                {isIndividual && <>
                    <Field label="First Name" required error={errors.first_name}>
                        <TextInput value={form.first_name} onChange={set('first_name')} placeholder="John" error={errors.first_name} />
                    </Field>
                    <Field label="Last Name" required error={errors.last_name}>
                        <TextInput value={form.last_name} onChange={set('last_name')} placeholder="Doe" error={errors.last_name} />
                    </Field>
                    <Field label="Date of Birth">
                        <TextInput type="date" value={form.date_of_birth} onChange={set('date_of_birth')} />
                    </Field>
                </>}

                {/* Business fields */}
                {isBusiness && <>
                    <Field label="Business Name" required error={errors.business_name} fullWidth>
                        <TextInput value={form.business_name} onChange={set('business_name')} placeholder="Acme Corp LLC" error={errors.business_name} />
                    </Field>
                    <Field label="Date of Incorporation">
                        <TextInput type="date" value={form.date_of_incorporation} onChange={set('date_of_incorporation')} />
                    </Field>
                </>}

                {/* Trust fields */}
                {isTrust && <>
                    <Field label="Trust Name" required error={errors.trust_name} fullWidth>
                        <TextInput value={form.trust_name} onChange={set('trust_name')} placeholder="Johnson Family Trust" error={errors.trust_name} />
                    </Field>
                    <Field label="Date of Incorporation">
                        <TextInput type="date" value={form.date_of_incorporation} onChange={set('date_of_incorporation')} />
                    </Field>
                </>}
            </FormSection>

            {/* ══ Section 2: Contact Details ══ */}
            <FormSection title="Contact Details" icon="📞">
                <Field label="Email" error={errors.email}>
                    <TextInput type="email" value={form.email} onChange={set('email')} placeholder="client@example.com" error={errors.email} />
                </Field>
                <Field label="Phone" error={errors.phone}>
                    <TextInput type="tel" value={form.phone} onChange={set('phone')} placeholder="+1 (555) 000-0000" error={errors.phone} />
                </Field>
            </FormSection>

            {/* ══ Section 3: Tax Information ══ */}
            <FormSection title="Tax Information" icon="🧾">
                <Field label="Tax ID">
                    <TextInput value={form.tax_id} onChange={set('tax_id')} placeholder="PAN / SSN / EIN" />
                </Field>
                <Field label="Residency Status">
                    <SelectInput
                        value={form.residency_status} onChange={set('residency_status')}
                        options={opts('residency_status')} placeholder="Select status…"
                    />
                </Field>
                <Field label="Country" fullWidth>
                    <div style={{ position: 'relative' }}>
                        <SelectInput
                            value={form.country} onChange={set('country')}
                            options={opts('country').map(o => ({ ...o, label: `${countryFlag(o.code)}  ${o.label}` }))}
                            placeholder="Select country…"
                        />
                    </div>
                </Field>
            </FormSection>

            {/* ══ Section 4: Address ══ */}
            <FormSection title="Address" icon="📍">
                <Field label="Address Line 1" fullWidth>
                    <TextInput value={form.address_line1} onChange={set('address_line1')} placeholder="123 Main Street" />
                </Field>
                <Field label="Address Line 2" fullWidth>
                    <TextInput value={form.address_line2} onChange={set('address_line2')} placeholder="Suite 100, Apt B…" />
                </Field>
                <Field label="City">
                    <TextInput value={form.city} onChange={set('city')} placeholder="New York" />
                </Field>
                <Field label="ZIP / PIN">
                    <TextInput value={form.zip_code} onChange={set('zip_code')} placeholder="10001" />
                </Field>
                <Field label="State (US only)" fullWidth>
                    <SelectInput
                        value={form.state} onChange={set('state')}
                        options={opts('state')} placeholder="Select state…"
                    />
                </Field>
            </FormSection>

            {/* ══ Section 5: Client Classification ══ */}
            <FormSection title="Client Classification" icon="🏷️">
                <Field label="Lifecycle Stage">
                    <SelectInput
                        value={form.lifecycle_stage} onChange={set('lifecycle_stage')}
                        options={opts('lifecycle_stage')} placeholder="Select stage…"
                    />
                </Field>
                <Field label="Risk Profile">
                    <SelectInput
                        value={form.risk_profile} onChange={set('risk_profile')}
                        options={opts('risk_profile')} placeholder="Select risk…"
                    />
                </Field>
                <Field label="Source">
                    <SelectInput
                        value={form.source} onChange={set('source')}
                        options={opts('source')} placeholder="Select source…"
                    />
                </Field>
            </FormSection>

            {/* ══ Section 6: Additional Information ══ */}
            <FormSection title="Additional Information" icon="📝">
                <Field label="Notes" fullWidth>
                    <TextAreaInput
                        value={form.notes} onChange={set('notes')}
                        placeholder="Free-form notes about the client…"
                    />
                </Field>
                <Field
                    label="Tags"
                    fullWidth
                    error={errors.tags}
                >
                    <TagInput tags={form.tags} onChange={set('tags')} error={errors.tags} />
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                        Type a tag and press <kbd style={{ background: 'var(--surface-3)', padding: '1px 5px', borderRadius: 3, fontSize: 10 }}>,</kbd> or <kbd style={{ background: 'var(--surface-3)', padding: '1px 5px', borderRadius: 3, fontSize: 10 }}>Enter</kbd> to add. E.g.: HNI, Startup, NRI
                    </div>
                </Field>
            </FormSection>

            <style>{`
                @keyframes spin { to { transform: rotate(360deg); } }
            `}</style>
        </form>
    );
}
