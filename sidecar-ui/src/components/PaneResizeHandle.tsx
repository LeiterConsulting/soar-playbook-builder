interface PaneResizeHandleProps {
  orientation: "horizontal" | "vertical";
  ariaLabel: string;
  ariaValueNow?: number;
  onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => void;
  onDoubleClick?: () => void;
  className?: string;
}

/** Draggable grip for resizing panes (horizontal = row split, vertical = column split). */
export function PaneResizeHandle({
  orientation,
  ariaLabel,
  ariaValueNow,
  onPointerDown,
  onDoubleClick,
  className = "",
}: PaneResizeHandleProps) {
  const isVertical = orientation === "vertical";

  return (
    <div
      className={`pane-resize-handle pane-resize-handle-${orientation}${className ? ` ${className}` : ""}`}
      role="separator"
      aria-orientation={isVertical ? "vertical" : "horizontal"}
      aria-valuenow={ariaValueNow}
      aria-label={ariaLabel}
      onPointerDown={onPointerDown}
      onDoubleClick={onDoubleClick}
    >
      <span
        className={`pane-resize-grip pane-resize-grip-${orientation}`}
        aria-hidden="true"
      />
    </div>
  );
}
