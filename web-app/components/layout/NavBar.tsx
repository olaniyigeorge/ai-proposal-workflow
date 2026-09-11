'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export function NavBar() {
  const pathname = usePathname();

  const navItems = [
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
  ];

  return (
    <nav className="space-y-1">
      {navItems.map((item) => (
        <Link
          key={item.name}
          href={item.href}
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
            item.active
              ? 'bg-[#2563eb]/10 text-[#2563eb] border border-[#2563eb]/20 shadow-sm'
              : 'text-[#5c646c] hover:text-[#1f2429] hover:bg-white'
          }`}
        >
          <span className={item.active ? 'text-[#2563eb]' : 'text-[#5c646c]'}>
            {item.icon}
          </span>
          {item.name}
        </Link>
      ))}
    </nav>
  );
}
