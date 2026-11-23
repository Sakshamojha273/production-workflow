import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Mail, Lock, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

const DEMO_EMAIL = 'admin@smartplan.ai';
const DEMO_PASSWORD = 'admin123';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoLogin, setDemoLogin] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (demoLogin) {
        await api.demoLogin();
      } else {
        await api.login(email, password);
      }
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-secondary-50 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="brand-logo brand-logo-login mb-4" aria-label="SmartPlan AI">
            <Activity className="brand-logo-icon w-10 h-10 text-white" aria-hidden="true" />
          </div>
          <h1 className="text-3xl font-bold text-secondary-900">SmartPlan AI</h1>
          <p className="text-secondary-500 mt-1">AI-Powered Production Planning & Workforce Optimization</p>
        </div>

        {/* Login Card */}
        <div className="card p-8">
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-secondary-900">Welcome back</h2>
            <p className="text-secondary-500 mt-1">Sign in to your account to continue</p>
          </div>

          {error && (
            <div className="mb-6 flex items-center gap-2 p-3 rounded-lg bg-danger-50 border border-danger-200 text-danger-700" role="alert">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <p className="text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="label">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input pl-10"
                  placeholder="admin@smartplan.ai"
                  required
                  disabled={loading}
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="label">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-secondary-400" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input pl-10 pr-10"
                  placeholder="••••••••"
                  required
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary-400 hover:text-secondary-600"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={demoLogin}
                  onChange={(e) => {
                    setDemoLogin(e.target.checked);
                    // Fill the demo account so the required fields never block a demo sign-in.
                    if (e.target.checked) {
                      setEmail(DEMO_EMAIL);
                      setPassword(DEMO_PASSWORD);
                    }
                  }}
                  className="w-4 h-4 rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-secondary-600">Use demo credentials</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Signing in...
                </span>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-secondary-200">
            <p className="text-center text-sm text-secondary-500">
              Demo credentials:
              <code className="ml-1 px-1.5 py-0.5 bg-secondary-100 rounded text-secondary-700 font-mono text-xs">admin@smartplan.ai / admin123</code>
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-6 text-sm text-secondary-500">
          <p>© 2024 SmartPlan AI. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
}