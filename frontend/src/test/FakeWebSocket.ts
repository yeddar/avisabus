/**
 * WebSocket double for the unit tests (passenger_alert_ui design §5): nothing ever leaves the
 * process. `src/test/setup.ts` installs it as the global WebSocket for every test, so no
 * component can open a real connection by accident. Tests drive the "server" side with
 * `open()`, `receive()` and `serverClose()`.
 */
export class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  /** Every socket created since the last reset, oldest first. */
  static instances: FakeWebSocket[] = [];

  static reset(): void {
    FakeWebSocket.instances = [];
  }

  /** The most recently created socket. */
  static last(): FakeWebSocket {
    const socket = FakeWebSocket.instances.at(-1);
    if (socket === undefined) throw new Error('no WebSocket has been created');
    return socket;
  }

  readonly url: string;
  readyState: number = FakeWebSocket.CONNECTING;
  /** Raw frames sent by the client. */
  readonly sent: string[] = [];
  /** Code passed to close() by the client, if it closed the socket itself. */
  closedByClient: number | null = null;

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string | URL) {
    this.url = String(url);
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    if (this.readyState !== FakeWebSocket.OPEN) {
      throw new DOMException('WebSocket is not open', 'InvalidStateError');
    }
    this.sent.push(data);
  }

  close(code = 1000): void {
    if (this.readyState === FakeWebSocket.CLOSED) return;
    this.closedByClient = code;
    this.finish(code);
  }

  /** Frames sent by the client, parsed as JSON. */
  sentMessages(): unknown[] {
    return this.sent.map((frame) => JSON.parse(frame) as unknown);
  }

  // --- server side, driven by the tests ---

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  /** Delivers a frame: objects are sent as JSON, strings as they are. */
  receive(message: unknown): void {
    const data = typeof message === 'string' ? message : JSON.stringify(message);
    this.onmessage?.(new MessageEvent('message', { data }));
  }

  serverClose(code = 1006): void {
    this.finish(code);
  }

  private finish(code: number): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code }));
  }
}
