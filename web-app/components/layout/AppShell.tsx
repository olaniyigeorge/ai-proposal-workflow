'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { NavBar } from './NavBar';
import { BackendKeepAlive } from './BackendKeepAlive';
import { clearClientAuthToken, getClientSessionInfo } from '@/lib/auth/session';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [session, setSession] = useState<{ email: string | null; isDevToken: boolean }>({
    email: null,
    isDevToken: false,
  });

  useEffect(() => {
    setSession(getClientSessionInfo());
  }, [pathname]);

  const handleSignOut = () => {
    clearClientAuthToken();
    router.push('/login');
  };

  // If on login page, don't show shell chrome — but still keep the backend
  // warm, since a cold-started backend on the very first request (someone
  // arriving at /login) is the most visible time for this to matter.
  if (pathname === '/login') {
    return (
      <>
        <BackendKeepAlive />
        {children}
      </>
    );
  }

  return (
    <div className="min-h-screen bg-white text-[#1f2429] flex flex-col md:flex-row antialiased">
      <BackendKeepAlive />
      {/* Mobile Top Header */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-[#d8dbd9] bg-white">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#1f2429] flex items-center justify-center font-bold text-white shadow-sm">
            K
          </div>
          <span className="font-semibold text-sm tracking-tight text-[#1f2429]">
            Proposal Workflow
          </span>
        </div>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-2 rounded-md text-[#5c646c] hover:text-[#1f2429] hover:bg-[#f5f6f5]"
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
        <div className="md:hidden border-b border-[#d8dbd9] bg-white p-4 space-y-4">
          <NavBar />
          <div className="pt-3 border-t border-[#d8dbd9] flex items-center justify-between text-xs text-[#5c646c]">
            <span className="truncate">{session.email || 'Salesperson'}</span>
            <button
              onClick={handleSignOut}
              className="px-2 py-0.5 rounded-full bg-[#f5f6f5] border border-[#d8dbd9] text-[#1f2429] font-mono text-[10px] cursor-pointer hover:bg-[#eef0ee]"
            >
              Sign Out
            </button>
          </div>
        </div>
      )}

      {/* Desktop Sidebar — pinned to the viewport height (md:h-screen +
          sticky), with only the nav section scrolling internally, so the
          session footer (and its Sign Out action) always stays on screen
          instead of being pushed below the fold on a tall page. */}
      <aside className="hidden md:flex md:w-64 md:h-screen md:sticky md:top-0 flex-col flex-shrink-0 border-r border-[#d8dbd9] bg-[#f5f6f5] overflow-hidden">
        {/* Brand Header */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-[#d8dbd9] flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-[#1f2429] flex items-center justify-center font-bold text-white shadow-sm">
            K
          </div>
          <div>
            <div className="font-semibold text-sm tracking-tight text-[#1f2429] leading-none">
              Proposal Workflow
            </div>
            <div className="text-[11px] text-[#5c646c] font-medium mt-1">
              Salesperson Review UI
            </div>
          </div>
        </div>

        {/* Navigation — the only part of the sidebar that scrolls */}
        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-6">
          <div className="text-[10px] font-semibold text-[#8a8f8c] uppercase tracking-wider px-3 mb-2">
            Workspace
          </div>
          <NavBar />
        </div>

        {/* User / Session Footer — always visible, never scrolls away */}
        <div className="flex-shrink-0 p-4 border-t border-[#d8dbd9] bg-white">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#eef0ee] border border-[#d8dbd9] flex items-center justify-center text-xs font-semibold text-[#1f2429]">
              SP
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-[#1f2429] truncate">
                {session.email || 'Salesperson'}
              </div>
              <div className="text-[11px] text-[#5c646c] truncate flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span>{session.isDevToken ? 'Dev Authenticated' : 'Signed in'}</span>
              </div>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-[#eef0ee] flex items-center justify-between text-[10px] text-[#5c646c]">
            <span>Role: salesperson</span>
            <button
              onClick={handleSignOut}
              className="text-[#2563eb] hover:text-[#1d4ed8] hover:underline cursor-pointer"
            >
              Sign Out
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 flex flex-col bg-white overflow-y-auto">
        <div className="flex-1 px-4 py-6 sm:px-6 md:px-8 lg:px-10 max-w-7xl w-full mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
