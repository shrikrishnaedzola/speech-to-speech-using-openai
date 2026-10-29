// 2. Transcript as chat bubbles with coloured highlights.
import { Section } from './ui.jsx'

const TAGS = {
  mishearing: { label: 'Mishearing', bubble: 'bg-red-50 border-red-400', chip: 'bg-red-100 text-red-800' },
  reask: { label: 'Re-asked', bubble: 'bg-orange-50 border-orange-400', chip: 'bg-orange-100 text-orange-800' },
  interruption: { label: 'Interruption', bubble: 'bg-violet-50 border-violet-400', chip: 'bg-violet-100 text-violet-800' },
  wrong_language: { label: 'Wrong language', bubble: 'border-dashed border-slate-400', chip: 'bg-slate-200 text-slate-700' },
}

function Bubble({ item }) {
  const isAgent = item.role === 'agent'
  const first = item.tags.find((t) => TAGS[t])
  const tone = first ? TAGS[first].bubble : isAgent ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-200'
  return (
    <div className={`flex ${isAgent ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-[85%] rounded-lg border px-3 py-2 text-sm ${tone}`}>
        <div className="mb-0.5 flex flex-wrap items-center gap-1 text-[11px] text-slate-500">
          <span>{item.time} · {isAgent ? 'Agent' : 'Caller'}</span>
          {item.detected_language && <span className="rounded bg-white px-1 text-slate-600 ring-1 ring-slate-200">{item.detected_language}</span>}
          {item.tags.filter((t) => TAGS[t]).map((t) => (
            <span key={t} className={`rounded-full px-1.5 ${TAGS[t].chip}`}>{TAGS[t].label}</span>
          ))}
        </div>
        <div className="text-slate-800">{item.text}</div>
      </div>
    </div>
  )
}

function ToolRow({ item }) {
  return (
    <div className="flex justify-center">
      <div className={`rounded border px-2 py-0.5 text-xs ${item.success ? 'border-blue-300 bg-blue-50 text-blue-800' : 'border-red-300 bg-red-50 text-red-800'}`}>
        {item.time} · 🔧 {item.name}({item.field_id || ''}{item.value ? ` = "${item.value}"` : ''}) ·{' '}
        {item.success ? 'ok' : `failed: ${item.error || ''}`}
      </div>
    </div>
  )
}

export default function TranscriptSection({ transcript }) {
  return (
    <Section id="transcript" title="2. Transcript">
      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        {Object.values(TAGS).map((t) => (
          <span key={t.label} className={`rounded-full px-2 py-0.5 ${t.chip}`}>{t.label}</span>
        ))}
        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-blue-800">Tool call</span>
      </div>
      <div className="max-h-[36rem] space-y-1.5 overflow-y-auto pr-1">
        {transcript.items.length === 0 && <p className="text-sm text-slate-400">No transcript recorded.</p>}
        {transcript.items.map((item, i) =>
          item.kind === 'turn' ? <Bubble key={i} item={item} /> : <ToolRow key={i} item={item} />,
        )}
      </div>
    </Section>
  )
}
