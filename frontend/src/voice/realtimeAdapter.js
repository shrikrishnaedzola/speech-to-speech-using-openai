// gpt-realtime-2.1 adapter (Realtime API over WebRTC).
//
// Events used (docs: Realtime function calling):
//   conversation.item.input_audio_transcription.completed -> caller transcript
//   response.output_audio_transcript.delta                -> agent transcript fragment
//   response.done -> response.output[] items with type "function_call" are tool calls
// Tool results go back as conversation.item.create (function_call_output), then response.create.
// https://developers.openai.com/api/docs/guides/realtime-function-calling
import { connectWebRTC, newEventId } from './webrtc.js'

export async function startRealtimeCall({ callId, emit, runTool, phoneMode }) {
  const conn = await connectWebRTC(callId, { phoneMode })

  const onOpen = () => {
    emit({ type: 'status', status: 'listening' })
    // Ask the agent to speak first (greeting).
    conn.send({ type: 'response.create', event_id: newEventId('greet') })
  }
  if (conn.dc.readyState === 'open') onOpen()
  else conn.dc.onopen = onOpen

  async function handleResponseDone(response) {
    const calls = (response?.output || []).filter((item) => item.type === 'function_call')
    if (calls.length === 0) return
    for (const item of calls) {
      let args = {}
      try {
        args = JSON.parse(item.arguments || '{}')
      } catch {
        /* backend returns an error the agent can read */
      }
      const output = await runTool(item.name, args)
      conn.send({
        type: 'conversation.item.create',
        event_id: newEventId('tool_result'),
        item: { type: 'function_call_output', call_id: item.call_id, output },
      })
    }
    conn.send({ type: 'response.create', event_id: newEventId('continue') })
  }

  conn.dc.onmessage = (msg) => {
    const ev = JSON.parse(msg.data)
    emit({ type: 'raw', event: ev })
    switch (ev.type) {
      case 'conversation.item.input_audio_transcription.completed':
        emit({ type: 'transcript', role: 'caller', text: ev.transcript, append: false, key: ev.item_id })
        break
      case 'response.output_audio_transcript.delta':
        emit({ type: 'transcript', role: 'agent', text: ev.delta, append: true, key: ev.item_id })
        break
      case 'response.done':
        handleResponseDone(ev.response)
        break
      case 'error':
        emit({ type: 'error', message: `${ev.error?.code || ''} ${ev.error?.message || ''}`.trim() })
        break
      default:
        break
    }
  }

  return {
    micStream: conn.mic,
    remoteStream: conn.remoteStream,
    setMuted(muted) {
      conn.mic.getAudioTracks().forEach((t) => (t.enabled = !muted))
    },
    async stop() {
      conn.close()
    },
  }
}
