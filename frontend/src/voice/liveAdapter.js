// GPT-Live adapter.
//
// Events used (docs: Managing GPT-Live sessions, Delegation and tools):
//   session.started                     -> session is ready (do NOT send session.start over WebRTC)
//   session.input_transcript.delta      -> caller transcript fragment
//   session.output_transcript.delta     -> agent transcript fragment
//   session.usage.updated               -> cumulative billed voice seconds (usage.seconds)
//   response.event                      -> envelope for delegated Responses events;
//        inner response.output_item.done with item.type "function_call" = a tool call
//   error, session.closed
// Tool results go back as response.item.create (function_call_output) + response.create.
// https://developers.openai.com/api/docs/guides/live-conversations
// https://developers.openai.com/api/docs/guides/live-delegation
import { connectWebRTC, newEventId } from './webrtc.js'

export async function startLiveCall({ callId, emit, runTool, phoneMode }) {
  const conn = await connectWebRTC(callId, { phoneMode })
  let resolveClosed
  const closed = new Promise((r) => (resolveClosed = r))

  async function handleFunctionCall(item) {
    let args = {}
    try {
      args = JSON.parse(item.arguments || '{}')
    } catch {
      /* leave args empty; backend returns an error the agent can read */
    }
    const output = await runTool(item.name, args)
    conn.send({
      type: 'response.item.create',
      event_id: newEventId('tool_result'),
      item: { type: 'function_call_output', call_id: item.call_id, output },
    })
    // Appending the result alone does not resume the backend.
    conn.send({ type: 'response.create', event_id: newEventId('continue') })
  }

  conn.dc.onmessage = (msg) => {
    const ev = JSON.parse(msg.data)
    emit({ type: 'raw', event: ev })
    switch (ev.type) {
      case 'session.started':
        emit({ type: 'status', status: 'listening' })
        break
      case 'session.input_transcript.delta':
        emit({ type: 'transcript', role: 'caller', text: ev.delta, append: true })
        break
      case 'session.output_transcript.delta':
        emit({ type: 'transcript', role: 'agent', text: ev.delta, append: true })
        break
      case 'session.usage.updated':
        emit({ type: 'usage', seconds: ev.usage?.seconds })
        break
      case 'response.event': {
        const inner = ev.event
        if (inner?.type === 'response.output_item.done' && inner.item?.type === 'function_call') {
          handleFunctionCall(inner.item)
        }
        break
      }
      case 'error':
        emit({ type: 'error', message: `${ev.error?.code || ''} ${ev.error?.message || ''}`.trim() })
        break
      case 'session.closed':
        if (ev.usage?.seconds != null) emit({ type: 'usage', seconds: ev.usage.seconds })
        resolveClosed()
        break
      default:
        break
    }
  }
  conn.dc.onclose = () => resolveClosed()

  return {
    micStream: conn.mic,
    remoteStream: conn.remoteStream,
    setMuted(muted) {
      conn.mic.getAudioTracks().forEach((t) => (t.enabled = !muted))
      conn.send({ type: muted ? 'session.input_audio.mute' : 'session.input_audio.unmute', event_id: newEventId('mute') })
    },
    async stop() {
      // Graceful close: send session.close and wait for session.closed (max 3s).
      conn.send({ type: 'session.close' })
      await Promise.race([closed, new Promise((r) => setTimeout(r, 3000))])
      conn.close()
    },
  }
}
