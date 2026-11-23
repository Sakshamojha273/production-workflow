import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../services/api';
import { WebSearchPage } from '../pages/WebSearchPage';

vi.mock('../services/api');

describe('WebSearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('submits a query and displays TinyFish search results', async () => {
    vi.mocked(api.searchWeb).mockResolvedValue({
      query: 'weather',
      total_results: 1,
      page: 0,
      results: [{
        position: 1,
        site_name: 'weather.example',
        title: 'Local forecast',
        snippet: 'Current conditions and forecast.',
        url: 'https://weather.example/',
      }],
    });

    render(<WebSearchPage />);
    fireEvent.change(screen.getByLabelText('What would you like to find?'), {
      target: { value: 'weather' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByRole('link', { name: /Local forecast/ })).toHaveAttribute(
      'href',
      'https://weather.example/',
    );
    expect(screen.getByText('Current conditions and forecast.')).toBeInTheDocument();
    expect(api.searchWeb).toHaveBeenCalledWith('weather');
  });
});
