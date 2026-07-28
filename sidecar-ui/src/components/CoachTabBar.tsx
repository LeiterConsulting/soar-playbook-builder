import type { CoachTab } from "../personas";
import { coachTabLabel } from "../personas";
import { useBuilder } from "../context/BuilderProvider";

const TABS: CoachTab[] = ["respond", "explain", "build"];

export function CoachTabBar() {
  const b = useBuilder();

  return (
    <nav className="coach-tab-bar" aria-label="Coach lanes">
      {TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          className={`coach-tab${b.coachTab === tab ? " coach-tab--active" : ""}`}
          aria-current={b.coachTab === tab ? "page" : undefined}
          onClick={() => b.setCoachTab(tab)}
        >
          {coachTabLabel(tab)}
        </button>
      ))}
      <span className="coach-tab-hint">
        {b.coachTab === "respond" && "Case-aware template suggestions"}
        {b.coachTab === "explain" && "Lessons & quizzes — try lesson 01-hello-playbook"}
        {b.coachTab === "build" && "Templates · NL · import"}
      </span>
    </nav>
  );
}
