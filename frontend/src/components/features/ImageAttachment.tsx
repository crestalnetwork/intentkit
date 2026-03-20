"use client";

import { useState, useCallback, useEffect } from "react";
import { Download, X, ZoomIn } from "lucide-react";
import type { ChatMessageAttachment } from "@/types/chat";

function ImageLightbox({
  src,
  alt,
  onClose,
}: {
  src: string;
  alt: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const handleDownload = useCallback(async () => {
    try {
      const response = await fetch(src);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = alt || "image";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Fallback: open in new tab
      window.open(src, "_blank", "noopener,noreferrer");
    }
  }, [src, alt]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      {/* Toolbar */}
      <div className="absolute top-4 right-4 flex gap-2 z-10">
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleDownload();
          }}
          className="rounded-full bg-white/20 hover:bg-white/30 p-2 text-white transition-colors"
          title="Download"
        >
          <Download className="h-5 w-5" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          className="rounded-full bg-white/20 hover:bg-white/30 p-2 text-white transition-colors"
          title="Close"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      {/* Image */}
      <img
        src={src}
        alt={alt}
        className="max-h-[90vh] max-w-[90vw] object-contain rounded"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

export function ImageAttachment({ att }: { att: ChatMessageAttachment }) {
  const [isOpen, setIsOpen] = useState(false);
  const [hasError, setHasError] = useState(false);
  const handleClose = useCallback(() => setIsOpen(false), []);

  const src = att.url;
  if (!src || hasError) return null;

  const alt = att.name || "Image";

  return (
    <>
      <div
        className="relative group max-w-xs cursor-pointer"
        onClick={() => setIsOpen(true)}
      >
        <img
          src={src}
          alt={alt}
          className="rounded-lg max-h-60 object-cover"
          onError={() => setHasError(true)}
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors rounded-lg flex items-center justify-center">
          <ZoomIn className="h-6 w-6 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow-lg" />
        </div>
      </div>
      {isOpen && <ImageLightbox src={src} alt={alt} onClose={handleClose} />}
    </>
  );
}
