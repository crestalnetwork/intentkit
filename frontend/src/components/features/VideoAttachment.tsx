"use client";

import type { ChatMessageAttachment } from "@/types/chat";

export function VideoAttachment({ att }: { att: ChatMessageAttachment }) {
  const src = att.url;
  if (!src) return null;

  return (
    <div className="max-w-md">
      <video controls className="rounded-lg w-full">
        <source src={src} />
        Your browser does not support the video tag.
      </video>
    </div>
  );
}
