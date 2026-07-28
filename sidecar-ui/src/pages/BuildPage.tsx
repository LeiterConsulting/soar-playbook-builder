import { useRef, type CSSProperties } from "react";
import { PreviewColumn } from "../components/PreviewColumn";
import { TroubleshootingCard } from "../components/TroubleshootingCard";
import { TemplateLibrary } from "../components/TemplateLibrary";
import { AssistantBanner } from "../components/AssistantBanner";
import { useBuilder } from "../context/BuilderProvider";
import { PaneResizeHandle } from "../components/PaneResizeHandle";
import { useResizableChatHeight } from "../hooks/useResizableChatHeight";
import { useResizableSplitPane } from "../hooks/useResizableSplitPane";

/** Main build workspace: chat, templates, preview, import actions. */
export function BuildPage({ coachLaneOnly = false }: { coachLaneOnly?: boolean }) {
  const b = useBuilder();
  const layoutRef = useRef<HTMLDivElement>(null);
  const leftRef = useRef<HTMLDivElement>(null);
  const chatStackRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLElement>(null);
  const { chatHeight, onPointerDown: onChatResize, resetHeight: resetChatHeight } =
    useResizableChatHeight(leftRef, chatStackRef, footerRef);
  const { leftPercent, onPointerDown: onSplitResize, resetSplit } = useResizableSplitPane(
    layoutRef,
    leftRef,
  );

  const layoutStyle =
    leftPercent != null
      ? ({ ["--split-left" as string]: `${leftPercent}%` } as CSSProperties)
      : undefined;

  return (
    <div
      ref={layoutRef}
      className={`layout${leftPercent != null ? " layout-split-sized" : ""}`}
      style={layoutStyle}
    >
      <div className="left build-left" ref={leftRef}>
        <AssistantBanner />
        <div
          ref={chatStackRef}
          className={`chat-stack${chatHeight != null ? " chat-stack-sized" : ""}`}
          style={chatHeight != null ? { height: chatHeight } : undefined}
        >
          <div className="chat-head">
            <h2>Chat</h2>
          </div>
          <div id="messages" className="chat-panel">
            {b.messages.length === 0 && (
              <p className="chat-empty">
                {b.coachTab === "explain"
                  ? "Ask for a lesson, quiz, or datapath explain — e.g. lesson 01-hello-playbook"
                  : b.coachTab === "respond"
                    ? "Use Respond above for suggestions, or describe a playbook here."
                    : "Choose a template below, load it, or describe a playbook in natural language."}
              </p>
            )}
            {b.messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}>
                {m.text}
              </div>
            ))}
            <div ref={b.messagesEndRef} />
          </div>
          <PaneResizeHandle
            orientation="horizontal"
            className="chat-resize-handle"
            ariaLabel="Drag to resize chat history. Templates and Natural language stay visible below. Double-click to reset."
            ariaValueNow={chatHeight ?? undefined}
            onPointerDown={onChatResize}
            onDoubleClick={resetChatHeight}
          />
        </div>
        <footer ref={footerRef} className="build-footer build-footer-pinned">
          {!coachLaneOnly && (
          <TemplateLibrary
            patterns={b.patterns}
            byCategory={b.patternsByCategory}
            orgTemplateCount={b.orgTemplateCount}
            value={b.currentPattern}
            onChange={b.setCurrentPattern}
            onLoad={() => void b.handleScaffold()}
            onValidate={() => void b.handleValidate()}
            onUseScenarioPrompt={(s) => b.setInput(s.examplePrompt)}
            busy={b.busy}
            scoreLabel={b.scoreLabel}
          />
          )}
          {b.troubleshooting && (
            <TroubleshootingCard
              entry={b.troubleshooting}
              onDismiss={() => b.setTroubleshooting(null)}
              onSearchRelated={(q) => {
                b.setShowHelp(true);
                b.setHelpQuery(q);
              }}
            />
          )}
          <section className="app-section chat-section">
            <div className="app-section-header">Natural Language</div>
            <div className="app-section-body chat-section-body">
              <div className="input-row">
                <textarea
                  value={b.input}
                  onChange={(e) => b.setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void b.sendMessage();
                    }
                  }}
                  placeholder={
                    b.coachTab === "explain"
                      ? "lesson 01-hello-playbook · quiz datapaths · explain artifact:*.cef.sourceAddress"
                      : "Describe the playbook you want — e.g. disable Okta user and notify Slack"
                  }
                  rows={2}
                />
                <button
                  type="button"
                  className={`btn btn-primary${b.busy ? " busy" : ""}`}
                  disabled={b.busy}
                  onClick={() => void b.sendMessage()}
                >
                  {b.busy ? "…" : "Build"}
                </button>
              </div>
            </div>
          </section>
        </footer>
      </div>

      <PaneResizeHandle
        orientation="vertical"
        ariaLabel="Drag to widen chat column. Double-click to reset width."
        ariaValueNow={leftPercent ?? undefined}
        onPointerDown={onSplitResize}
        onDoubleClick={resetSplit}
      />

      <PreviewColumn
        variant="build"
        activeTab={b.activePreviewTab}
        onTabChange={b.setActivePreviewTab}
        preview={b.preview}
        source={b.currentSource}
      />
    </div>
  );
}
