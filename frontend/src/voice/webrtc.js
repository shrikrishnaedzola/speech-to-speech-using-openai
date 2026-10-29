// Shared WebRTC setup for both models.
//
// Flow (OpenAI WebRTC guide, server-side SDP exchange):
//   1. Browser creates an SDP offer with the mic track + "oai-events" data channel.
//   2. Our backend posts the offer to OpenAI with the API key and returns the SDP answer.
//   3. Browser applies the answer. Audio flows on media tracks, JSON events on the data channel.
// https://developers.openai.com/api/docs/guides/realtime-webrtc
//
// Phone mode (audio_mode "phone_8khz"): both directions go through an 8 kHz
// AudioContext with a 300 Hz high-pass, to sound like a phone line.
import { api } from '../api.js'

function phoneLine(ctx, source) {
  const highPass = ctx.createBiquadFilter()
  highPass.type = 'highpass'
  highPass.frequency.value = 300 // phone band is ~300-3400 Hz; 8 kHz sampling cuts above 4 kHz
  source.connect(highPass)
  return highPass
}

export async function connectWebRTC(callId, { phoneMode = false } = {}) {
  const pc = new RTCPeerConnection()
  const phoneCtx = phoneMode ? new AudioContext({ sampleRate: 8000 }) : null

  // Agent audio: play it, and hand the stream to the audio meter.
  const audioEl = new Audio()
  audioEl.autoplay = true
  // Chrome only feeds a remote stream into Web Audio while a media element plays it,
  // so in phone mode the element stays attached but muted.
  audioEl.muted = phoneMode
  const remoteStream = new Promise((resolve) => {
    pc.ontrack = (e) => {
      audioEl.srcObject = e.streams[0]
      if (phoneCtx) phoneLine(phoneCtx, phoneCtx.createMediaStreamSource(e.streams[0])).connect(phoneCtx.destination)
      resolve(e.streams[0])
    }
  })

  // Echo cancellation matters: without it the agent's voice leaks into the mic
  // and looks like a barge-in. Headphones are still recommended.
  const mic = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  })
  let sendTrack = mic.getAudioTracks()[0]
  if (phoneCtx) {
    const dest = phoneCtx.createMediaStreamDestination()
    phoneLine(phoneCtx, phoneCtx.createMediaStreamSource(mic)).connect(dest)
    sendTrack = dest.stream.getAudioTracks()[0]
  }
  pc.addTrack(sendTrack, mic)

  const dc = pc.createDataChannel('oai-events')

  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)
  let answer
  try {
    answer = await api.createSession(callId, offer.sdp)
  } catch (err) {
    mic.getTracks().forEach((t) => t.stop())
    pc.close()
    phoneCtx?.close()
    throw err
  }
  await pc.setRemoteDescription({ type: 'answer', sdp: answer.sdp })

  const close = () => {
    mic.getTracks().forEach((t) => t.stop())
    sendTrack.stop()
    pc.close()
    phoneCtx?.close()
    audioEl.srcObject = null
  }
  const send = (event) => {
    if (dc.readyState === 'open') dc.send(JSON.stringify(event))
  }

  return { pc, dc, mic, remoteStream, send, close, openaiSessionId: answer.openai_session_id }
}

let eventCounter = 0
export const newEventId = (prefix) => `${prefix}_${Date.now()}_${++eventCounter}`
