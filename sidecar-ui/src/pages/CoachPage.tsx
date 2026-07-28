import { CoachTabBar } from "../components/CoachTabBar";
import { CoachRespondPanel } from "../components/CoachRespondPanel";
import { TutorPanel } from "../components/TutorPanel";
import { BuildPage } from "./BuildPage";
import { useBuilder } from "../context/BuilderProvider";

/** Coach / tutor / assistant persona — Respond · Explain · Build lanes. */
export function CoachPage() {
  const b = useBuilder();

  if (b.coachTab === "build") {
    return (
      <>
        <CoachTabBar />
        <BuildPage />
      </>
    );
  }

  return (
    <>
      <CoachTabBar />
      {b.coachTab === "respond" && <CoachRespondPanel />}
      {b.coachTab === "explain" && <TutorPanel />}
      <BuildPage coachLaneOnly />
    </>
  );
}
