'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import { ProposalSummaryResponse } from '@/lib/api/types';
import { ProposalStatusBadge } from './ProposalStatusBadge';

interface ProposalListProps {
  initialProposals: ProposalSummaryResponse[];
}

export function ProposalList({ initialProposals }: ProposalListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const filteredProposals = useMemo(() => {
    return initialProposals.filter((p) => {
      const matchesSearch =
        searchQuery === '' ||
        p.company_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.client_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.client_email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.salesperson_name.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus =
        statusFilter === 'ALL' || p.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [initialProposals, searchQuery, statusFilter]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: initialProposals.length };
    initialProposals.forEach((p) => {
      counts[p.status] = (counts[p.status] || 0) + 1;
    });
    return counts;
  }, [initialProposals]);

  const quickFilterTabs = [
    { id: 'ALL', label: 'All Proposals' },
    { id: 'IN_REVIEW', label: 'In Review' },
    { id: 'PENDING_APPROVAL', label: 'Pending Approval' },
    { id: 'APPROVED', label: 'Approved' },
    { id: 'DRAFT', label: 'Draft' },
  ];

  return (
    <div className="space-y-6">
      {/* Search & Filter Header */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Search input */}
        <div className="relative flex-1 max-w-md">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-500">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            placeholder="Search by company, client, or salesperson..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-[#121520] border border-[#1e2436] focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg text-sm text-zinc-200 placeholder-zinc-500 transition-colors duration-150 outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-xs text-zinc-500 hover:text-zinc-300"
            >
              Clear
            </button>
          )}
        </div>

        {/* Quick status tabs */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          {quickFilterTabs.map((tab) => {
            const count = statusCounts[tab.id] || 0;
            const isSelected = statusFilter === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
                  isSelected
                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40 border border-transparent'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                    isSelected
                      ? 'bg-indigo-500/30 text-indigo-200'
                      : 'bg-zinc-800 text-zinc-500'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Proposals Content */}
      {filteredProposals.length === 0 ? (
        <div className="rounded-xl border border-[#1e2436] bg-[#121520] p-12 text-center">
          <div className="w-12 h-12 rounded-full bg-zinc-800/80 border border-zinc-700/50 flex items-center justify-center mx-auto text-zinc-400 mb-4">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-zinc-200">
            No proposals found
          </h3>
          <p className="text-sm text-zinc-500 mt-1 max-w-sm mx-auto">
            {searchQuery || statusFilter !== 'ALL'
              ? 'No proposals matched your filter criteria. Try clearing search or status filters.'
              : 'No proposal records currently exist. Submissions arrive via Google Forms & n8n webhook into POST /intake.'}
          </p>
          {(searchQuery || statusFilter !== 'ALL') && (
            <button
              onClick={() => {
                setSearchQuery('');
                setStatusFilter('ALL');
              }}
              className="mt-4 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 text-zinc-300 hover:bg-zinc-700 border border-zinc-700"
            >
              Reset Filters
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-[#1e2436] bg-[#121520] overflow-hidden shadow-xl shadow-black/20">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#1e2436] bg-[#0d0f17]/80 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                  <th className="py-3.5 px-4 sm:px-6">Company & Client</th>
                  <th className="py-3.5 px-4">Salesperson</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Created</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2436] text-sm">
                {filteredProposals.map((proposal) => (
                  <tr
                    key={proposal.id}
                    className="hover:bg-[#171b29] transition-colors group"
                  >
                    <td className="py-4 px-4 sm:px-6">
                      <Link
                        href={`/proposals/${proposal.id}`}
                        className="block group-hover:text-indigo-300"
                      >
                        <div className="font-medium text-zinc-100 flex items-center gap-2">
                          <span>{proposal.company_name}</span>
                        </div>
                        <div className="text-xs text-zinc-400 mt-0.5 flex items-center gap-2">
                          <span>{proposal.client_name}</span>
                          <span className="text-zinc-600">�</span>
                          <span className="text-zinc-500 font-mono text-[11px]">
                            {proposal.client_email}
                          </span>
                        </div>
                      </Link>
                    </td>
                    <td className="py-4 px-4 text-zinc-300 text-xs">
                      {proposal.salesperson_name}
                    </td>
                    <td className="py-4 px-4">
                      <ProposalStatusBadge status={proposal.status} size="sm" />
                    </td>
                    <td className="py-4 px-4 text-zinc-400 text-xs whitespace-nowrap">
                      {new Date(proposal.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </td>
                    <td className="py-4 px-4 text-right whitespace-nowrap">
                      <Link
                        href={`/proposals/${proposal.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800/80 hover:bg-indigo-600/30 text-zinc-300 hover:text-indigo-200 border border-zinc-700/60 hover:border-indigo-500/40 transition-all duration-150"
                      >
                        <span>Review</span>
                        <svg className="w-3.5 h-3.5 text-zinc-400 group-hover:text-indigo-300 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
