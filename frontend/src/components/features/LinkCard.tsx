interface LinkMeta {
  title?: string;
  description?: string;
  image?: string;
  favicon?: string;
}

interface LinkCardProps {
  link: string;
  meta?: LinkMeta | null;
}

function getDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export function LinkCard({ link, meta }: LinkCardProps) {
  const domain = getDomain(link);

  if (!meta) {
    return (
      <a
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 inline-block text-sm text-blue-600 hover:underline break-all"
      >
        {link}
      </a>
    );
  }

  const thumbnail = meta.image || meta.favicon;

  return (
    <a
      href={link}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-2 flex h-[4.5rem] max-w-sm overflow-hidden rounded-md border transition-colors hover:bg-accent/50"
    >
      {thumbnail && (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          src={thumbnail}
          alt=""
          className="h-full w-[4.5rem] shrink-0 object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).parentElement!.style.display = "none";
          }}
        />
      )}
      <div className="flex min-w-0 flex-col justify-center px-3 py-1.5">
        <p className="truncate text-sm font-medium leading-snug">
          {meta.title || domain}
        </p>
        <p className="line-clamp-2 text-xs leading-tight text-muted-foreground">
          {meta.description || domain}
        </p>
      </div>
    </a>
  );
}
