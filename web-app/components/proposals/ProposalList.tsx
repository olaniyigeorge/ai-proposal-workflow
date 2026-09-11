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
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#8a8f8c]">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            placeholder="Search by company, client, or salesperson..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-white border border-[#d8dbd9] focus:border-[#2563eb] focus:ring-1 focus:ring-[#2563eb] rounded-lg text-sm text-[#1f2429] placeholder-[#9aa0a6] transition-colors duration-150 outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-xs text-[#8a8f8c] hover:text-[#1f2429]"
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
                    ? 'bg-[#2563eb]/10 text-[#2563eb] border border-[#2563eb]/30'
                    : 'text-[#5c646c] hover:text-[#1f2429] hover:bg-[#f5f6f5] border border-transparent'
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                    isSelected
                      ? 'bg-[#2563eb]/15 text-[#1d4ed8]'
                      : 'bg-[#f5f6f5] text-[#8a8f8c]'
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
        <div className="rounded-xl border border-[#d8dbd9] bg-white p-12 text-center">
          <div className="w-12 h-12 rounded-full bg-[#f5f6f5] border border-[#d8dbd9] flex items-center justify-center mx-auto text-[#8a8f8c] mb-4">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-[#1f2429]">
            No proposals found
          </h3>
          <p className="text-sm text-[#5c646c] mt-1 max-w-sm mx-auto">
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
              className="mt-4 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#f5f6f5] text-[#1f2429] hover:bg-[#eef0ee] border border-[#d8dbd9]"
            >
              Reset Filters
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-[#d8dbd9] bg-white overflow-hidden shadow-[0_8px_24px_-8px_rgba(31,36,41,0.1)]">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#d8dbd9] bg-[#f5f6f5] text-[11px] font-semibold text-[#5c646c] uppercase tracking-wider">
                  <th className="py-3.5 px-4 sm:px-6">Company & Client</th>
                  <th className="py-3.5 px-4">Salesperson</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Created</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eef0ee] text-sm">
                {filteredProposals.map((proposal, index) => (
                  <tr
                    key={proposal.id}
                    className="hover:bg-[#f5f6f5] transition-colors group animate-fade-in"
                    style={{ animationDelay: `${Math.min(index * 35, 280)}ms` }}
                  >
                    <td className="py-4 px-4 sm:px-6">
                      <Link
                        href={`/proposals/${proposal.id}`}
                        className="block group-hover:text-[#2563eb]"
                      >
                        <div className="font-medium text-[#1f2429] flex items-center gap-2">
                          <span>{proposal.company_name}</span>
                        </div>
                        <div className="text-xs text-[#5c646c] mt-0.5 flex items-center gap-2">
                          <span>{proposal.client_name}</span>
                          <span className="text-[#c2c7c4]">·</span>
                          <span className="text-[#8a8f8c] font-mono text-[11px]">
                            {proposal.client_email}
                          </span>
                        </div>
                      </Link>
                    </td>
                    <td className="py-4 px-4 text-[#374151] text-xs">
                      {proposal.salesperson_name}
                    </td>
                    <td className="py-4 px-4">
                      <ProposalStatusBadge status={proposal.status} size="sm" />
                    </td>
                    <td className="py-4 px-4 text-[#5c646c] text-xs whitespace-nowrap">
                      {new Date(proposal.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </td>
                    <td className="py-4 px-4 text-right whitespace-nowrap">
                      <Link
                        href={`/proposals/${proposal.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#f5f6f5] hover:bg-[#2563eb]/10 text-[#1f2429] hover:text-[#2563eb] border border-[#d8dbd9] hover:border-[#2563eb]/30 transition-all duration-150"
                      >
                        <span>Review</span>
                        <svg className="w-3.5 h-3.5 text-[#8a8f8c] group-hover:text-[#2563eb] transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
