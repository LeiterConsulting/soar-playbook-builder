import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { BuildPage } from "./pages/BuildPage";
import { CoachPage } from "./pages/CoachPage";
import { RunPage } from "./pages/RunPage";
import { HelpPage } from "./pages/HelpPage";
import { useBuilder } from "./context/BuilderProvider";

function IndexRedirect() {
  const { personaMode } = useBuilder();
  if (personaMode === "coach" || personaMode === "tutor") {
    return <Navigate to="/coach" replace />;
  }
  return <Navigate to="/build" replace />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<IndexRedirect />} />
        <Route path="build" element={<BuildPage />} />
        <Route path="coach" element={<CoachPage />} />
        <Route path="run" element={<RunPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route path="*" element={<IndexRedirect />} />
      </Route>
    </Routes>
  );
}
