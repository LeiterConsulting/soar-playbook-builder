import type { RefObject } from "react";
import { useResizablePaneHeight } from "./useResizablePaneHeight";

/** Drag-to-resize chat panel height; persists preference in localStorage. */
export function useResizableChatHeight(
  containerRef: RefObject<HTMLElement | null>,
  chatStackRef: RefObject<HTMLElement | null>,
  footerRef: RefObject<HTMLElement | null>,
) {
  const { paneHeight, onPointerDown, resetHeight } = useResizablePaneHeight(
    containerRef,
    chatStackRef,
    {
      storageKey: "pb-chat-panel-height",
      minPane: 56,
      minSibling: 220,
      siblingRef: footerRef,
    },
  );

  return { chatHeight: paneHeight, onPointerDown, resetHeight };
}
