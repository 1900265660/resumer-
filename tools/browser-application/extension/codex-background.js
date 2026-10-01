"use strict";
const files = ["shared/resume-schema.js", "shared/diagnostics.js", "shared/field-text.js",
  "shared/field-semantics.js", "shared/fill-runtime.js", "shared/content-bridge.js", "shared/ai-client.js", "content.js"];
chrome.sidePanel.setPanelBehavior({openPanelOnActionClick: true});
// Called only from the local Playwright worker, not exposed to website messages.
globalThis.codexCommand = async (tabId, message) => {
  const state = (await chrome.storage.local.get("codexState")).codexState;
  if (!state || state.tabId !== tabId) throw new Error("unbound_tab");
  if (state.paused && message.action !== "codex:inspect") throw new Error("user_paused");
  const tab = await chrome.tabs.get(tabId);
  if (new URL(tab.url).origin !== state.origin) throw new Error("new_origin_requires_user");
  await chrome.scripting.executeScript({target: {tabId}, files});
  const result = await chrome.tabs.sendMessage(tabId, message);
  if (!result?.ok) throw new Error(result?.error || "extension_no_response");
  return result.data;
};
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL("codex-panel.html"))) return;
  (async () => {
    const {codexState: state} = await chrome.storage.local.get("codexState");
    if (!state) return;
    if (message.action === "pause") {state.paused = true; state.confirmedDigest = null;}
    if (message.action === "confirm" && !state.paused && state.pending?.digest === message.digest) state.confirmedDigest = message.digest;
    await chrome.storage.local.set({codexState: state});
  })().then(() => reply({ok: true}));
  return true;
});
