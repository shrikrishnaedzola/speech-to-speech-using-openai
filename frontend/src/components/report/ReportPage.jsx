// Post-call report page. Opened in a new tab from the tester: /?report=<call_id>
import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import AccuracySection from './AccuracySection.jsx'
import AiSummarySection from './AiSummarySection.jsx'
import CostSection from './CostSection.jsx'
import IssuesSection from './IssuesSection.jsx'
import LanguageSection from './LanguageSection.jsx'
import LatencySection from './LatencySection.jsx'
import MishearingsSection from './MishearingsSection.jsx'
import SummarySection from './SummarySection.jsx'
import TranscriptSection from './TranscriptSection.jsx'
import VoiceQualitySection from './VoiceQualitySection.jsx'

const NAV = [
  ['summary', 'Summary'], ['transcript', 'Transcript'], ['mishearings', 'Mishearings'],
  ['voice_quality', 'Voice'], ['latency', 'Latency'], ['language', 'Language'],
  ['accuracy', 'Accuracy'], ['cost', 'Cost'], ['issues', 'Issues'], ['ai_summary', 'AI summary'],
]

export default function ReportPage({ callId }) {
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null) // 'regenerate' | 'ratings' | 'ai' | null

  useEffect(() => {
    api.getReport(callId).then(setReport).catch((e) => setError(e.message))
  }, [callId])

  useEffect(() => {
    if (report) document.title = `Report - ${report.call.provider} ${report.call.model} - call ${report.call.call_id}`
  }, [report])

  async function run(kind, action) {
    setBusy(kind)
    setError(null)
    try {
      setReport(await action())
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  const banner = (
    <div className="sticky top-0 z-10 bg-amber-400 px-4 py-1.5 text-center text-sm font-bold text-amber-950">
      TEST MODE - dummy data only
    </div>
  )

  if (!report) {
    return (
      <div className="min-h-screen bg-slate-100">
        {banner}
        <p className="p-6 text-sm text-slate-600">{error ? <span className="text-red-700">Could not load report: {error}</span> : 'Loading report…'}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-100">
      {banner}
      <header className="mx-auto max-w-5xl px-4 pt-5">
        <h1 className="text-2xl font-bold text-slate-900">
          Post-call report · {report.call.provider} / {report.call.model} / {report.call.language}
        </h1>
        <p className="text-sm text-slate-500">
          Call {report.call.call_id} · {report.call.form_name || 'form'} · generated {report.generated_at.replace('T', ' ').slice(0, 19)} UTC
        </p>

        {report.pii.found && (
          <div className="mt-3 rounded-lg border border-red-400 bg-red-50 p-3 text-sm text-red-800">
            ⚠ {report.pii.warnings.length} number(s) that look like phone or Aadhaar numbers were found and masked
            ({report.pii.warnings.map((w) => w.where).join('; ')}). Use dummy data only.
          </div>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          {['pdf', 'md', 'json'].map((f) => (
            <a key={f} href={api.reportExportUrl(callId, f)}
              className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Download {f === 'md' ? 'Markdown' : f.toUpperCase()}
            </a>
          ))}
          <button
            onClick={() => run('regenerate', () => api.generateReport(callId))}
            disabled={!!busy}
            className="rounded border border-blue-400 bg-white px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50"
            title="Rebuild the report after adding Correct/Wrong marks or expected values in the tester"
          >
            {busy === 'regenerate' ? 'Regenerating…' : 'Regenerate report'}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-700">{error}</p>}

        <nav className="mt-4 flex flex-wrap gap-1 text-xs">
          {NAV.map(([id, label], i) => (
            <a key={id} href={`#${id}`} className="rounded-full bg-white px-2.5 py-1 text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50">
              {i + 1}. {label}
            </a>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-5xl space-y-4 px-4 py-4">
        <SummarySection report={report} />
        <TranscriptSection transcript={report.transcript} />
        <MishearingsSection data={report.mishearings} />
        <VoiceQualitySection
          data={report.voice_quality}
          codeMixing={report.language.code_mixing_rating}
          saving={busy === 'ratings'}
          onSaveRatings={(ratings) => run('ratings', () => api.saveRatings(callId, ratings))}
        />
        <LatencySection data={report.latency} />
        <LanguageSection data={report.language} />
        <AccuracySection data={report.accuracy} />
        <CostSection data={report.cost} />
        <IssuesSection issues={report.issues} />
        <AiSummarySection
          summary={report.ai_summary}
          busy={busy === 'ai'}
          onGenerate={() => run('ai', () => api.generateReport(callId, true))}
        />
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-8 text-xs text-slate-500">
        <b>TEST MODE - dummy data only.</b> {report.footer} · schema {report.schema_version}
      </footer>
    </div>
  )
}
