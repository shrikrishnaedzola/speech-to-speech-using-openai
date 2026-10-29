// Column 2: one card per active form field, with tester Correct/Wrong marks.
import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Panel from './Panel.jsx'

const BADGES = {
  pending: { label: 'Pending', className: 'bg-slate-100 text-slate-600' },
  filled: { label: 'Filled', className: 'bg-green-100 text-green-800' },
  needs_confirmation: { label: 'Needs confirmation', className: 'bg-amber-100 text-amber-800' },
  skipped: { label: 'Skipped', className: 'bg-slate-200 text-slate-700' },
}

function formatValue(value) {
  if (value === null || value === undefined) return '—'
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}

function ReviewControls({ field, onReview }) {
  const mark = field.review?.mark || null
  const [expected, setExpected] = useState(field.review?.expected_value || '')
  useEffect(() => {
    setExpected(field.review?.expected_value || '')
  }, [field.review?.expected_value])

  const button = (value, label, active) => (
    <button
      className={`rounded px-2 py-0.5 text-xs font-medium ${
        mark === value ? active : 'border border-slate-300 text-slate-600 hover:bg-slate-50'
      }`}
      onClick={() => onReview(field.id, mark === value ? null : value, expected)}
    >
      {label}
    </button>
  )

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      {button('correct', 'Correct', 'bg-green-600 text-white')}
      {button('wrong', 'Wrong', 'bg-red-600 text-white')}
      <input
        className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-0.5 text-xs"
        placeholder="Expected value"
        value={expected}
        onChange={(e) => setExpected(e.target.value)}
        // Save the expected value when leaving the box (keeps the current mark).
        onBlur={() => mark && expected !== (field.review?.expected_value || '') && onReview(field.id, mark, expected)}
      />
    </div>
  )
}

function FieldCard({ field, onReview }) {
  const badge = BADGES[field.status] || BADGES.pending
  const hasValue = field.value !== null && field.value !== undefined
  return (
    <div
      className={`rounded-lg border p-3 transition-colors ${
        field.review?.mark === 'wrong' ? 'border-red-300' : 'border-slate-200'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-slate-800">
            {field.label}
            {field.required && <span className="text-red-500"> *</span>}
          </div>
          <div className="text-[11px] text-slate-400">
            {field.id}
            {field.condition && <> · follow-up: {field.condition}</>}
          </div>
        </div>
        <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}>
          {badge.label}
        </span>
      </div>
      <div className="mt-1 text-base text-slate-900">{formatValue(field.value)}</div>
      {field.confidence === 'low' && <div className="text-xs text-amber-700">Low confidence</div>}
      {field.reason && <div className="text-xs text-slate-500">Reason: {field.reason}</div>}
      {hasValue && <ReviewControls field={field} onReview={onReview} />}
    </div>
  )
}

export default function FormPanel({ report, callId, onReview }) {
  const fields = report?.fields || []
  const active = fields.filter((f) => f.active)
  const hiddenCount = fields.length - active.length

  return (
    <Panel
      title={`2. Form Data${report ? ` - ${report.form.name}` : ''}`}
      actions={
        callId && (
          <div className="flex gap-2 text-sm">
            <a className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50" href={api.exportUrl(callId, 'json')}>
              Export JSON
            </a>
            <a className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50" href={api.exportUrl(callId, 'csv')}>
              Export CSV
            </a>
          </div>
        )
      }
    >
      {!report && <p className="text-sm text-slate-400">Start a call or a simulation to see the form.</p>}
      {active.map((f) => (
        <FieldCard key={f.id} field={f} onReview={onReview} />
      ))}
      {hiddenCount > 0 && (
        <p className="text-xs text-slate-400">
          {hiddenCount} follow-up field(s) hidden because their condition is not met.
        </p>
      )}
    </Panel>
  )
}
