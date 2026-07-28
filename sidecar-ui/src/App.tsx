import { HashRouter } from "react-router-dom";
import { BuilderProvider } from "./context/BuilderProvider";
import { AppRouter } from "./router";
import "./App.css";

interface AppProps {
  aiInstructions: string;
  defaultUiMode: string;
}

export function App({ aiInstructions, defaultUiMode }: AppProps) {
  return (
    <HashRouter>
      <BuilderProvider aiInstructions={aiInstructions} defaultUiMode={defaultUiMode}>
        <AppRouter />
      </BuilderProvider>
    </HashRouter>
  );
}
