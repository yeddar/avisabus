const FREQUENCY_HZ = 880;
const DURATION_S = 0.3;
const ATTACK_S = 0.02;
const PEAK_GAIN = 0.3;

let context: AudioContext | null = null;

/** Test isolation only: forget the shared AudioContext. */
export function resetToneForTests(): void {
  context = null;
}

/**
 * Short tone for a new request (driver_ui.AC-07, design §1): an 880 Hz oscillator, 300 ms, with a
 * soft envelope. It is generated with Web Audio, so there are no audio files. Without Web Audio
 * or if the browser refuses, the view simply stays silent.
 */
export function playTone(): void {
  if (typeof AudioContext === 'undefined') return;
  try {
    context ??= new AudioContext();
    if (context.state === 'suspended') void context.resume();
    const now = context.currentTime;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.value = FREQUENCY_HZ;
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(PEAK_GAIN, now + ATTACK_S);
    gain.gain.linearRampToValueAtTime(0, now + DURATION_S);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(now);
    oscillator.stop(now + DURATION_S);
  } catch {
    // Web Audio refused (e.g. no audio device): the highlight of the stop still shows the request.
  }
}
