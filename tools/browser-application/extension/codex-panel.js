let digest;
async function render() {
  const {codexState: s} = await chrome.storage.local.get("codexState");
  document.getElementById("job").textContent = s ? `${s.company} · ${s.job}` : "等待 Codex 连接";
  document.getElementById("status").textContent = s ? `${s.paused ? "已暂停" : s.phase} ${s.reason || ""}` : "";
  document.getElementById("review").hidden = !s?.pending;
  if (s?.pending) {
    digest = s.pending.digest;
    document.getElementById("summary").textContent = JSON.stringify(s.pending.summary, null, 2);
    const button = document.getElementById("confirm");
    button.disabled = s.paused || s.confirmedDigest === digest;
    button.textContent = s.confirmedDigest === digest ? "已确认，等待 Codex 提交" : "确认本次提交";
  }
}
document.getElementById("pause").onclick = () => chrome.runtime.sendMessage({action: "pause"});
document.getElementById("confirm").onclick = () => chrome.runtime.sendMessage({action: "confirm", digest});
chrome.storage.onChanged.addListener(render);
render();
