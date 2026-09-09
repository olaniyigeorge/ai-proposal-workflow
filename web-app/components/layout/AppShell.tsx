'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { NavBar } from './NavBar';
import { DEV_TOKEN } from '@/lib/auth/session';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // If on login page, don't show shell chrome
  if (pathname === '/login') {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-[#090a0f] text-zinc-100 flex flex-col md:flex-row antialiased">
      {/* Mobile Top Header */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-[#1e2436] bg-[#0d0f17]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-sm">
            P
          </div>
          <span className="font-semibold text-sm tracking-tight text-white">
            Proposal Workflow
          </span>
        </div>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800"
          aria-label="Toggle Navigation"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            {mobileMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile Dropdown Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-[#1e2436] bg-[#0d0f17] p-4 space-y-4">
          <NavBar />
          <div className="pt-3 border-t border-[#1e2436] flex items-center justify-between text-xs text-zinc-400">
            <span>Salesperson Role</span>
            <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono text-[10px]">
              Dev Auth
            </span>
          </div>
        </div>
      )}

      {/* Desktop Sidebar */}
      <aside className="hidden md:flex md:w-64 flex-col flex-shrink-0 border-r border-[#1e2436] bg-[#0d0f17]/90 backdrop-blur-md">
        {/* Brand Header */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-[#1e2436]">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center font-bold text-white shadow-md shadow-indigo-500/20">
            P
          </div>
          <div>
            <div className="font-semibold text-sm tracking-tight text-white leading-none">
              Proposal Workflow
            </div>
            <div className="text-[11px] text-zinc-500 font-medium mt-1">
              Salesperson Review UI
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex-1 px-4 py-6">
          <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider px-3 mb-2">
            Workspace
          </div>
          <NavBar />
        </div>

        {/* User / Session Footer */}
        <div className="p-4 border-t border-[#1e2436] bg-[#0b0d14]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700/80 flex items-center justify-center text-xs font-semibold text-zinc-300">
              SP
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-zinc-200 truncate">
                Salesperson
              </div>
              <div className="text-[11px] text-zinc-500 truncate flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>Dev Authenticated</span>
              </div>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-zinc-800/60 flex items-center justify-between text-[10px] text-zinc-500">
            <span>Role: salesperson</span>
            <Link
              href="/login"
              className="text-indigo-400 hover:text-indigo-300 hover:underline"
            >
              Switch
            </Link>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 flex flex-col bg-[#090a0f] overflow-y-auto">
        <div className="flex-1 px-4 py-6 sm:px-6 md:px-8 lg:px-10 max-w-7xl w-full mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
