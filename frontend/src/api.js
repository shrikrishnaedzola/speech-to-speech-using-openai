// Small fetch wrappers for the FastAPI backend. All calls go to /api (proxied by Vite).

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      message = (await res.json()).detail || message
    } catch {
      /* body was not JSON */
    }
    throw new Error(message)
  }
  return res.json()
}

export const api = {
  config: () => request('/config'),
  forms: () => request('/forms'),
  createCall: (body) => request('/calls', { method: 'POST', body }),
  // Sends our SDP offer; the backend talks to OpenAI with the key and returns the SDP answer.
  createSession: (callId, sdp) => request('/session', { method: 'POST', body: { call_id: callId, sdp } }),
  runTool: (callId, name, args) =>
    request(`/tools/${name}`, { method: 'POST', body: { call_id: callId, arguments: args } }),
  getCall: (callId) => request(`/calls/${callId}`),
  addTurn: (callId, latencyMs, tsMs) =>
    request(`/calls/${callId}/turns`, { method: 'POST', body: { latency_ms: latencyMs, ts_ms: tsMs } }),
  endCall: (callId, body) => request(`/calls/${callId}/end`, { method: 'POST', body }),
  review: (callId, body) => request(`/calls/${callId}/review`, { method: 'POST', body }),
  exportUrl: (callId, format) => `/api/calls/${callId}/export?format=${format}`,

  // Agent voice recording (WAV blob) for the optional MOS score.
  uploadAudio: async (callId, wavBlob) => {
    const res = await fetch(`/api/calls/${callId}/audio`, { method: 'POST', body: wavBlob, headers: { 'Content-Type': 'audio/wav' } })
    if (!res.ok) throw new Error(`Audio upload failed: ${res.status}`)
    return res.json()
  },

  // Post-call report (shared report_module)
  getReport: (callId) => request(`/calls/${callId}/report`),
  generateReport: (callId, aiSummary = false) =>
    request(`/calls/${callId}/report?ai_summary=${aiSummary}`, { method: 'POST' }),
  saveRatings: (callId, ratings) => request(`/calls/${callId}/ratings`, { method: 'POST', body: ratings }),
  reportExportUrl: (callId, format) => `/api/calls/${callId}/report/export?format=${format}`,
}
