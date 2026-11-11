import { createContext, useContext } from 'react'

export interface AlertsState {
  connected: boolean // live push channel is open
  muted: boolean
  setMuted: (muted: boolean) => void
}

export const AlertsContext = createContext<AlertsState>({ connected: false, muted: false, setMuted: () => {} })

export function useAlerts() {
  return useContext(AlertsContext)
}

const MUTE_KEY = 'aicam_alerts_muted'

export function loadMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === '1'
  } catch {
    return false
  }
}

export function saveMuted(muted: boolean) {
  try {
    localStorage.setItem(MUTE_KEY, muted ? '1' : '0')
  } catch {
    // storage unavailable (private mode): the setting just won't persist
  }
}

let audio: AudioContext | null = null

/** Short generated tones, so no sound file is needed. Critical: three rising beeps; warning: one. */
export function playAlertSound(severity: string) {
  const beeps = severity === 'critical' ? [880, 988, 1175] : severity === 'warning' ? [740] : []
  if (!beeps.length) return
  try {
    audio ??= new AudioContext()
    const start = audio.currentTime
    beeps.forEach((freq, i) => {
      const osc = audio!.createOscillator()
      const gain = audio!.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      const t = start + i * 0.18
      gain.gain.setValueAtTime(0.0001, t)
      gain.gain.exponentialRampToValueAtTime(0.25, t + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.15)
      osc.connect(gain).connect(audio!.destination)
      osc.start(t)
      osc.stop(t + 0.16)
    })
  } catch {
    // audio blocked or unsupported: the visual alert still shows
  }
}
