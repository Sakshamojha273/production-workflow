import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../services/api';

describe('TinyFish API streaming', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('parses research events across streamed chunks', async () => {
    const encoder = new TextEncoder();
    const streamText = [
      `data: ${JSON.stringify({ event: 'created', research_run_id: 'run-1' })}\n\n`,
      `data: ${JSON.stringify({ event: 'final_result', result: 'Cited report', citations: [] })}\n\n`,
      'data: {"event":"done"}\n\n',
    ].join('');
    const splitAt = streamText.indexOf('"final_result"') + 8;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(streamText.slice(0, splitAt)));
        controller.enqueue(encoder.encode(streamText.slice(splitAt)));
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, body } as Response);
    vi.stubGlobal('fetch', fetchMock);
    const events: string[] = [];

    await api.runResearch('Research manufacturing trends', (event) => {
      if (typeof event.event === 'string') events.push(event.event);
    });

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/research',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(events).toEqual(['created', 'final_result', 'done']);
  });
});
