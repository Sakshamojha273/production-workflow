import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../services/api';
import { WebResearchPage } from '../pages/WebResearchPage';

vi.mock('../services/api');

describe('WebResearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('submits a research query and displays the report and citations', async () => {
    vi.mocked(api.runResearch).mockImplementation(async (_query, onEvent) => {
      onEvent({
        event: 'final_result',
        result: 'A source-backed research summary.',
        citations: ['https://example.com/source'],
      });
      onEvent({ event: 'done' });
    });

    render(<WebResearchPage />);
    fireEvent.change(screen.getByLabelText('What would you like to research?'), {
      target: { value: 'Research manufacturing trends' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Start research' }));

    expect(await screen.findByText('A source-backed research summary.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /https:\/\/example.com\/source/ })).toHaveAttribute(
      'href',
      'https://example.com/source',
    );
    expect(api.runResearch).toHaveBeenCalledWith(
      'Research manufacturing trends',
      expect.any(Function),
    );
  });
});
