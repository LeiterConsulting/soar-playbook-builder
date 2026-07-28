import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

function mount() {
  const rootEl = document.getElementById("root");
  if (!rootEl) return;

  const aiInstructions = rootEl.getAttribute("data-ai-instructions") || "";
  const defaultUiMode = rootEl.getAttribute("data-default-ui-mode") || "studio";

  createRoot(rootEl).render(
    <StrictMode>
      <App aiInstructions={aiInstructions} defaultUiMode={defaultUiMode} />
    </StrictMode>,
  );
}

mount();
