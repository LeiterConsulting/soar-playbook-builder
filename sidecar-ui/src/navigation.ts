import { useSyncExternalStore } from "react";

export type AppRoute = "build" | "coach" | "run" | "help";

const APP_ROUTES = new Set<AppRoute>(["build", "coach", "run", "help"]);

export function parseHashRoute(hash: string): AppRoute | null {
  const route = hash.replace(/^#\/?/, "").split(/[/?]/, 1)[0]?.toLowerCase();
  return APP_ROUTES.has(route as AppRoute) ? (route as AppRoute) : null;
}

function subscribeToHashRoute(onStoreChange: () => void): () => void {
  window.addEventListener("hashchange", onStoreChange);
  return () => window.removeEventListener("hashchange", onStoreChange);
}

function readHashRoute(): AppRoute | null {
  return parseHashRoute(window.location.hash);
}

export function useHashRoute(defaultRoute: AppRoute): AppRoute {
  return useSyncExternalStore(subscribeToHashRoute, readHashRoute, () => defaultRoute) ?? defaultRoute;
}

export function routeHref(route: AppRoute): string {
  return `#/${route}`;
}

export function navigateToRoute(route: AppRoute): void {
  window.location.hash = `/${route}`;
}
