// Column 3: response times, counts, scores, cost, tool calls and raw events.
import Panel from './Panel.jsx'

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900">{value ?? '—'}</div>
      {hint && <div className="text-[11px] text-slate-400">{hint}</div>}
    </div>
  )
}

const pct = (x) => (x === null || x === undefined ? null : `${Math.round(x * 100)}%`)
const formatDuration = (s) => (s ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}` : null)

export default function MetricsPanel({
  report, mode, inCall, elapsed, interruptions, usageSeconds, ratePerMin, liveInitSeconds, rawEvents, errors,
}) {
  const metrics = report?.metrics
  const scores = report?.scores
  const latencies = metrics?.turn_latencies_ms || []

  // While the call runs, estimate cost locally; afterwards use the backend's number.
  let cost
  if (inCall) {
    const seconds = usageSeconds ?? elapsed + (mode === 'live' ? liveInitSeconds : 0)
    cost = { usd: (seconds / 60) * ratePerMin, seconds }
  } else if (report?.cost) {
    cost = { usd: report.cost.estimated_usd, seconds: report.cost.billable_seconds }
  }

  const duration = inCall ? elapsed : metrics?.duration_s
  const interruptionCount = inCall ? interruptions : (metrics?.interruptions ?? interruptions)

  return (
    <Panel title="3. Test Metrics & Logs">
      {errors.length > 0 && (
        <div className="space-y-1 rounded-lg border border-red-300 bg-red-50 p-2">
          {errors.map((e, i) => (
            <div key={i} className="text-xs text-red-700">
              {e.ts.toLocaleTimeString()} - {e.message}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat label="Avg response" value={metrics?.avg_latency_ms != null ? `${metrics.avg_latency_ms} ms` : null} />
        <Stat label="Max response" value={metrics?.max_latency_ms != null ? `${metrics.max_latency_ms} ms` : null} />
        <Stat label="Turns" value={metrics?.turns ?? 0} />
        <Stat label="Interruptions" value={interruptionCount} />
        <Stat label="Duration" value={formatDuration(duration)} />
        <Stat
          label="Est. cost"
          value={cost ? `$${cost.usd.toFixed(4)}` : null}
          hint={cost ? `${cost.seconds.toFixed(0)}s billable` : null}
        />
        <Stat
          label="Accuracy"
          value={pct(scores?.accuracy)}
          hint={scores ? `${scores.correct_fields}/${scores.filled_fields} correct (${scores.reviewed_fields} reviewed)` : null}
        />
        <Stat
          label="Completion"
          value={pct(scores?.completion)}
          hint={scores ? `${scores.required_filled}/${scores.required_total} required` : null}
        />
      </div>
      {mode === 'live' && (
        <p className="text-[11px] text-slate-400">
          Cost covers voice minutes only. Delegated tool-model tokens are billed separately.
        </p>
      )}

      <div>
        <h3 className="mb-1 text-sm font-semibold text-slate-700">Response time per turn</h3>
        <p className="mb-2 text-[11px] text-slate-400">Caller stops speaking → first agent audio (measured in browser).</p>
        {latencies.length === 0 && <p className="text-xs text-slate-400">No turns yet.</p>}
        <div className="space-y-1">
          {latencies.map((t) => {
            const max = metrics.max_latency_ms || 1
            return (
              <div key={t.turn} className="flex items-center gap-2 text-xs">
                <span className="w-8 text-slate-500">#{t.turn}</span>
                <div className="h-2 flex-1 rounded bg-slate-100">
                  <div
                    className={`h-2 rounded ${t.latency_ms > 1500 ? 'bg-red-400' : 'bg-blue-400'}`}
                    style={{ width: `${(t.latency_ms / max) * 100}%` }}
                  />
                </div>
                <span className="w-16 text-right tabular-nums">{t.latency_ms} ms</span>
              </div>
            )
          })}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-700">Tool calls ({report?.tool_calls?.length || 0})</h3>
        <div className="space-y-1">
          {(report?.tool_calls || []).map((t) => (
            <details key={t.id} className="rounded border border-slate-200 text-xs">
              <summary className="flex cursor-pointer items-center gap-2 px-2 py-1">
                <span className={t.success ? 'text-green-600' : 'text-red-600'}>{t.success ? '✔' : '✖'}</span>
                <span className="font-mono">{t.name}</span>
                <span className="truncate text-slate-500">{t.arguments.field_id || ''}</span>
                <span className="ml-auto tabular-nums text-slate-400">{t.duration_ms} ms</span>
              </summary>
              <pre className="overflow-x-auto bg-slate-50 p-2">
                {JSON.stringify({ arguments: t.arguments, result: t.result }, null, 2)}
              </pre>
            </details>
          ))}
        </div>
      </div>

      <details className="rounded border border-slate-200">
        <summary className="cursor-pointer px-2 py-1 text-sm font-semibold text-slate-700">
          Raw event log ({rawEvents.length})
        </summary>
        <div className="max-h-96 overflow-y-auto p-2 font-mono text-[11px]">
          {rawEvents.map((r, i) => (
            <details key={i} className={r.event.type === 'error' ? 'text-red-600' : 'text-slate-700'}>
              <summary className="cursor-pointer">
                {r.ts.toLocaleTimeString()} {r.event.type}
              </summary>
              <pre className="overflow-x-auto bg-slate-50 p-1">{JSON.stringify(r.event, null, 2)}</pre>
            </details>
          ))}
        </div>
      </details>
    </Panel>
  )
}
