'use client';

import React from 'react';
import { SectionApprovalStatus } from '@/lib/api/types';
import { getSectionStatusConfig } from '@/lib/proposal-status';

interface SectionApprovalBadgeProps {
  status: SectionApprovalStatus | string;
}

export function SectionApprovalBadge({ status }: SectionApprovalBadgeProps) {
  const config = getSectionStatusConfig(status);

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${config.badgeClass}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotClass}`} />
      <span>{config.label}</span>
    </span>
  );
}
