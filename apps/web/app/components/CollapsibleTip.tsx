'use client';

import { useState } from 'react';

interface CollapsibleTipProps {
  title: string;
  icon?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleTip({
  title,
  icon = '',
  defaultOpen = false,
  children
}: CollapsibleTipProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl overflow-hidden transition-all duration-200">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-amber-100 transition-colors"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-3">
          {icon && <span className="text-xl">{icon}</span>}
          <span className="font-semibold text-amber-900 text-sm sm:text-base">
            {title}
          </span>
        </div>
        <svg
          className={`w-5 h-5 text-amber-700 transform transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 text-sm text-amber-900 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}
