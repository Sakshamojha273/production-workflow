import React from 'react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  onError?: (error: Error, info: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Top-level boundary: a render error shows a message instead of React
 * unmounting the whole tree and leaving #root empty.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Unhandled render error:', error, info.componentStack);
    this.props.onError?.(error, info);
  }

  private reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div role="alert" className="min-h-[50vh] flex items-center justify-center p-8">
        <div className="card p-8 max-w-lg text-center">
          <h2 className="text-xl font-semibold text-secondary-900 mb-2">Something went wrong</h2>
          <p className="text-secondary-500 mb-4">This page failed to render. Details: {error.message}</p>
          <div className="flex justify-center gap-2">
            <button type="button" className="btn-secondary" onClick={this.reset}>
              Try again
            </button>
            <button type="button" className="btn-primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      </div>
    );
  }
}
