// 6. Language support.
import { Section, Tile, Tiles, na, pct } from './ui.jsx'

export default function LanguageSection({ data }) {
  const pctValue = data.agent_correct_language_pct
  return (
    <Section id="language" title="6. Language support" note={data.detection_note}>
      <Tiles>
        <Tile label="Selected language" value={data.selected} />
        <Tile label="Detected from caller" value={data.detected_caller_languages.join(', ') || 'n/a'}
          hint={`${data.code_mixed_caller_turns} code-mixed caller turn(s)`} />
        <Tile label="Agent replied in the right language" value={pct(pctValue)}
          hint={`${data.agent_correct_language_turns} of ${data.agent_turns_judged} judged turns`}
          tone={pctValue !== null && pctValue < 0.9 ? 'bad' : undefined} />
        <Tile label="Code-mixing handling (tester)" value={data.code_mixing_rating ? `${data.code_mixing_rating} / 5` : 'not rated'}
          hint="Rate it in section 4" />
      </Tiles>
      <p className="mt-3 text-sm text-slate-700">
        Language-specific mishearings: <b>{na(data.language_mishearings)}</b>
        {data.agent_wrong_language_turn_indexes.length > 0 &&
          ` · Wrong-language agent turns are marked grey in the transcript.`}
      </p>
    </Section>
  )
}
