'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function NavBar() {
  const pathname = usePathname();

  const navItems = [
     {
      name: 'New Request',
      href: 'https://docs.google.com/forms/u/0/d/e/1FAIpQLSfa8ndbPc9pNgyOpapTh8h4QnUWjTyx_CkCBS7iExXp97FaCQ/formResponse',
      external: true,
      icon: (
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6m5-3h5m0 0v5m0-5L10 14"
          />
        </svg>
      ),
    },
    {
      name: 'Proposals',
      href: '/proposals',
      active: pathname.startsWith('/proposals'),
      icon: (
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      ),
    },
    {
      name: 'Team',
      href: '/team',
      active: pathname.startsWith('/team'),
      icon: (
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-1.13a4 4 0 100-8 4 4 0 000 8zm6 1.13a4 4 0 013 3.87V20"
          />
        </svg>
      ),
    },
  ];


return (
  <nav className="space-y-1">
    {navItems.map((item) =>
      item.external ? (
        <a
          key={item.name}
          href={item.href}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[#5c646c] hover:text-[#1f2429] hover:bg-white transition-all duration-150"
        >
          <span className="text-[#5c646c]">{item.icon}</span>

          {item.name}

          <svg
            className="w-3 h-3 ml-auto text-[#9aa0a6]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </a>
      ) : (
        <Link
          key={item.name}
          href={item.href}
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
            item.active
              ? "bg-[#2563eb]/10 text-[#2563eb] border border-[#2563eb]/20 shadow-sm"
              : "text-[#5c646c] hover:text-[#1f2429] hover:bg-white"
          }`}
        >
          <span
            className={
              item.active ? "text-[#2563eb]" : "text-[#5c646c]"
            }
          >
            {item.icon}
          </span>

          {item.name}
        </Link>
      )
    )}
  </nav>
)
}