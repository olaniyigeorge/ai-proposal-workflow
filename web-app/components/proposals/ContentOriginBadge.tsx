'use client';

import React from 'react';
import { ContentOrigin } from '@/lib/api/types';
import { getContentOriginConfig } from '@/lib/proposal-status';

interface ContentOriginBadgeProps {
  origin: ContentOrigin | string;
}

export function ContentOriginBadge({ origin }: ContentOriginBadgeProps) {
  const config = getContentOriginConfig(origin);

  return (
    <span
      title={config.description}
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border tracking-wide uppercase ${config.badgeClass}`}
    >
      {config.label}
    </span>
  );
}
