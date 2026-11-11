import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { playTone, resetToneForTests } from '../tone';

class FakeAudioParam {
  value = 0;
  events: { type: string; value: number; time: number }[] = [];
  setValueAtTime = (value: number, time: number) => this.events.push({ type: 'set', value, time });
  linearRampToValueAtTime = (value: number, time: number) =>
    this.events.push({ type: 'ramp', value, time });
  exponentialRampToValueAtTime = (value: number, time: number) =>
    this.events.push({ type: 'exp', value, time });
}

class FakeNode {
  connect = vi.fn();
  disconnect = vi.fn();
  gain = new FakeAudioParam();
  frequency = new FakeAudioParam();
  type = '';
  startedAt: number | null = null;
  stoppedAt: number | null = null;
  start = (at: number) => {
    this.startedAt = at;
  };
  stop = (at: number) => {
    this.stoppedAt = at;
  };
}

class FakeAudioContext {
  static instances: FakeAudioContext[] = [];
  state = 'running';
  currentTime = 1;
  destination = {};
  oscillators: FakeNode[] = [];
  gains: FakeNode[] = [];
  resume = vi.fn(() => Promise.resolve());

  constructor() {
    FakeAudioContext.instances.push(this);
  }

  createOscillator() {
    const node = new FakeNode();
    this.oscillators.push(node);
    return node;
  }

  createGain() {
    const node = new FakeNode();
    this.gains.push(node);
    return node;
  }
}

describe('playTone', () => {
  beforeEach(() => {
    FakeAudioContext.instances = [];
    resetToneForTests();
    vi.stubGlobal('AudioContext', FakeAudioContext);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('[driver_ui.AC-07] plays an 880 Hz oscillator for no more than 0.5 s, generated with Web Audio', () => {
    playTone();

    const context = FakeAudioContext.instances[0] as FakeAudioContext;
    const oscillator = context.oscillators[0] as FakeNode;
    expect(oscillator.frequency.value).toBe(880);
    expect(oscillator.startedAt).toBe(1);
    expect((oscillator.stoppedAt as number) - 1).toBeLessThanOrEqual(0.5);
    expect((context.gains[0] as FakeNode).gain.events.length).toBeGreaterThan(0);
  });

  it('[driver_ui.AC-07] reuses one AudioContext and resumes it when suspended', () => {
    playTone();
    const context = FakeAudioContext.instances[0] as FakeAudioContext;
    context.state = 'suspended';

    playTone();

    expect(FakeAudioContext.instances).toHaveLength(1);
    expect(context.resume).toHaveBeenCalledTimes(1);
    expect(context.oscillators).toHaveLength(2);
  });

  it('[driver_ui.AC-07] does nothing without Web Audio', () => {
    vi.stubGlobal('AudioContext', undefined);

    expect(() => playTone()).not.toThrow();
  });
});
