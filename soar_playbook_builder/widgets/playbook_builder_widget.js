"use strict";

const mcpUrl = document.body.dataset.mcpUrl || "";
const log = (message) => {
  const element = document.getElementById("log");
  element.textContent = `${element.textContent ? `${element.textContent}\n` : ""}${message}`;
};

async function poll(resetSnapshot) {
  const playbookId = document.getElementById("playbook_id").value;
  if (!playbookId) {
    log("Enter playbook ID");
    return;
  }
  const handlerBase = window.location.pathname.replace(/\/widget.*$/, "");
  try {
    const response = await fetch(`${handlerBase}/poll_playbook`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        playbook_id: Number.parseInt(playbookId, 10),
        reset_snapshot: resetSnapshot,
      }),
    });
    const data = await response.json();
    log(JSON.stringify(data, null, 2));
    document
      .getElementById("refresh_banner")
      .classList.toggle("show", Boolean(data.changed));
  } catch (error) {
    log(`Poll failed: ${error}`);
  }
}

document.getElementById("poll").addEventListener("click", () => poll(false));
document.getElementById("reset").addEventListener("click", () => poll(true));

if (mcpUrl) {
  log(`External MCP: ${mcpUrl}`);
  log("Use Cursor with X-MCP-Toolsets: splunk,soar,soar_tutor");
}
