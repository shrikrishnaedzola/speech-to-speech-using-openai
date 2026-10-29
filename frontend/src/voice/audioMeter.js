// Measures response time and barge-ins from audio levels in the browser.
//
// Why not server events? GPT-Live does not document speech-start/stop events,
// so we measure the same way for both models: watch the mic level (caller)
// and the remote audio level (agent).
//
//   response time = first agent audio  -  moment the caller's voice stopped
//   barge-in      = caller starts speaking while the agent is speaking

const TICK_MS = 30
const CALLER_LEVEL = 0.02 // RMS above this = caller voice
const AGENT_LEVEL = 0.01 // RMS above this = agent audio
const CALLER_START_MS = 150 // voice must last this long to count as speech
const CALLER_SILENCE_MS = 700 // silence this long = caller finished
const AGENT_SILENCE_MS = 500 // silence this long = agent finished

function levelReader(audioCtx, stream) {
  const source = audioCtx.createMediaStreamSource(stream)
  const analyser = audioCtx.createAnalyser()
  analyser.fftSize = 512
  source.connect(analyser) // not connected to speakers: the <audio> element plays it
  const buf = new Float32Array(analyser.fftSize)
  return () => {
    analyser.getFloatTimeDomainData(buf)
    let sum = 0
    for (const v of buf) sum += v * v
    return Math.sqrt(sum / buf.length)
  }
}

export class TurnTracker {
  constructor({ onTurn, onBargeIn, onAgentSpeaking, onCallerSpeaking }) {
    this.cb = { onTurn, onBargeIn, onAgentSpeaking, onCallerSpeaking }
    this.callerSpeaking = false
    this.agentSpeaking = false
    this.callerAboveSince = null
    this.lastCallerVoice = 0
    this.lastAgentAudio = 0
    this.callerStoppedAt = null // set when the caller finished and we wait for the agent
  }

  start(micStream, remoteStream) {
    this.audioCtx = new AudioContext()
    this.readMic = levelReader(this.audioCtx, micStream)
    this.readAgent = levelReader(this.audioCtx, remoteStream)
    this.timer = setInterval(() => this.tick(), TICK_MS)
  }

  stop() {
    clearInterval(this.timer)
    this.audioCtx?.close()
  }

  tick() {
    const now = performance.now()
    this.updateCaller(now, this.readMic())
    this.updateAgent(now, this.readAgent())
  }

  updateCaller(now, level) {
    if (level > CALLER_LEVEL) {
      this.lastCallerVoice = now
      if (this.callerAboveSince === null) this.callerAboveSince = now
      if (!this.callerSpeaking && now - this.callerAboveSince >= CALLER_START_MS) {
        this.callerSpeaking = true
        this.callerStoppedAt = null
        this.cb.onCallerSpeaking?.(true)
        if (this.agentSpeaking) this.cb.onBargeIn?.()
      }
    } else {
      this.callerAboveSince = null
      if (this.callerSpeaking && now - this.lastCallerVoice >= CALLER_SILENCE_MS) {
        this.callerSpeaking = false
        this.callerStoppedAt = this.lastCallerVoice // when the voice actually ended
        this.cb.onCallerSpeaking?.(false)
      }
    }
  }

  updateAgent(now, level) {
    if (level > AGENT_LEVEL) {
      this.lastAgentAudio = now
      if (!this.agentSpeaking) {
        this.agentSpeaking = true
        this.cb.onAgentSpeaking?.(true)
        // The agent may answer before our 700ms silence window closes.
        if (this.callerStoppedAt === null && this.callerSpeaking && now - this.lastCallerVoice >= CALLER_START_MS) {
          this.callerSpeaking = false
          this.callerStoppedAt = this.lastCallerVoice
          this.cb.onCallerSpeaking?.(false)
        }
        if (this.callerStoppedAt !== null) {
          this.cb.onTurn?.(now - this.callerStoppedAt)
          this.callerStoppedAt = null
        }
      }
    } else if (this.agentSpeaking && now - this.lastAgentAudio >= AGENT_SILENCE_MS) {
      this.agentSpeaking = false
      this.cb.onAgentSpeaking?.(false)
    }
  }
}
