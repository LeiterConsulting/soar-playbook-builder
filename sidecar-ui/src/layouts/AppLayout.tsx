import type { ReactNode } from "react";
import { EnvironmentMenu } from "../components/EnvironmentMenu";
import { EsBackLink } from "../components/EsBackLink";
import { WorkflowStrip } from "../components/WorkflowStrip";
import { useBuilder } from "../context/BuilderProvider";
import { routeHref, type AppRoute } from "../navigation";
import { personaSubtitle, personaTitle } from "../personas";

interface AppLayoutProps {
  route: AppRoute;
  children: ReactNode;
}

const NAV_STUDIO: Array<{ to: AppRoute; label: string }> = [
  { to: "build", label: "Build" },
  { to: "run", label: "Run" },
  { to: "help", label: "Help" },
];

const NAV_COACH: Array<{ to: AppRoute; label: string }> = [
  { to: "coach", label: "Coach" },
  { to: "help", label: "Help" },
];

const NAV_ASSISTANT: Array<{ to: AppRoute; label: string }> = [
  { to: "build", label: "Build" },
  { to: "help", label: "Help" },
];

export function AppLayout({ route, children }: AppLayoutProps) {
  const b = useBuilder();
  const showWorkflowStrip = route === "build" && b.personaMode === "studio";
  const nav =
    b.personaMode === "coach" || b.personaMode === "tutor"
      ? NAV_COACH
      : b.personaMode === "assistant"
        ? NAV_ASSISTANT
        : NAV_STUDIO;
  const title = personaTitle(b.personaMode);
  const subtitle = personaSubtitle(b.personaMode);

  return (
    <>
      <header className="app-chrome-header">
        <div className="header-brand">
          <img
            src={`${b.handlerBase}/playbook_builder_logo.png`}
            alt=""
            className="header-logo"
            width={32}
            height={32}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
          <div className="header-brand-text">
            <h1>{title}</h1>
            {subtitle && <span className="header-sub persona-sub">{subtitle}</span>}
          </div>
          {b.usingMocks && <span className="header-sub mock-badge">Mock</span>}
        </div>
        <div className="header-meta">
          <EsBackLink investigationContext={b.investigationContext} eventId={b.urlCtx.eventId} />
          <EnvironmentMenu
            apiGet={b.apiGet}
            bridgeOk={b.bridgeOk}
            bridgeLabel={b.bridgeLabel}
            bridgeTone={b.bridgeTone}
            onRetryBridge={b.checkBridgeStatus}
            onUseTemplate={(patternId) => {
              b.setCurrentPattern(patternId);
              void b.handleScaffold();
            }}
            onFixEnvironment={() => b.handleFixEnvironment()}
            onRunSetupAction={(action) => b.handleSetupAction(action)}
            fixing={b.fixingEnvironment}
            suggestedPattern={b.currentPattern}
            refreshToken={b.envRefreshToken}
          />
          <div className="ctx" title={b.ctxLabel}>
            {b.ctxLabel}
          </div>
        </div>
      </header>

      <nav className="app-nav" aria-label="Main">
        {nav.map(({ to, label }) => (
          <a
            key={to}
            href={routeHref(to)}
            className={`app-nav-link${route === to ? " active" : ""}`}
            aria-current={route === to ? "page" : undefined}
          >
            {label}
          </a>
        ))}
      </nav>

      {showWorkflowStrip && <WorkflowStrip activeStep={b.workflowStep} />}

      <main className="app-main">{children}</main>
    </>
  );
}
