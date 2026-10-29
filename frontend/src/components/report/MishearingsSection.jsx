// 3. Mishearings: what was said vs what the AI heard.
import { Section, Table, Tile, Tiles, mmss, na, pct } from './ui.jsx'

const SOURCE = {
  value: 'Saved value differs from expected',
  changed_value: 'Answer changed later',
  marked_wrong: 'Tester marked wrong',
  caller_correction: 'Caller corrected the agent',
}

export default function MishearingsSection({ data }) {
  const rows = data.items.map((m) => [
    mmss(m.ts_ms),
    <span className="font-medium text-slate-900">{na(m.said)}</span>,
    <span className="text-red-700">{na(m.heard)}</span>,
    na(m.field_label),
    m.fixed ? <span className="text-green-700">✔ Yes</span> : <span className="font-semibold text-red-700">✖ No</span>,
    <span className="text-xs text-slate-600">
      {SOURCE[m.source]}
      {m.number_issue && <><br />{m.number_issue}</>}
      {m.caller_correction && m.source !== 'caller_correction' && <><br />Caller: "{m.caller_correction}"</>}
    </span>,
  ])
  const changedLines = data.script?.lines.filter((l) => l.wer > 0) || []

  return (
    <Section id="mishearings" title="3. Mishearings" note={data.note}>
      <Tiles>
        <Tile label="Mishearings" value={data.total} tone={data.unfixed ? 'bad' : undefined} />
        <Tile label="Fixed later in the call" value={`${data.fixed} / ${data.total}`} />
        <Tile label="Number mix-ups" value={data.number_issues} tone={data.number_issues ? 'warn' : undefined} />
        <Tile label="WER · CER" value={`${pct(data.wer)} · ${pct(data.cer)}`} hint="CER suits Indian scripts better" />
      </Tiles>
      <div className="mt-4">
        <Table
          head={['Time', 'What was said', 'What the AI heard', 'Field', 'Fixed?', 'Notes']}
          rows={rows}
          empty="No mishearings found."
        />
      </div>
      {data.script && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-slate-600">
            Expected script vs transcript ({changedLines.length} of {data.script.lines.length} lines differ)
          </summary>
          <Table
            head={['Expected', 'Transcribed', 'WER', 'CER']}
            rows={changedLines.map((l) => [l.expected, l.heard, pct(l.wer), pct(l.cer)])}
            empty="All lines matched."
          />
        </details>
      )}
    </Section>
  )
}
