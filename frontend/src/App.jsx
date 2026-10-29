// Main screen: holds call state and wires the voice adapter to the three panels.
import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { TurnTracker } from './voice/audioMeter.js'
import { startLiveCall } from './voice/liveAdapter.js'
import { startRealtimeCall } from './voice/realtimeAdapter.js'
import { startSimulatedCall } from './simulate/simulator.js'
import { startAgentRecorder } from './voice/recorder.js'
import TestBanner from './components/TestBanner.jsx'
import CallPanel from './components/CallPanel.jsx'
import FormPanel from './components/FormPanel.jsx'
import MetricsPanel from './components/MetricsPanel.jsx'

const ADAPTERS = { live: startLiveCall, realtime: startRealtimeCall, simulate: startSimulatedCall }
const MAX_RAW_EVENTS = 500

// Add a transcript fragment: append to the matching bubble, or start a new one.
function mergeTranscript(prev, ev) {
  const key = ev.role + (ev.key ? `:${ev.key}` : '')
  if (ev.append) {
    // Look back a few bubbles: with Realtime, the caller's transcript can arrive
    // after the agent has already started its reply.
    const lookBack = ev.key ? 5 : 1
    for (let i = prev.length - 1; i >= Math.max(0, prev.length - lookBack); i--) {
      if (prev[i].key === key) {
        const next = [...prev]
        next[i] = { ...prev[i], text: prev[i].text + ev.text }
        return next
      }
    }
  }
  return [...prev, { key, role: ev.role, text: ev.text, ts: new Date() }]
}

