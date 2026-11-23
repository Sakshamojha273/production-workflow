import { FormEvent, useState } from 'react';
import { ExternalLink, Globe2, Search } from 'lucide-react';
import { api } from '../services/api';

interface SearchResult {
  position?: number;
  site_name?: string;
  title?: string;
  snippet?: string;
  url?: string;
  date?: string;
}

interface SearchResponse {
  results: SearchResult[];
  total_results?: number;
  page?: number;
}

export function WebSearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [totalResults, setTotalResults] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);
    setTotalResults(null);

    try {
      const response = await api.searchWeb(query.trim()) as SearchResponse;
      setResults(Array.isArray(response.results) ? response.results : []);
      setTotalResults(typeof response.total_results === 'number' ? response.total_results : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to search the web.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-primary-100 p-3 text-primary-700">
          <Globe2 className="h-6 w-6" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Web Search</h1>
          <p className="text-secondary-500">Live web results powered by TinyFish Search</p>
        </div>
      </div>

      <form className="card space-y-4 p-5" onSubmit={handleSubmit}>
        <label className="label" htmlFor="web-search-query">What would you like to find?</label>
        <input
          id="web-search-query"
          className="input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search the web, for example: weather in New York"
          maxLength={2000}
          required
          disabled={loading}
        />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-secondary-500">
            TinyFish Search daily allowances and account rate limits apply.
          </p>
          <button type="submit" className="btn-primary shrink-0" disabled={loading || !query.trim()}>
            <Search className="h-4 w-4" aria-hidden="true" />
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>

      {error && <div className="card border-danger-200 bg-danger-50 p-4 text-sm text-danger-700" role="alert">{error}</div>}

      {results.length > 0 && (
        <section className="space-y-3" aria-labelledby="web-search-results-title">
          <div className="flex items-center justify-between">
            <h2 id="web-search-results-title" className="text-lg font-semibold text-secondary-900">Search results</h2>
            {totalResults !== null && <span className="text-sm text-secondary-500">{totalResults} results</span>}
          </div>
          {results.map((result, index) => (
            <article key={result.url || `${result.title || 'result'}-${index}`} className="card p-5">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-secondary-500">
                {typeof result.position === 'number' && <span>#{result.position}</span>}
                {result.site_name && <span>{result.site_name}</span>}
                {result.date && <span>{result.date}</span>}
              </div>
              {result.url && /^https?:\/\//i.test(result.url) ? (
                <a
                  className="inline-flex items-center gap-2 text-lg font-semibold text-primary-700 hover:underline"
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {result.title || result.url}
                  <ExternalLink className="h-4 w-4 shrink-0" aria-hidden="true" />
                </a>
              ) : (
                <h3 className="text-lg font-semibold text-secondary-900">{result.title || 'Search result'}</h3>
              )}
              {result.snippet && <p className="mt-2 text-sm leading-6 text-secondary-600">{result.snippet}</p>}
            </article>
          ))}
        </section>
      )}

      {!loading && totalResults === 0 && (
        <p className="text-sm text-secondary-500" role="status">No results found. Try a different query.</p>
      )}
    </div>
  );
}
