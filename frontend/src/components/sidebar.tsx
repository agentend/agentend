"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  Rocket,
  Brain,
  RefreshCw,
  BarChart3,
  Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/fleet", label: "Fleet", icon: Rocket },
  { href: "/memory", label: "Memory", icon: Brain },
  { href: "/workflows", label: "Workflows", icon: RefreshCw },
  { href: "/metrics", label: "Metrics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col items-center w-12 bg-sidebar border-r border-border py-3 gap-1">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            title={label}
            className={`flex items-center justify-center w-9 h-9 rounded-md transition-colors ${
              active
                ? "bg-white text-black"
                : "text-text-muted hover:text-text-primary hover:bg-hover"
            }`}
          >
            <Icon size={18} />
          </Link>
        );
      })}
    </nav>
  );
}
