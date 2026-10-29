// Small shared pieces for the report page.

// Colours from the reference data-viz palette.
export const STATUS = { Good: '#0ca30c', OK: '#fab219', Poor: '#d03b3b' } // always shown with a text label
export const SERIES = { STT: '#2a78d6', LLM: '#eb6834', TTS: '#1baf7a' } // validated categorical order
export const BLUE = '#2a78d6'
export const GRID = '#e4e3df'
export const MUTED = '#52514e'

export const pct = (v) => (v === null || v === undefined ? 'n/a' : `${Math.round(v * 100)}%`)
export const ms = (v) => (v === null || v === undefined ? 'n/a' : `${Math.round(v).toLocaleString()} ms`)
export const na = (v) => (v === null || v === undefined || v === '' ? 'n/a' : String(v))
export const usd = (v) => (v === null || v === undefined ? 'n/a' : v < 1 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`)
export const inr = (v) => (v === null || v === undefined ? 'n/a' : `₹${v.toFixed(2)}`)
export const yesNo = (v) => (v === true ? 'Yes' : v === false ? 'No' : 'n/a')
export const duration = (s) => (s ? `${Math.floor(s / 60)} min ${Math.floor(s % 60)} s` : 'n/a')
export const mmss = (tsMs) => {
  if (tsMs === null || tsMs === undefined) return '--:--'
  const s = Math.floor(tsMs / 1000)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export function Section({ id, title, children, note }) {
  return (
    <section id={id} className="scroll-mt-20 rounded-lg bg-white p-4 shadow-sm sm:p-5">
      <h2 className="mb-3 border-b border-slate-200 pb-2 text-lg font-semibold text-slate-800">{title}</h2>
      {children}
      {note && <p className="mt-3 text-xs italic text-slate-500">{note}</p>}
    </section>
  )
}

export function Tile({ label, value, hint, tone }) {
  const tones = { good: 'text-green-700', bad: 'text-red-700', warn: 'text-amber-700' }
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-lg font-semibold ${tones[tone] || 'text-slate-900'}`}>{value}</div>
      {hint && <div className="text-[11px] text-slate-500">{hint}</div>}
    </div>
  )
}

export function Tiles({ children }) {
  return <div className="grid grid-cols-2 gap-2 md:grid-cols-4">{children}</div>
}

// Status badge: colour + text, never colour alone.
export function RatingBadge({ rating }) {
  if (!rating) return <span className="text-slate-400">n/a</span>
  const style = {
    Good: 'bg-green-100 text-green-800',
    OK: 'bg-amber-100 text-amber-800',
    Poor: 'bg-red-100 text-red-800',
  }[rating]
  const icon = { Good: '✔', OK: '●', Poor: '✖' }[rating]
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>{icon} {rating}</span>
}

export function Table({ head, rows, empty = 'Nothing to show.' }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            {head.map((h) => (
              <th key={h} className="py-1.5 pr-3 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={head.length} className="py-2 text-slate-400">{empty}</td></tr>
          )}
          {rows.map((cells, i) => (
            <tr key={i} className="border-b border-slate-100 align-top">
              {cells.map((c, j) => (
                <td key={j} className="py-1.5 pr-3">{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Recharts tooltip in the page's text colours.
export function ChartTooltip({ active, payload, label, labelPrefix = 'Turn', unit = 'ms' }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded border border-slate-200 bg-white px-2 py-1 text-xs shadow">
      <div className="font-medium text-slate-800">{labelPrefix} {label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-1.5 text-slate-700">
          <span className="inline-block h-2 w-2 rounded-sm" style={{ background: p.color || p.payload.fill }} />
          {p.name}: {Math.round(p.value).toLocaleString()} {unit}
          {p.payload.rating && p.name === 'Reply time' && <span className="text-slate-500">({p.payload.rating})</span>}
        </div>
      ))}
    </div>
  )
}
