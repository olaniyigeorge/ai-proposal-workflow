'use client';

import React from 'react';
import { ProposalStatus } from '@/lib/api/types';
import { getStatusConfig } from '@/lib/proposal-status';

interface ProposalStatusBadgeProps {
  status: ProposalStatus | string;
  size?: 'sm' | 'md' | 'lg';
  showDescription?: boolean;
}

export function ProposalStatusBadge({
  status,
  size = 'md',
  showDescription = false,
}: ProposalStatusBadgeProps) {
  const config = getStatusConfig(status);

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1.5',
    md: 'text-xs px-2.5 py-1 gap-2',
    lg: 'text-sm px-3 py-1.5 gap-2.5',
  }[size];

  return (
    <div className="inline-flex flex-col">
      <span
        title={config.description}
        className={`inline-flex items-center font-medium rounded-full border transition-all duration-200 ${sizeClasses} ${config.badgeClass}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${config.dotClass}`} />
        <span>{config.label}</span>
      </span>
      {showDescription && (
        <span className="text-[11px] text-zinc-400 mt-1 pl-1 font-normal">
          {config.description}
        </span>
      )}
    </div>
  );
}
