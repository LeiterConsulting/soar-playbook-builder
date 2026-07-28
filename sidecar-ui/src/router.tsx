import { AppLayout } from "./layouts/AppLayout";
import { BuildPage } from "./pages/BuildPage";
import { CoachPage } from "./pages/CoachPage";
import { RunPage } from "./pages/RunPage";
import { HelpPage } from "./pages/HelpPage";
import { useBuilder } from "./context/BuilderProvider";
import { useHashRoute, type AppRoute } from "./navigation";

export function AppRouter() {
  const { personaMode } = useBuilder();
  const defaultRoute: AppRoute =
    personaMode === "coach" || personaMode === "tutor" ? "coach" : "build";
  const route = useHashRoute(defaultRoute);

  let page;
  switch (route) {
    case "coach":
      page = <CoachPage />;
      break;
    case "run":
      page = <RunPage />;
      break;
    case "help":
      page = <HelpPage />;
      break;
    default:
      page = <BuildPage />;
  }

  return (
    <AppLayout route={route}>
      {page}
    </AppLayout>
  );
}
