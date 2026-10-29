// Simulate mode: replays sampleReplay.json without a microphone or OpenAI.
// Tool calls still go to the real backend, so validation and form cards are tested for free.
// It emits the same events as the real adapters, plus "turn" and "bargein"
// (which the audio meter produces in a real call).
import replay from './sampleReplay.json'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function startSimulatedCall({ emit, runTool }) {
  let stopped = false

  async function run() {
    emit({ type: 'status', status: 'listening' })
    for (const step of replay.steps) {
      await sleep(step.delay || 0)
      if (stopped) return
      emit({ type: 'raw', event: { type: `simulate.${step.type}`, ...step } })
      if (step.type === 'say') {
        if (step.role === 'agent') emit({ type: 'agentSpeaking', value: true })
        emit({ type: 'transcript', role: step.role, text: step.text, append: false })
        if (step.role === 'agent') setTimeout(() => emit({ type: 'agentSpeaking', value: false }), 600)
      } else if (step.type === 'tool') {
        await runTool(step.name, step.args)
      } else if (step.type === 'turn') {
        emit({ type: 'turn', latency_ms: step.latency_ms })
      } else if (step.type === 'bargein') {
        emit({ type: 'bargein' })
      }
    }
    emit({ type: 'simulationDone' })
  }
  run()

  return {
    micStream: null,
    remoteStream: null,
    setMuted() {},
    async stop() {
      stopped = true
    },
  }
}
