import { useEffect } from "react";
import { HelpGuide } from "../components/HelpGuide";
import { SetupAssistant } from "../components/SetupAssistant";
import { TroubleshootingCard } from "../components/TroubleshootingCard";
import { useBuilder } from "../context/BuilderProvider";

export function HelpPage() {
  const b = useBuilder();

  useEffect(() => {
    void b.fetchHelp("");
  }, [b.fetchHelp]);

  useEffect(() => {
    const timer = setTimeout(() => void b.fetchHelp(b.helpQuery), 300);
    return () => clearTimeout(timer);
  }, [b.helpQuery, b.fetchHelp]);

  return (
    <div className="layout help-page">
      <div className="left">
        <div className="help-page-scroll">
          <div className="help-page-main">
            <p className="help-page-lead">
              Expand a section for step-by-step guidance or troubleshooting.
            </p>
            <SetupAssistant />
            <HelpGuide
              query={b.helpQuery}
              onQueryChange={b.setHelpQuery}
              entries={b.helpEntries}
              loading={b.helpLoading}
            />
            {b.troubleshooting && (
              <TroubleshootingCard
                entry={b.troubleshooting}
                onDismiss={() => b.setTroubleshooting(null)}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
