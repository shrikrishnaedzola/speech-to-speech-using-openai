// 10. Optional AI-written summary (clearly labelled, numbers checked by the backend).
import { Section } from './ui.jsx'

export default function AiSummarySection({ summary, onGenerate, busy }) {
  return (
    <Section id="ai_summary" title="10. AI-written summary (optional)">
      {summary?.text ? (
        <div className="rounded-lg border border-dashed border-slate-400 p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-800">
            {summary.label}
            {summary.stale && <span className="ml-2 font-normal normal-case text-slate-500">(written for an earlier version of this report)</span>}
          </div>
          <p className="whitespace-pre-line text-sm text-slate-800">{summary.text}</p>
          {summary.unverified_numbers?.length > 0 && (
            <p className="mt-2 text-sm font-medium text-red-700">
              ⚠ These numbers were not in the metrics - check them before sharing: {summary.unverified_numbers.join(', ')}
            </p>
          )}
          <p className="mt-2 text-[11px] text-slate-400">Model: {summary.model} · {summary.generated_at}</p>
        </div>
      ) : summary?.error ? (
        <p className="text-sm text-red-700">AI summary failed: {summary.error}</p>
      ) : (
        <p className="text-sm text-slate-500">
          Not generated. The AI only sees the computed metrics and the masked transcript, and every number it writes is checked.
        </p>
      )}
      <button
        onClick={onGenerate}
        disabled={busy}
        className="mt-3 rounded border border-slate-400 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
      >
        {busy ? 'Writing summary…' : summary?.text ? 'Rewrite AI summary' : 'Generate AI summary'}
      </button>
    </Section>
  )
}
