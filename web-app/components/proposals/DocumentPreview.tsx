'use client';

import React, { useEffect, useState } from 'react';
import { getDocument } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { DocumentArtifactResponse } from '@/lib/api/types';

interface DocumentPreviewProps {
  proposalId: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

export function DocumentPreview({ proposalId }: DocumentPreviewProps) {
  const [doc, setDoc] = useState<DocumentArtifactResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getDocument(proposalId)
      .then((data) => {
        if (!cancelled) setDoc(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load document.');
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [proposalId]);

  if (isLoading) {
    return <p className="text-xs text-zinc-500">Loading document…</p>;
  }

  if (error) {
    return <p className="text-xs text-rose-400">{error}</p>;
  }

  if (!doc) {
    return null;
  }

  return (
    <div className="p-3 rounded-lg bg-teal-950/20 border border-teal-800/40 text-xs space-y-2">
      <div className="flex items-center justify-between text-teal-300">
        <span className="font-medium">Document Ready</span>
        <span className="text-teal-400/70">
          {doc.page_count} page{doc.page_count === 1 ? '' : 's'} &middot; {formatBytes(doc.file_size_bytes)}
        </span>
      </div>
      <a
        href={doc.download_url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-indigo-300 hover:text-indigo-200 font-medium"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        Download PDF
      </a>
    </div>
  );
}
