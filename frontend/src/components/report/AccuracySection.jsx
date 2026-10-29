// 7. Accuracy of the form data.
import { Section, Table, Tile, Tiles, na, pct } from './ui.jsx'

export default function AccuracySection({ data }) {
  const correctCell = (c) =>
    c === true ? <span className="text-green-700">✔ Yes</span> : c === false ? <span className="font-semibold text-red-700">✖ No</span> : <span className="text-slate-400">not checked</span>

  return (
    <Section id="accuracy" title="7. Accuracy (form data)">
      <Tiles>
        <Tile label="Field accuracy" value={pct(data.field_accuracy)} hint={`${data.correct_fields} correct of ${data.filled_fields} filled`} />
        <Tile label="Completion" value={pct(data.completion)} hint={`${data.required_filled} of ${data.required_total} required fields`} />
        <Tile label="Invalid answers re-asked & fixed" value={`${data.invalid_answers_recovered} / ${data.invalid_answers}`}
          hint={`${data.corrections_saved} correction(s) saved`} />
        <Tile label="Tool call success" value={pct(data.tool_success_rate)}
          hint={`${data.tool_calls_total} calls · ${data.validation_errors.length} validation errors`} />
      </Tiles>

      <h3 className="mb-1 mt-4 text-sm font-semibold text-slate-700">
        Follow-up questions ({data.follow_up_errors} error{data.follow_up_errors === 1 ? '' : 's'})
      </h3>
      <Table
        head={['Field', 'Rule', 'Needed?', 'Asked?', 'Correct?']}
        rows={data.follow_ups.map((f) => [f.label, f.condition, f.needed ? 'Yes' : 'No', f.asked ? 'Yes' : 'No', correctCell(f.correct)])}
        empty="This form has no follow-up questions."
      />

      <h3 className="mb-1 mt-4 text-sm font-semibold text-slate-700">Fields</h3>
      <Table
        head={['Field', 'Expected', 'Saved', 'Correct?', 'Notes']}
        rows={data.table.map((r) => [r.label, na(r.expected), na(r.saved), r.saved === null ? '—' : correctCell(r.correct), <span className="text-xs text-slate-600">{r.notes}</span>])}
      />

      {data.validation_errors.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-slate-600">Backend validation errors ({data.validation_errors.length})</summary>
          <ul className="mt-1 list-disc pl-5 text-slate-700">
            {data.validation_errors.map((e, i) => <li key={i}>{e.name}({na(e.field_id)}): {e.error}</li>)}
          </ul>
        </details>
      )}
    </Section>
  )
}
