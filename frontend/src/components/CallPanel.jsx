// Column 1: call settings, call buttons, status and live transcript.
import { useEffect, useRef } from 'react'
import Panel from './Panel.jsx'

const STATUS = {
  idle: { label: 'Idle', color: 'bg-slate-300' },
  connecting: { label: 'Connecting', color: 'bg-amber-400 animate-pulse' },
  listening: { label: 'Listening', color: 'bg-green-500' },
  speaking: { label: 'Agent speaking', color: 'bg-blue-500 animate-pulse' },
  ended: { label: 'Ended', color: 'bg-slate-500' },
  failed: { label: 'Failed', color: 'bg-red-500' },
}

function Select({ label, value, onChange, options, disabled }) {
  return (
    <label className="block text-sm">
      <span className="text-slate-600">{label}</span>
      <select
        className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 disabled:bg-slate-100"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function CallPanel({
  config, forms, settings, setSettings, status, inCall, muted, transcript, onStart, onSimulate, onEnd, onMute,
  reportCallId,
}) {
  const bottomRef = useRef(null)
  // Braces matter: newer browsers return a Promise from scrollIntoView,
  // and React would treat a returned value as a cleanup function.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [transcript])

  const set = (key) => (value) => setSettings((s) => ({ ...s, [key]: value }))
  const voices = config?.voices?.[settings.mode] || []

  function changeMode(mode) {
    setSettings((s) => ({
      ...s,
      mode,
      voice: config.voices[mode].includes(s.voice) ? s.voice : config.voices[mode][0],
      ratePerMin: config.cost_per_min[mode],
    }))
  }

  const statusInfo = STATUS[status] || STATUS.idle

  return (
    <Panel
      title="1. Call & Conversation"
      actions={
        <span className="flex items-center gap-2 text-sm text-slate-700">
          <span className={`h-3 w-3 rounded-full ${statusInfo.color}`} />
          {statusInfo.label}
        </span>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <Select
            label="Form to test"
            value={settings.formId}
            onChange={set('formId')}
            disabled={inCall}
            options={forms.map((f) => ({ value: f.id, label: f.name }))}
          />
        </div>
        <Select
          label="Model"
          value={settings.mode}
          onChange={changeMode}
          disabled={inCall || !config}
          options={(config?.models || []).map((m) => ({ value: m.mode, label: m.model }))}
        />
        <Select
          label="Language"
          value={settings.language}
          onChange={set('language')}
          disabled={inCall}
          options={(config?.languages || []).map((l) => ({ value: l, label: l }))}
        />
        <Select
          label="Voice"
          value={settings.voice}
          onChange={set('voice')}
          disabled={inCall}
          options={voices.map((v) => ({ value: v, label: v }))}
        />
        <label className="block text-sm">
          <span className="text-slate-600">Cost rate (USD/min)</span>
          <input
            type="number"
            step="0.01"
            min="0"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 disabled:bg-slate-100"
            value={settings.ratePerMin}
            onChange={(e) => set('ratePerMin')(e.target.value)}
            disabled={inCall}
          />
        </label>
        <Select
          label="Audio mode"
          value={settings.audioMode}
          onChange={set('audioMode')}
          disabled={inCall}
          options={[
            { value: 'normal', label: 'Normal' },
            { value: 'phone_8khz', label: 'Phone (8 kHz)' },
          ]}
        />
        {/* Hidden when the deployment cannot store audio (e.g. Vercel) */}
        {config?.features?.agent_audio !== false && (
          <label className="flex items-end gap-2 pb-1.5 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={settings.recordAudio}
              onChange={(e) => set('recordAudio')(e.target.checked)}
              disabled={inCall}
            />
            Record agent voice (for MOS)
          </label>
        )}
        {settings.mode === 'live' && (
          <label className="col-span-2 block text-sm">
            <span className="text-slate-600">Delegated tool model (GPT-Live backend)</span>
            <input
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 disabled:bg-slate-100"
              value={settings.delegateModel}
              onChange={(e) => set('delegateModel')(e.target.value)}
              disabled={inCall}
            />
          </label>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          className="rounded bg-green-600 px-4 py-2 font-medium text-white hover:bg-green-700 disabled:opacity-40"
          onClick={onStart}
          disabled={inCall || !settings.formId || !config?.api_key_configured}
        >
          Start Call
        </button>
        <button
          className="rounded bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-700 disabled:opacity-40"
          onClick={onEnd}
          disabled={!inCall}
        >
          End Call
        </button>
        <button
          className="rounded border border-slate-400 px-4 py-2 font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40"
          onClick={onMute}
          disabled={!inCall}
        >
          {muted ? 'Unmute' : 'Mute'}
        </button>
        <button
          className="rounded border border-indigo-400 px-4 py-2 font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-40"
          onClick={onSimulate}
          disabled={inCall || !settings.formId}
          title="Replay a saved sample call through the backend. No mic, no OpenAI cost."
        >
          Simulate
        </button>
      </div>
      {reportCallId && !inCall && (
        <a
          className="block rounded-lg border-2 border-blue-500 bg-blue-50 px-4 py-2 text-center font-medium text-blue-800 hover:bg-blue-100"
          href={`/?report=${reportCallId}`}
          target="_blank"
          rel="noreferrer"
        >
          Report ready - open post-call report ↗
        </a>
      )}
      {settings.mode === 'live' && !inCall && (
        <p className="text-xs text-slate-500">GPT-Live: say "hello" after connecting to start the conversation.</p>
      )}

      <div className="space-y-2">
        {transcript.length === 0 && <p className="text-sm text-slate-400">Transcript will appear here.</p>}
        {transcript.map((t, i) => (
          <div key={i} className={`flex ${t.role === 'agent' ? 'justify-start' : 'justify-end'}`}>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                t.role === 'agent' ? 'bg-blue-50 text-slate-800' : 'bg-green-50 text-slate-800'
              }`}
            >
              <div className="mb-0.5 text-[11px] text-slate-500">
                {t.role === 'agent' ? 'Agent' : 'Caller'} · {t.ts.toLocaleTimeString()}
              </div>
              {t.text}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </Panel>
  )
}
