import { FormEvent, useState } from 'react';
import { ExternalLink, Globe2, Search, Sparkles } from 'lucide-react';
import { api } from '../services/api';

interface Citation {
  url: string;
  title?: string;
}

const progressLabels: Record<string, string> = {
  created: 'Research started',
  plan_updated: 'Planning research questions',
  sources_searching: 'Searching sources',
  sources_searched: 'Reviewing search results',
  sources_fetching: 'Collecting source details',
  source_fetched: 'Source collected',
  synthesis_started: 'Writing the cited report',
};

export function WebResearchPage() {
  const [query, setQuery] = useState('');
  const [report, setReport] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [progress, setProgress] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setReport('');
    setCitations([]);
    setProgress('Connecting to TinyFish...');

    try {
      await api.runResearch(query.trim(), (researchEvent) => {
        if (typeof researchEvent.event === 'string') {
          setProgress(progressLabels[researchEvent.event] || 'Research in progress...');
        }
        if (researchEvent.event === 'final_result') {
          const result = researchEvent.result;
          setReport(typeof result === 'string' ? result : JSON.stringify(result, null, 2));
          const items = Array.isArray(researchEvent.citations) ? researchEvent.citations : [];
          setCitations(items.flatMap((item): Citation[] => {
            if (typeof item === 'string' && /^https?:\/\//i.test(item)) return [{ url: item }];
            if (item && typeof item === 'object' && 'url' in item && typeof item.url === 'string') {
              return [{ url: item.url, title: 'title' in item && typeof item.title === 'string' ? item.title : undefined }];
            }
            return [];
          }));
        }
      });
      setProgress('Research complete');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to complete web research.');
      setProgress('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-primary-100 p-3 text-primary-700">
            <Globe2 className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-secondary-900">Web Research</h1>
            <p className="text-secondary-500">Source-backed research powered by TinyFish</p>
          </div>
        </div>
      </div>

      <form className="card space-y-4 p-5" onSubmit={handleSubmit}>
        <label className="label" htmlFor="research-query">What would you like to research?</label>
        <textarea
          id="research-query"
          className="input min-h-32 resize-y"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="For example: Research current supply-chain risks affecting automotive manufacturers and summarize the evidence."
          maxLength={10000}
          required
          disabled={loading}
        />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-secondary-500">
            Deep research can take several minutes and may incur TinyFish account usage charges.
          </p>
          <button type="submit" className="btn-primary shrink-0" disabled={loading || !query.trim()}>
            {loading ? <Sparkles className="h-4 w-4 animate-pulse" aria-hidden="true" /> : <Search className="h-4 w-4" aria-hidden="true" />}
            {loading ? 'Researching...' : 'Start research'}
          </button>
        </div>
      </form>

      {error && <div className="card border-danger-200 bg-danger-50 p-4 text-sm text-danger-700" role="alert">{error}</div>}

      {progress && !error && (
        <div className="flex items-center gap-2 text-sm text-secondary-600" role="status" aria-live="polite">
          {loading && <Sparkles className="h-4 w-4 animate-pulse text-primary-600" aria-hidden="true" />}
          {progress}
        </div>
      )}

      {report && (
        <section className="card space-y-5 p-5" aria-labelledby="research-report-title">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary-600" aria-hidden="true" />
            <h2 id="research-report-title" className="text-lg font-semibold text-secondary-900">Research report</h2>
          </div>
          <div className="whitespace-pre-wrap break-words text-sm leading-7 text-secondary-700">{report}</div>
          {citations.length > 0 && (
            <div className="border-t border-secondary-200 pt-4">
              <h3 className="mb-3 text-sm font-semibold text-secondary-800">Sources</h3>
              <ul className="space-y-2">
                {citations.map((citation, index) => (
                  <li key={`${citation.url}-${index}`}>
                    <a
                      className="inline-flex items-center gap-2 break-all text-sm text-primary-700 hover:underline"
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {citation.title || citation.url}
                      <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