export default function App() {
  const [config, setConfig] = useState(null)
  const [forms, setForms] = useState([])
  const [settings, setSettings] = useState({
    formId: '', mode: 'live', language: 'English', voice: 'marin', ratePerMin: 0.05, delegateModel: '',
    audioMode: 'normal', recordAudio: true,
  })
  const [activeMode, setActiveMode] = useState(null) // mode of the current/last call
  const [callId, setCallId] = useState(null)
  const [status, setStatus] = useState('idle')
  const [muted, setMuted] = useState(false)
  const [transcript, setTranscript] = useState([])
  const [report, setReport] = useState(null)
  const [rawEvents, setRawEvents] = useState([])
  const [errors, setErrors] = useState([])
  const [interruptions, setInterruptions] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [usageSeconds, setUsageSeconds] = useState(null)
  const [reportReady, setReportReady] = useState(false)

  // Refs hold values that event callbacks need without re-rendering.
  const callIdRef = useRef(null)
  const controllerRef = useRef(null)
  const trackerRef = useRef(null)
  const timerRef = useRef(null)
  const startTimeRef = useRef(0)
  const endingRef = useRef(false)
  const transcriptRef = useRef([])
  const interruptionsRef = useRef(0)
  const usageRef = useRef(null)
  // For the post-call report: browser time zero, timeline events, agent audio recorder.
  const clientStartedAtRef = useRef(null)
  const eventsRef = useRef([])
  const recorderRef = useRef(null)

  // ms since the call connected (0 before that)
  const sinceStart = () => (startTimeRef.current ? Math.round(performance.now() - startTimeRef.current) : 0)

  useEffect(() => {
    transcriptRef.current = transcript
  }, [transcript])

  // Load dropdown options once.
  useEffect(() => {
    Promise.all([api.config(), api.forms()])
      .then(([cfg, formList]) => {
        setConfig(cfg)
        setForms(formList)
        setSettings((s) => ({
          ...s,
          formId: formList[0]?.id || '',
          ratePerMin: cfg.cost_per_min.live,
          delegateModel: cfg.models.find((m) => m.mode === 'live')?.delegate_model || '',
        }))
      })
      .catch((err) => addError(`Backend not reachable: ${err.message}`))
  }, [])

  function addError(message) {
    setErrors((prev) => [...prev, { ts: new Date(), message }])
  }

  async function refresh() {
    if (!callIdRef.current) return
    try {
      setReport(await api.getCall(callIdRef.current))
    } catch (err) {
      addError(err.message)
    }
  }

  // Called by the adapters when the model asks for a tool. Returns the output string for the model.
  async function runTool(name, args) {
    try {
      const res = await api.runTool(callIdRef.current, name, args)
      refresh()
      return res.output
    } catch (err) {
      addError(`Tool ${name} failed: ${err.message}`)
      return JSON.stringify({ ok: false, error: 'Server error, please continue with the next question.' })
    }
  }

  async function recordTurn(latencyMs) {
    if (!callIdRef.current || endingRef.current) return
    try {
      await api.addTurn(callIdRef.current, Math.round(latencyMs), sinceStart())
      refresh()
    } catch (err) {
      addError(err.message)
    }
  }

  function bumpInterruptions() {
    eventsRef.current.push({ type: 'barge_in', ts_ms: sinceStart() })
    interruptionsRef.current += 1
    setInterruptions(interruptionsRef.current)
  }

  function setAgentSpeaking(speaking) {
    if (!endingRef.current) setStatus(speaking ? 'speaking' : 'listening')
  }

  // One place that handles every normalized event from the adapters.
  function handleEvent(ev) {
    switch (ev.type) {
      case 'raw':
        setRawEvents((prev) => [...prev.slice(-(MAX_RAW_EVENTS - 1)), { ts: new Date(), event: ev.event }])
        break
      case 'status':
        if (!endingRef.current) setStatus(ev.status)
        break
      case 'transcript':
        if (ev.text) setTranscript((prev) => mergeTranscript(prev, ev))
        break
      case 'usage':
        if (ev.seconds != null) {
          usageRef.current = ev.seconds
          setUsageSeconds(ev.seconds)
        }
        break
      case 'error':
        addError(ev.message)
        break
      case 'agentSpeaking':
        setAgentSpeaking(ev.value)
        break
      case 'turn':
        recordTurn(ev.latency_ms)
        break
      case 'bargein':
        bumpInterruptions()
        break
      case 'simulationDone':
        endCall()
        break
      default:
        break
    }
  }

  async function startCall(mode) {
    // Reset everything from the previous call.
    endingRef.current = false
    interruptionsRef.current = 0
    usageRef.current = null
    eventsRef.current = []
    recorderRef.current = null
    setReportReady(false)
    setTranscript([])
    setRawEvents([])
    setErrors([])
    setInterruptions(0)
    setUsageSeconds(null)
    setElapsed(0)
    setMuted(false)
    setReport(null)
    setActiveMode(mode)
    setStatus('connecting')

    try {
      const call = await api.createCall({
        form_id: settings.formId,
        mode,
        language: settings.language,
        voice: settings.voice,
        delegate_model: mode === 'live' ? settings.delegateModel || null : null,
        cost_rate_per_min: mode === 'simulate' ? 0 : Number(settings.ratePerMin),
        audio_mode: settings.audioMode,
      })
      callIdRef.current = call.call_id
      setCallId(call.call_id)
      await refresh()

      const controller = await ADAPTERS[mode]({
        callId: call.call_id, emit: handleEvent, runTool, phoneMode: settings.audioMode === 'phone_8khz',
      })
      controllerRef.current = controller
      startTimeRef.current = performance.now()
      clientStartedAtRef.current = new Date().toISOString()
      timerRef.current = setInterval(() => setElapsed((performance.now() - startTimeRef.current) / 1000), 500)

      if (mode !== 'simulate') {
        const tracker = new TurnTracker({
          onTurn: recordTurn,
          onBargeIn: bumpInterruptions,
          onAgentSpeaking: setAgentSpeaking,
        })
        trackerRef.current = tracker
        const remote = await controller.remoteStream
        tracker.start(controller.micStream, remote)
        if (settings.recordAudio) recorderRef.current = startAgentRecorder(remote)
      }
    } catch (err) {
      addError(`Could not start call: ${err.message}`)
      await endCall(true)
    }
  }

  async function endCall(failed = false) {
    if (endingRef.current) return
    endingRef.current = true
    trackerRef.current?.stop()
    trackerRef.current = null
    clearInterval(timerRef.current)
    // Stop the agent-audio recorder before the connection closes; WAV conversion runs in the background.
    const wavPromise = recorderRef.current?.stopAsWav().catch((err) => addError(`Recording failed: ${err.message}`))
    recorderRef.current = null
    try {
      await controllerRef.current?.stop()
    } catch (err) {
      addError(err.message)
    }
    controllerRef.current = null
    const duration = startTimeRef.current ? (performance.now() - startTimeRef.current) / 1000 : 0
    startTimeRef.current = 0
    setStatus(failed ? 'failed' : 'ended')
    if (!callIdRef.current) return
    try {
      const finalReport = await api.endCall(callIdRef.current, {
        duration_s: Math.round(duration * 10) / 10,
        interruptions: interruptionsRef.current,
        usage_seconds: usageRef.current,
        transcript: transcriptRef.current.map((t) => ({ role: t.role, text: t.text, ts: t.ts.toISOString() })),
        failed,
        client_started_at: clientStartedAtRef.current,
        events: eventsRef.current,
      })
      setReport(finalReport)
      setReportReady(Boolean(finalReport.report_ready))
      // Upload the agent's voice (for the optional MOS score); the backend refreshes the report.
      const wav = await wavPromise
      if (wav) await api.uploadAudio(callIdRef.current, wav)
    } catch (err) {
      addError(err.message)
    }
  }

  function toggleMute() {
    const next = !muted
    controllerRef.current?.setMuted(next)
    setMuted(next)
  }

  async function saveReview(fieldId, mark, expectedValue) {
    try {
      setReport(await api.review(callId, { field_id: fieldId, mark, expected_value: expectedValue || null }))
    } catch (err) {
      addError(err.message)
    }
  }

  const inCall = ['connecting', 'listening', 'speaking'].includes(status)

  return (
    <div className="min-h-screen">
      <TestBanner apiKeyConfigured={config?.api_key_configured} />
      <main className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-3">
        <CallPanel
          config={config}
          forms={forms}
          settings={settings}
          setSettings={setSettings}
          status={status}
          inCall={inCall}
          muted={muted}
          transcript={transcript}
          onStart={() => startCall(settings.mode)}
          onSimulate={() => startCall('simulate')}
          onEnd={() => endCall()}
          onMute={toggleMute}
          reportCallId={reportReady ? callId : null}
        />
        <FormPanel report={report} callId={callId} onReview={saveReview} />
        <MetricsPanel
          report={report}
          mode={activeMode}
          inCall={inCall}
          elapsed={elapsed}
          interruptions={interruptions}
          usageSeconds={usageSeconds}
          ratePerMin={activeMode === 'simulate' ? 0 : Number(settings.ratePerMin)}
          liveInitSeconds={config?.live_init_seconds ?? 15}
          rawEvents={rawEvents}
          errors={errors}
        />
      </main>
    </div>
  )
}
