// 9. Issues and recommendations, most severe first.
import { Section } from './ui.jsx'

const SEVERITY = {
  High: 'bg-red-100 text-red-800',
  Medium: 'bg-amber-100 text-amber-800',
  Low: 'bg-slate-100 text-slate-700',
}

export default function IssuesSection({ issues }) {
  return (
    <Section id="issues" title="9. Issues and recommendations">
      {issues.length === 0 && <p className="text-sm text-slate-500">No issues found.</p>}
      <ul className="space-y-2">
        {issues.map((i, n) => (
          <li key={n} className="flex flex-col gap-1 rounded-lg border border-slate-200 p-3 sm:flex-row sm:items-start sm:gap-3">
            <span className={`w-fit shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${SEVERITY[i.severity]}`}>{i.severity}</span>
            <div className="text-sm">
              <div className="font-medium text-slate-900">{i.title}</div>
              <div className="text-slate-600">→ {i.suggestion}</div>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  )
}
