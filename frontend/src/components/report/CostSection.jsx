// 8. Cost.
import { Section, Table, Tile, Tiles, inr, na, usd } from './ui.jsx'

export default function CostSection({ data }) {
  return (
    <Section id="cost" title="8. Cost" note={`Rates last updated: ${data.rates_last_updated}. Edit rates in report_module/settings.json.`}>
      <Tiles>
        <Tile label="This call" value={usd(data.total_usd)} hint={`${inr(data.total_inr)} at ₹${data.inr_per_usd}/USD`} />
        <Tile label="Per minute" value={usd(data.cost_per_min_usd)} />
        <Tile label="Per completed form" value={usd(data.cost_per_completed_form_usd)} hint={data.cost_per_completed_form_usd === null ? 'form not completed or no cost' : undefined} />
        <Tile label="1,000 similar calls" value={usd(data.projection_1000_calls_usd)} hint={inr(data.projection_1000_calls_inr)} />
      </Tiles>
      <div className="mt-4">
        <Table
          head={['Item', 'Usage', 'Rate (USD)', 'Cost']}
          rows={data.breakdown.map((b) => [
            <>{b.label}{!b.verified && <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] text-amber-800">unverified</span>}</>,
            `${na(b.usage)} ${b.usage_key}`,
            b.rate_usd === null ? <span className="text-slate-400">not set</span> : `${b.rate_usd} per ${b.unit.toLocaleString()}`,
            usd(b.usd),
          ])}
          empty="No rates configured for this provider."
        />
      </div>
      {data.warnings.map((w) => <p key={w} className="mt-1 text-xs text-amber-700">⚠ {w}</p>)}
    </Section>
  )
}
