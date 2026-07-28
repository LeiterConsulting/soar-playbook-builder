import { NavLink, Outlet, useLocation } from "react-router-dom";
import { EnvironmentMenu } from "../components/EnvironmentMenu";
import { EsBackLink } from "../components/EsBackLink";
import { WorkflowStrip } from "../components/WorkflowStrip";
import { useBuilder } from "../context/BuilderProvider";
import { personaSubtitle, personaTitle } from "../personas";

const NAV_STUDIO = [
  { to: "/build", label: "Build" },
  { to: "/run", label: "Run" },
  { to: "/help", label: "Help" },
];

const NAV_COACH = [
  { to: "/coach", label: "Coach" },
  { to: "/help", label: "Help" },
];

const NAV_ASSISTANT = [
  { to: "/build", label: "Build" },
  { to: "/help", label: "Help" },
];

export function AppLayout() {
  const b = useBuilder();
  const { pathname } = useLocation();
  const showWorkflowStrip =
    (pathname === "/build" || pathname.endsWith("/build")) && b.personaMode === "studio";
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
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `app-nav-link${isActive ? " active" : ""}`}
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {showWorkflowStrip && <WorkflowStrip activeStep={b.workflowStep} />}

      <Outlet />
    </>
  );
}
