import React from 'react';
import { AlertOctagon, RotateCcw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Unhandled UI exception caught by ErrorBoundary:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (typeof this.props.onReset === 'function') {
      this.props.onReset();
    } else {
      window.location.reload();
    }
  };

  handleSignOut = () => {
    try {
      localStorage.removeItem('haemopulse_user');
      localStorage.removeItem('token');
    } catch {
      // Ignore storage access errors
    }
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] p-6 text-center">
          <div className="w-full max-w-lg p-6 sm:p-8 rounded-2xl glass-panel border border-rose-900/60 bg-slate-950/90 shadow-2xl space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-rose-950/80 border border-rose-800/80 flex items-center justify-center text-rose-400 mx-auto shadow-lg">
              <AlertOctagon className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Something went wrong</h2>
              <p className="text-xs text-slate-400 mt-1">
                An unexpected error occurred while rendering this section. Your session remains intact.
              </p>
            </div>
            {this.state.error?.message && (
              <div className="p-3 bg-slate-900/90 border border-slate-800 rounded-xl text-left text-[11px] font-mono text-rose-300 overflow-x-auto max-h-32">
                {this.state.error.message}
              </div>
            )}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-blood-600 hover:bg-blood-500 text-white text-xs font-bold transition flex items-center justify-center space-x-2"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Retry &amp; Reload</span>
              </button>
              <button
                type="button"
                onClick={this.handleSignOut}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
              >
                Sign In Again
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
