import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

export type Politeness = 'polite' | 'assertive';
type Announce = (message: string, politeness?: Politeness) => void;

const AnnouncerContext = createContext<Announce | null>(null);

/**
 * Single screen reader announcement mechanism (frontend_i18n.AC-12): one polite and one
 * assertive live region. Views announce through useAnnounce() and never create their own
 * regions. A nested provider reuses the outer regions.
 */
export function AnnouncerProvider({ children }: { children: ReactNode }) {
  const parent = useContext(AnnouncerContext);
  const [messages, setMessages] = useState<Record<Politeness, string>>({
    polite: '',
    assertive: '',
  });
  const frames = useRef<Partial<Record<Politeness, number>>>({});

  const announce = useCallback<Announce>((message, politeness = 'polite') => {
    // Clear first and write on the next frame so a repeated message is announced again.
    setMessages((current) => ({ ...current, [politeness]: '' }));
    const pending = frames.current[politeness];
    if (pending !== undefined) cancelAnimationFrame(pending);
    frames.current[politeness] = requestAnimationFrame(() => {
      frames.current[politeness] = undefined;
      setMessages((current) => ({ ...current, [politeness]: message }));
    });
  }, []);

  useEffect(() => {
    const pending = frames.current;
    return () => {
      Object.values(pending).forEach((id) => id !== undefined && cancelAnimationFrame(id));
    };
  }, []);

  const value = useMemo(() => parent ?? announce, [parent, announce]);

  if (parent !== null) {
    return <>{children}</>;
  }

  return (
    <AnnouncerContext.Provider value={value}>
      {children}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {messages.polite}
      </div>
      <div role="alert" aria-live="assertive" aria-atomic="true" className="sr-only">
        {messages.assertive}
      </div>
    </AnnouncerContext.Provider>
  );
}

export function useAnnounce(): Announce {
  const announce = useContext(AnnouncerContext);
  if (announce === null) {
    throw new Error('useAnnounce() must be used inside <AnnouncerProvider>');
  }
  return announce;
}
