// 4. Voice quality: tester ratings (editable), optional MOS, audio issues.
import { useEffect, useState } from 'react'
import { Section, Tile, Tiles, na } from './ui.jsx'

const RATING_FIELDS = [
  ['naturalness', 'Naturalness'],
  ['clarity', 'Clarity'],
  ['pronunciation', 'Pronunciation'],
  ['accent_fit', 'Accent fit for the language'],
  ['politeness', 'Politeness / tone'],
  ['code_mixing', 'Code-mixing handling (e.g. Hinglish)'],
]

function Stars({ value, onChange }) {
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(value === n ? null : n)}
          className={`h-7 w-7 rounded border text-sm font-medium ${
            value && n <= value ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-300 text-slate-500 hover:bg-slate-50'
          }`}
          aria-label={`${n} of 5`}
        >
          {n}
        </button>
      ))}
    </div>
  )
}

export default function VoiceQualitySection({ data, codeMixing, onSaveRatings, saving }) {
  const [form, setForm] = useState({})
  useEffect(() => {
    setForm({ ...data.ratings, code_mixing: codeMixing, notes: data.tester_notes || '' })
  }, [data, codeMixing])

  const issues = data.issues
  return (
    <Section id="voice_quality" title="4. Voice quality">
      <Tiles>
        <Tile label="Average tester rating" value={data.ratings_avg ? `${data.ratings_avg} / 5` : 'not rated'} hint={`${data.ratings_count} of 5 rated`} />
        <Tile label="MOS (automatic, 1-5)" value={na(data.mos.mos)} hint={data.mos.reason || data.mos.model} />
        <Tile label="Long silences (> 2 s)" value={issues.long_silences.length} tone={issues.long_silences.length ? 'warn' : undefined} />
        <Tile label="Talk-overs · cut-offs" value={`${issues.talk_over_count} · ${issues.cut_off_sentences.length}`} />
      </Tiles>
      {issues.repeated_phrases.length > 0 && (
        <p className="mt-2 text-sm text-slate-700">
          Repeated phrases: {issues.repeated_phrases.map((p) => `"${p.text}" × ${p.times}`).join('; ')}
        </p>
      )}

      <form
        className="mt-4 rounded-lg border border-slate-200 p-3"
        onSubmit={(e) => {
          e.preventDefault()
          onSaveRatings(form)
        }}
      >
        <h3 className="mb-2 text-sm font-semibold text-slate-700">Tester ratings (1 = poor, 5 = excellent)</h3>
        <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {RATING_FIELDS.map(([key, label]) => (
            <div key={key} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="text-slate-700">{label}</span>
              <Stars value={form[key] ?? null} onChange={(v) => setForm((f) => ({ ...f, [key]: v }))} />
            </div>
          ))}
        </div>
        <textarea
          className="mt-3 w-full rounded border border-slate-300 p-2 text-sm"
          rows={2}
          placeholder="Notes (no personal data)"
          value={form.notes || ''}
          onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
        />
        <button
          type="submit"
          disabled={saving}
          className="mt-2 rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save ratings & update report'}
        </button>
      </form>
    </Section>
  )
}
