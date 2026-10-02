import '@testing-library/jest-dom/vitest';

// jsdom has no EventSource; the live hooks open one per case. A silent stub is enough for render tests.
class FakeEventSource {
  addEventListener() {}
  close() {}
}
(globalThis as unknown as { EventSource: unknown }).EventSource = FakeEventSource;
