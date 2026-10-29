// 5. Latency: stats, reply time per turn (status-coloured), STT/LLM/TTS split (Sarvam).
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ChartTooltip, GRID, MUTED, RatingBadge, SERIES, STATUS, Section, Tile, Tiles, ms } from './ui.jsx'

export default function LatencySection({ data }) {
  const th = data.thresholds
  const perTurn = data.per_turn.map((t) => ({ ...t, fill: STATUS[t.rating] }))

  return (
    <Section id="latency" title="5. Latency">
      <Tiles>
        <Tile label="Average" value={ms(data.avg_ms)} hint={<RatingBadge rating={data.rating} />} />
        <Tile label="Median" value={ms(data.median_ms)} />
        <Tile label="p90" value={ms(data.p90_ms)} hint="90% of replies were at or below this" />
        <Tile label="Max" value={ms(data.max_ms)} hint={`${data.turns} turns measured`} />
      </Tiles>

      {perTurn.length > 0 && (
        <>
          <h3 className="mb-1 mt-5 text-sm font-semibold text-slate-700">Reply time per turn</h3>
          {/* Legend: colour + label for each rating band */}
          <div className="mb-1 flex flex-wrap gap-3 text-xs text-slate-600">
            <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: STATUS.Good }} />Good &lt; {th.good} ms</span>
            <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: STATUS.OK }} />OK {th.good}-{th.ok} ms</span>
            <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm" style={{ background: STATUS.Poor }} />Poor &gt; {th.ok} ms</span>
          </div>
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={perTurn} margin={{ top: 10, right: 60, left: 0 }}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="turn" tick={{ fontSize: 11, fill: MUTED }} />
                {/* Always tall enough to show the "OK" limit line */}
                <YAxis tick={{ fontSize: 11, fill: MUTED }} width={50}
                  domain={[0, (max) => Math.ceil(Math.max(max, th.ok * 1.1) / 250) * 250]} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: '#f4f3f0' }} />
                <ReferenceLine y={th.good} stroke={MUTED} strokeDasharray="4 3"
                  label={{ value: `Good ${th.good}`, position: 'right', fontSize: 10, fill: MUTED }} />
                <ReferenceLine y={th.ok} stroke={MUTED} strokeDasharray="4 3"
                  label={{ value: `OK ${th.ok}`, position: 'right', fontSize: 10, fill: MUTED }} />
                <Bar dataKey="latency_ms" name="Reply time" radius={[4, 4, 0, 0]} maxBarSize={28}>
                  {perTurn.map((t) => <Cell key={t.turn} fill={t.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {data.has_stage_split && (
        <>
          <h3 className="mb-1 mt-5 text-sm font-semibold text-slate-700">Time per stage (STT / LLM / TTS)</h3>
          <div className="h-60">
            <ResponsiveContainer>
              <BarChart data={data.per_turn} margin={{ top: 10, right: 20, left: 0 }}>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="turn" tick={{ fontSize: 11, fill: MUTED }} />
                <YAxis tick={{ fontSize: 11, fill: MUTED }} width={50} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: '#f4f3f0' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {/* white stroke = 2px gap between stacked segments */}
                <Bar dataKey="stt_ms" name="STT" stackId="s" fill={SERIES.STT} stroke="#fff" strokeWidth={2} maxBarSize={28} />
                <Bar dataKey="llm_ms" name="LLM" stackId="s" fill={SERIES.LLM} stroke="#fff" strokeWidth={2} maxBarSize={28} />
                <Bar dataKey="tts_ms" name="TTS" stackId="s" fill={SERIES.TTS} stroke="#fff" strokeWidth={2} maxBarSize={28}
                  radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      <h3 className="mb-1 mt-4 text-sm font-semibold text-slate-700">Slowest 3 turns</h3>
      <ul className="space-y-1 text-sm text-slate-700">
        {data.slowest.map((s) => (
          <li key={s.turn}>
            <span className="font-medium">Turn {s.turn}: {ms(s.latency_ms)}</span> - {s.context}
          </li>
        ))}
        {data.slowest.length === 0 && <li className="text-slate-400">No turns measured.</li>}
      </ul>
    </Section>
  )
}
