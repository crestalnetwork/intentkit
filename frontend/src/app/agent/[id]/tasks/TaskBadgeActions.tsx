import Link from "next/link";

import { badgeVariants } from "@/components/ui/badge";

interface TaskBadgeActionsProps {
  enabled: boolean;
  logsHref: string;
  onToggle: () => void;
  readOnly?: boolean;
}

export function TaskBadgeActions({
  enabled,
  logsHref,
  onToggle,
  readOnly,
}: TaskBadgeActionsProps) {
  return (
    <>
      <Link href={logsHref} className={badgeVariants({ variant: "outline" })}>
        Logs
      </Link>
      {readOnly ? (
        <span
          className={badgeVariants({ variant: enabled ? "default" : "secondary" })}
        >
          {enabled ? "Enabled" : "Disabled"}
        </span>
      ) : (
        <button
          type="button"
          className={badgeVariants({ variant: enabled ? "default" : "secondary" })}
          onClick={onToggle}
        >
          {enabled ? "Enabled" : "Disabled"}
        </button>
      )}
    </>
  );
}
