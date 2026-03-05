"use client";

import Link from "next/link";

export type NavItem = {
  href: string;
  label: string;
  icon: string;
  badge?: number;
  exact?: boolean;
};

export type NavSection = {
  label: string;
  items: NavItem[];
};

export function SidebarSection({
  section,
  isActive,
}: {
  section: NavSection;
  isActive: (href: string, exact?: boolean) => boolean;
}) {
  return (
    <div>
      <p className="mb-1 px-3 pt-4 text-xs font-semibold uppercase tracking-wider text-slate-400 first:pt-0">
        {section.label}
      </p>
      {section.items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            isActive(item.href, item.exact)
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          }`}
        >
          <svg
            className="h-5 w-5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d={item.icon}
            />
          </svg>
          <span className="flex-1">{item.label}</span>
          {item.badge != null && item.badge > 0 && (
            <span className="ml-auto inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-red-600 px-1.5 py-0.5 text-xs font-semibold leading-none text-white">
              {item.badge}
            </span>
          )}
        </Link>
      ))}
    </div>
  );
}
