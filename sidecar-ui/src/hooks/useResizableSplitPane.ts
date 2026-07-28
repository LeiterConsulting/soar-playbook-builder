import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

const STORAGE_KEY = "pb-split-left-percent";
const MIN_LEFT_PERCENT = 22;
const MAX_LEFT_PERCENT = 82;
const MIN_PANE_PX = 260;

function readStored(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) && n >= MIN_LEFT_PERCENT && n <= MAX_LEFT_PERCENT ? n : null;
  } catch {
    return null;
  }
}

/** Drag-to-resize left/right column split; persists left pane width as % in localStorage. */
export function useResizableSplitPane(
  layoutRef: RefObject<HTMLElement | null>,
  leftRef: RefObject<HTMLElement | null>,
) {
  const [leftPercent, setLeftPercent] = useState<number | null>(readStored);
  const startPercentRef = useRef(0);
  const startXRef = useRef(0);

  const clampPercent = useCallback(
    (pct: number) => {
      const layout = layoutRef.current;
      if (!layout || layout.clientWidth <= 0) {
        return Math.max(MIN_LEFT_PERCENT, Math.min(MAX_LEFT_PERCENT, pct));
      }
      const minPct = (MIN_PANE_PX / layout.clientWidth) * 100;
      const maxPct = ((layout.clientWidth - MIN_PANE_PX) / layout.clientWidth) * 100;
      const lo = Math.max(MIN_LEFT_PERCENT, minPct);
      const hi = Math.min(MAX_LEFT_PERCENT, maxPct);
      return Math.max(lo, Math.min(hi, pct));
    },
    [layoutRef],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (e.button !== 0) return;
      e.preventDefault();

      const layout = layoutRef.current;
      const left = leftRef.current;
      if (!layout || !left) return;

      startXRef.current = e.clientX;
      startPercentRef.current =
        leftPercent ?? (left.offsetWidth / layout.clientWidth) * 100;

      const handle = e.currentTarget;
      handle.setPointerCapture(e.pointerId);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";

      const onMove = (ev: PointerEvent) => {
        const delta = ev.clientX - startXRef.current;
        const deltaPct = (delta / layout.clientWidth) * 100;
        setLeftPercent(clampPercent(startPercentRef.current + deltaPct));
      };

      const onUp = (ev: PointerEvent) => {
        handle.releasePointerCapture(ev.pointerId);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("pointercancel", onUp);
        setLeftPercent((pct) => {
          if (pct != null) {
            try {
              localStorage.setItem(STORAGE_KEY, String(Math.round(pct * 10) / 10));
            } catch {
              /* ignore */
            }
          }
          return pct;
        });
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
      window.addEventListener("pointercancel", onUp);
    },
    [clampPercent, layoutRef, leftPercent, leftRef],
  );

  const resetSplit = useCallback(() => {
    setLeftPercent(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (leftPercent == null) return;
    const onResize = () => {
      setLeftPercent((pct) => (pct != null ? clampPercent(pct) : null));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [leftPercent, clampPercent]);

  return { leftPercent, onPointerDown, resetSplit };
}
