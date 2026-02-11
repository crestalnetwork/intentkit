"use client";

import { type SyntheticEvent } from "react";
import dynamic from "next/dynamic";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Lazy load ReactMarkdown to avoid build issues with static export
const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

// Common image file extensions for auto-preview
const IMAGE_EXTENSIONS = /\.(jpg|jpeg|png|svg|webp|gif|bmp|ico|avif)$/i;

interface MarkdownRendererProps {
  children: string;
  className?: string;
  components?: Components;
}

// On image load error, replace the image with a plain link
function handleImageError(e: SyntheticEvent<HTMLImageElement>) {
  const img = e.currentTarget;
  const link = img.parentElement;
  if (link) {
    link.textContent = img.alt || img.src;
  }
}

// Default components with image preview for URLs and safe link handling
const defaultComponents: Components = {
  a: ({ href, children, ...props }) => {
    // Auto-preview: if the URL ends with a common image extension, render as image
    if (href && IMAGE_EXTENSIONS.test(href)) {
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={href}
            alt={typeof children === "string" ? children : href}
            className="max-w-full rounded-md my-1"
            loading="lazy"
            onError={handleImageError}
          />
        </a>
      );
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
        {children}
      </a>
    );
  },
};

export function MarkdownRenderer({ children, className, components }: MarkdownRendererProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ ...defaultComponents, ...components }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
