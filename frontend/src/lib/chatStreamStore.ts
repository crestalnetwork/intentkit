import type { ChatMessage } from "@/types/chat";

// Module-level stream store: owns the fetch lifecycle independently of React
// components, so navigation does not cancel an in-flight chat generation.

export type StreamStatus = "active" | "done" | "error" | "cancelled";

export type StreamSnapshot = {
  messages: ChatMessage[];
  status: StreamStatus;
  error?: Error;
};

type Session = {
  controller: AbortController;
  snapshot: StreamSnapshot;
};

type Listener = (snapshot: StreamSnapshot | null) => void;

const sessions = new Map<string, Session>();
const listeners = new Map<string, Set<Listener>>();

// Keep finished sessions around briefly so a remounting component can still
// apply the tail of the stream (e.g. the "cancelled" status + any trailing
// messages) before we drop them.
const CLEANUP_AFTER_MS = 120_000;

function getOrCreateListeners(key: string): Set<Listener> {
  let set = listeners.get(key);
  if (!set) {
    set = new Set();
    listeners.set(key, set);
  }
  return set;
}

function readSnapshot(key: string): StreamSnapshot | null {
  const session = sessions.get(key);
  if (!session) return null;
  return {
    messages: [...session.snapshot.messages],
    status: session.snapshot.status,
    error: session.snapshot.error,
  };
}

function notify(key: string) {
  const set = listeners.get(key);
  if (!set || set.size === 0) return;
  const snapshot = readSnapshot(key);
  set.forEach((fn) => fn(snapshot));
}

function scheduleCleanup(key: string, session: Session) {
  setTimeout(() => {
    const current = sessions.get(key);
    if (current === session && current.snapshot.status !== "active") {
      sessions.delete(key);
      notify(key);
    }
  }, CLEANUP_AFTER_MS);
}

export function startChatStream(
  key: string,
  runner: (signal: AbortSignal) => AsyncGenerator<ChatMessage>,
): boolean {
  const existing = sessions.get(key);
  if (existing && existing.snapshot.status === "active") {
    return false;
  }

  const controller = new AbortController();
  const session: Session = {
    controller,
    snapshot: { messages: [], status: "active" },
  };
  sessions.set(key, session);
  notify(key);

  void (async () => {
    try {
      for await (const msg of runner(controller.signal)) {
        session.snapshot.messages.push(msg);
        notify(key);
      }
      session.snapshot.status = "done";
      notify(key);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        session.snapshot.status = "cancelled";
      } else {
        session.snapshot.status = "error";
        session.snapshot.error =
          err instanceof Error ? err : new Error(String(err));
      }
      notify(key);
    } finally {
      scheduleCleanup(key, session);
    }
  })();

  return true;
}

export function cancelChatStream(key: string): void {
  const session = sessions.get(key);
  if (session && session.snapshot.status === "active") {
    session.controller.abort();
  }
}

export function getChatStreamSnapshot(key: string): StreamSnapshot | null {
  return readSnapshot(key);
}

export function subscribeToChatStream(
  key: string,
  listener: Listener,
): () => void {
  const set = getOrCreateListeners(key);
  set.add(listener);
  listener(readSnapshot(key));
  return () => {
    const current = listeners.get(key);
    if (!current) return;
    current.delete(listener);
    if (current.size === 0) listeners.delete(key);
  };
}
