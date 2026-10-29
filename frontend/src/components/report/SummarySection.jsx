// 1. Call summary: score, verdict, strengths/problems, score per part.
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BLUE, GRID, MUTED, Section, Tile, Tiles, duration, na, yesNo } from './ui.jsx'

const PART_LABELS = {
  accuracy: 'Accuracy', mishearings: 'Mishearings', latency: 'Latency',
  voice_quality: 'Voice quality', language: 'Language support', cost: 'Cost',
}
const VERDICT_STYLE = {
  Good: 'bg-green-100 text-green-800',
  'Needs improvement': 'bg-amber-100 text-amber-800',
  Poor: 'bg-red-100 text-red-800',
}

export default function SummarySection({ report }) {
  const { call, summary } = report
  const parts = Object.entries(summary.parts).map(([key, value]) => ({
    name: PART_LABELS[key],
    score: value ?? 0,
    label: value === null ? 'not rated' : Math.round(value),
    weight: summary.effective_weights[key],
  }))

  return (
    <Section id="summary" title="1. Call summary">
      <Tiles>
        <Tile label="Provider · model" value={call.provider} hint={call.model} />
        <Tile label="Language · voice" value={call.language} hint={na(call.voice)} />
        <Tile label="Duration · date" value={duration(call.duration_s)} hint={call.started_at?.slice(0, 16).replace('T', ' ')} />
        <Tile
          label="Audio mode · form completed"
          value={call.audio_mode === 'phone_8khz' ? 'Phone 8 kHz' : 'Normal'}
          hint={`Form completed: ${yesNo(call.form_completed)}`}
        />
      </Tiles>

      <div className="my-4 flex flex-wrap items-center gap-4">
        <div className="text-5xl font-extrabold text-slate-900">
          {na(summary.score)}
          <span className="text-lg font-normal text-slate-500">/100</span>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-semibold ${VERDICT_STYLE[summary.verdict] || 'bg-slate-100'}`}>
          {summary.verdict}
        </span>
        {summary.verdict_note && <span className="text-xs italic text-slate-500">{summary.verdict_note}</span>}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="mb-1 text-sm font-semibold text-green-800">Key strengths</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {summary.strengths.length ? summary.strengths.map((s) => <li key={s}>{s}</li>) : <li>None stood out.</li>}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 text-sm font-semibold text-red-800">Key problems</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {summary.problems.length ? summary.problems.map((p) => <li key={p}>{p}</li>) : <li>No problems found.</li>}
          </ul>
        </div>
      </div>

      <h3 className="mb-1 mt-5 text-sm font-semibold text-slate-700">Score per part (0-100)</h3>
      <div className="h-56">
        <ResponsiveContainer>
          <BarChart data={parts} layout="vertical" margin={{ left: 10, right: 50 }}>
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: MUTED }} />
            <YAxis type="category" dataKey="name" width={115} tick={{ fontSize: 12, fill: MUTED }} />
            <Tooltip
              cursor={{ fill: '#f4f3f0' }}
              formatter={(v, n, p) => [p.payload.label === 'not rated' ? 'not rated' : `${p.payload.label} (weight ${p.payload.weight ?? 0}%)`, 'Score']}
            />
            <Bar dataKey="score" fill={BLUE} radius={[0, 4, 4, 0]} barSize={16}>
              <LabelList dataKey="label" position="right" style={{ fontSize: 11, fill: '#0b0b0b' }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs italic text-slate-500">
        Not-rated parts are left out and their weight is shared by the others.
        {summary.missing_parts.length > 0 && ` Missing: ${summary.missing_parts.map((k) => PART_LABELS[k]).join(', ')}.`}
      </p>
    </Section>
  )
}
