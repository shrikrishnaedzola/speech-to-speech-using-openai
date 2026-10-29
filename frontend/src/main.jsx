import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Loaded only when a report is opened (keeps charts out of the tester's bundle).
const ReportPage = lazy(() => import('./components/report/ReportPage.jsx'))

// "/?report=12" opens the post-call report for call 12 (in a new tab); anything else is the tester.
const reportId = new URLSearchParams(window.location.search).get('report')

ReactDOM.createRoot(document.getElementById('root')).render(
  reportId ? (
    <Suspense fallback={<p className="p-6 text-sm text-slate-600">Loading report…</p>}>
      <ReportPage callId={reportId} />
    </Suspense>
  ) : (
    <App />
  ),
)
