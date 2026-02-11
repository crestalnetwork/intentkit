"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

// Lazy load ReactMarkdown to avoid build issues with static export
const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

// Common image file extensions for auto-preview (matched against URL pathname)
const IMAGE_EXTENSIONS = /\.(jpg|jpeg|png|webp|gif|bmp|ico|avif)$/i;

// Check if a URL points to an image based on its pathname
function isImageUrl(url: string): boolean {
  try {
    const pathname = new URL(url).pathname;
    return IMAGE_EXTENSIONS.test(pathname);
  } catch {
    return IMAGE_EXTENSIONS.test(url);
  }
}

// Check if a URL is an external http(s) link
function isExternalUrl(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

interface MarkdownRendererProps {
  children: string;
  className?: string;
  components?: Components;
  enableBreaks?: boolean;
}

// Image preview component with error fallback using React state
function ImagePreview({ href, alt }: { href: string; alt: string }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {alt || href}
      </a>
    );
  }

  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={href}
        alt={alt}
        className="max-w-full rounded-md my-1"
        loading="lazy"
        onError={() => setFailed(true)}
      />
    </a>
  );
}

// Default components with image preview for URLs and safe link handling
const defaultComponents: Components = {
  a: ({ href, children, ...props }) => {
    // Auto-preview: if the URL points to a common image, render as image preview
    if (href && isImageUrl(href)) {
      const alt = typeof children === "string" ? children : href;
      return <ImagePreview href={href} alt={alt} />;
    }
    // Only open external http(s) links in new tab
    if (href && isExternalUrl(href)) {
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
          {children}
        </a>
      );
    }
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  },
};

export function MarkdownRenderer({
  children,
  className,
  components,
  enableBreaks = false,
}: MarkdownRendererProps) {
  const plugins = enableBreaks ? [remarkGfm, remarkBreaks] : [remarkGfm];
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={plugins}
        components={{ ...defaultComponents, ...components }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
