// Records the AGENT's voice (remote stream only, never the caller's mic) for the
// optional MOS voice-quality score. Dummy test calls only.
//
// After the call the recording is converted to a 16 kHz mono WAV in the browser,
// so the backend does not need ffmpeg.

export function startAgentRecorder(stream) {
  const recorder = new MediaRecorder(stream)
  const chunks = []
  recorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data)
  }
  recorder.start(1000) // a chunk every second, so a dropped call still keeps most audio

  return {
    async stopAsWav() {
      if (recorder.state !== 'inactive') {
        await new Promise((resolve) => {
          recorder.onstop = resolve
          recorder.stop()
        })
      }
      const blob = new Blob(chunks, { type: recorder.mimeType })
      if (!blob.size) return null
      const ctx = new AudioContext()
      const decoded = await ctx.decodeAudioData(await blob.arrayBuffer())
      ctx.close()
      // Resample to 16 kHz mono (what the MOS model expects).
      const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * 16000), 16000)
      const source = offline.createBufferSource()
      source.buffer = decoded
      source.connect(offline.destination)
      source.start()
      const rendered = await offline.startRendering()
      return encodeWav(rendered.getChannelData(0), 16000)
    },
  }
}

// 16-bit PCM WAV file from float samples (-1..1).
function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const write = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)))
  write(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  write(8, 'WAVE')
  write(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate
  view.setUint16(32, 2, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  write(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}
