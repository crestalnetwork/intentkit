"use client";

import dynamic from "next/dynamic";
import type { Components } from "react-markdown";

// Lazy load ReactMarkdown to avoid build issues with static export
const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

interface MarkdownRendererProps {
  children: string;
  className?: string;
  components?: Components;
}

export function MarkdownRenderer({ children, className, components }: MarkdownRendererProps) {
  return (
    <div className={className}>
      <ReactMarkdown components={components}>{children}</ReactMarkdown>
    </div>
  );
}
