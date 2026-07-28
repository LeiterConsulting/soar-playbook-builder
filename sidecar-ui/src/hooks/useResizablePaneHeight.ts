import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

export interface ResizablePaneHeightOptions {
  storageKey: string;
  minPane?: number;
  minSibling?: number;
  siblingRef?: RefObject<HTMLElement | null>;
}

function readStored(storageKey: string, minPane: number): number | null {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) && n >= minPane ? n : null;
  } catch {
    return null;
  }
}

/** Drag-to-resize a pane height within a column; persists preference in localStorage. */
export function useResizablePaneHeight(
  containerRef: RefObject<HTMLElement | null>,
  paneRef: RefObject<HTMLElement | null>,
  { storageKey, minPane = 56, minSibling = 120, siblingRef }: ResizablePaneHeightOptions,
) {
  const [paneHeight, setPaneHeight] = useState<number | null>(() =>
    readStored(storageKey, minPane),
  );
  const startHeightRef = useRef(0);
  const startYRef = useRef(0);

  const reservedSibling = useCallback(() => {
    const measured = siblingRef?.current?.offsetHeight;
    if (measured && measured > 0) return measured + 8;
    return minSibling;
  }, [minSibling, siblingRef]);

  const clampHeight = useCallback(
    (h: number) => {
      const container = containerRef.current;
      if (!container) return Math.max(minPane, h);
      const max = container.clientHeight - reservedSibling();
      if (max < minPane) {
        return Math.max(minPane, max);
      }
      return Math.max(minPane, Math.min(h, max));
    },
    [containerRef, minPane, reservedSibling],
  );

  const refitPane = useCallback(() => {
    setPaneHeight((h) => {
      if (h == null) return null;
      const next = clampHeight(h);
      if (next !== h) {
        try {
          localStorage.setItem(storageKey, String(Math.round(next)));
        } catch {
          /* ignore */
        }
      }
      return next;
    });
  }, [clampHeight, storageKey]);

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (e.button !== 0) return;
      e.preventDefault();

      const pane = paneRef.current;
      startHeightRef.current = paneHeight ?? pane?.offsetHeight ?? 200;
      startYRef.current = e.clientY;

      const handle = e.currentTarget;
      handle.setPointerCapture(e.pointerId);
      document.body.style.cursor = "row-resize";
      document.body.style.userSelect = "none";

      const onMove = (ev: PointerEvent) => {
        const delta = ev.clientY - startYRef.current;
        setPaneHeight(clampHeight(startHeightRef.current + delta));
      };

      const onUp = (ev: PointerEvent) => {
        handle.releasePointerCapture(ev.pointerId);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onUp);
        setPaneHeight((h) => {
          if (h != null) {
            try {
              localStorage.setItem(storageKey, String(Math.round(h)));
            } catch {
              /* ignore quota / private mode */
            }
          }
          return h;
        });
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
    },
    [clampHeight, paneHeight, paneRef, storageKey],
  );

  const resetHeight = useCallback(() => {
    setPaneHeight(null);
    try {
      localStorage.removeItem(storageKey);
    } catch {
      /* ignore */
    }
  }, [storageKey]);

  useEffect(() => {
    if (paneHeight == null) return;
    const onResize = () => refitPane();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [paneHeight, refitPane]);

  useEffect(() => {
    if (paneHeight == null) return;
    const container = containerRef.current;
    const sibling = siblingRef?.current;
    if (!container) return;

    const observer = new ResizeObserver(() => refitPane());
    observer.observe(container);
    if (sibling) observer.observe(sibling);
    return () => observer.disconnect();
  }, [paneHeight, containerRef, siblingRef, refitPane]);

  return { paneHeight, onPointerDown, resetHeight, refitPane };
}
