const presetAgents = {
  x: [
    {role: "リサーチ", provider: "gemini", instructions: "市場の論点、一次情報を確認すべき点、読者の疑問を箇条書きで整理する。未検証の事実は断定しない。"},
    {role: "構成", provider: "openai", instructions: "前工程の調査を材料に、読者に届く結論先行の構成案を作る。見出しと各節の要点を明示する。"},
    {role: "文章", provider: "anthropic", instructions: "構成をもとに、自然で具体的な日本語の原稿を書く。根拠のない数字・引用は作らない。"},
    {role: "X投稿", provider: "openai", instructions: "原稿をもとに、読みやすいX投稿を3案作る。出力は投稿本文だけにする。"},
    {role: "炎上チェック", provider: "gemini", instructions: "成果物を安全・信頼性・誤解可能性の観点で確認し、問題箇所と置換案を具体的に示す。"},
    {role: "画像プロンプト", provider: "openai", instructions: "内容に合う、文字なしのSNS用アイキャッチ画像を生成するための詳細な英語プロンプトを書く。"},
  ],
  note: [
    {role: "リサーチ", provider: "gemini", instructions: "テーマの市場背景、読者の疑問、確認すべき一次情報を整理する。"},
    {role: "構成", provider: "openai", instructions: "読者の悩みから解決策へ導くnote記事の構成を作る。"},
    {role: "記事執筆", provider: "anthropic", instructions: "構成をもとに、note記事として読み応えのある本文を書く。"},
    {role: "編集・事実確認", provider: "gemini", instructions: "記事を編集し、事実性・読みやすさ・誤解の余地を確認する。"},
    {role: "タイトル・アイキャッチ", provider: "openai", instructions: "記事タイトル案と、文字なしのアイキャッチ用英語プロンプトを作る。"},
  ],
  line: [
    {role: "ヒアリング整理", provider: "gemini", instructions: "依頼内容から確認すべき業務課題とヒアリング項目を整理する。"},
    {role: "業務分析", provider: "openai", instructions: "現状業務、課題、KPI、LINE自動化の余地を分析する。"},
    {role: "導線設計", provider: "openai", instructions: "友だち追加から成約までのLINE導線を設計する。"},
    {role: "ステップ配信設計", provider: "anthropic", instructions: "配信シナリオ、メッセージ、条件分岐を具体化する。"},
    {role: "提案書", provider: "anthropic", instructions: "クライアント提出用の提案書として、目的・施策・期待効果・進行をまとめる。"},
    {role: "リスク確認", provider: "gemini", instructions: "個人情報、誤認表現、運用リスクを確認し改善案を示す。"},
  ],
};
const builtInTemplates = [
  {id: "x", name: "AI活用術のX投稿", goal: "AI活用術のX投稿を作る", brief: "AI活用を仕事に活かしたい個人事業主向けに、初心者にも分かる親しみやすいX投稿を作りたい。"},
  {id: "note", name: "note記事の構成", goal: "note記事の構成を作る", brief: "カスタムGPT販売の始め方について、読者の悩みから解決策へ導くnote記事の構成を作りたい。"},
  {id: "line", name: "LINE自動化の提案書", goal: "LINE自動化の提案書を作る", brief: "クライアントのLINE業務を自動化するためのヒアリング、導線、ステップ配信、提案書を作りたい。"},
];
let roles = presetAgents.x.map((agent) => agent.role);
let selectedTemplate = "x";
let activeAgents = [];
let customTemplates = JSON.parse(localStorage.getItem("rucchi-fugu-custom-templates") || "[]");
const steps = document.querySelector("#steps");
const activity = document.querySelector("#activity");
const outputs = document.querySelector("#outputs");
const status = document.querySelector("#n8n-status");
const runCost = document.querySelector("#run-cost");
document.querySelector(".n8n-select")?.remove();
const defaultProviders = Object.fromEntries(presetAgents.x.map((agent) => [agent.role, agent.provider]));
const selectedProviders = {...defaultProviders, ...JSON.parse(localStorage.getItem("rucchi-fugu-agent-settings") || "{}")};
const defaultModels = {"記事執筆": "claude-sonnet-4-5-20250929", "ステップ配信設計": "claude-sonnet-4-5-20250929", "提案書": "claude-sonnet-4-5-20250929"};
const selectedModels = {...defaultModels, ...JSON.parse(localStorage.getItem("rucchi-fugu-model-settings") || "{}")};
let n8nEnabled = localStorage.getItem("rucchi-fugu-n8n-enabled") === "true";
let xaiLiveSearch = localStorage.getItem("rucchi-fugu-xai-live-search") === "true";
const themeToggle = document.querySelector("#theme-toggle");
const savedTheme = localStorage.getItem("rucchi-fugu-theme") || "dark";

function applyTheme(theme) {
  document.body.dataset.theme = theme;
  themeToggle.querySelector("span").textContent = theme === "dark" ? "ライト表示" : "ダーク表示";
  localStorage.setItem("rucchi-fugu-theme", theme);
}

applyTheme(savedTheme);
themeToggle.addEventListener("click", () => applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark"));

function escapeHtml(value) {
  return String(value || "").replace(/[&<>'"]/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[character]);
}
function cloneAgents(agents) { return agents.map((agent) => ({...agent})); }
function formatUsd(value) { return `US$${Number(value || 0).toFixed(4)}`; }
function providerOptions(selected) {
  return [["openai", "ChatGPT"], ["anthropic", "Claude"], ["gemini", "Gemini"], ["xai", "Grok"]]
    .map(([value, label]) => `<option value="${value}" ${selected === value ? "selected" : ""}>${label}</option>`).join("");
}
function modelOptions(provider, selected) {
  const models = provider === "anthropic"
    ? [["", "Claude Haiku 4.5（標準）"], ["claude-sonnet-4-5-20250929", "Claude Sonnet 4.5（重要な長文）"]]
    : [["", "標準モデルを使用"]];
  return models.map(([value, label]) => `<option value="${value}" ${selected === value ? "selected" : ""}>${label}</option>`).join("");
}
async function persistUserSettings() {
  const body = {providers: selectedProviders, model_overrides: selectedModels, n8n_enabled: n8nEnabled, xai_live_search: xaiLiveSearch, custom_templates: customTemplates};
  localStorage.setItem("rucchi-fugu-agent-settings", JSON.stringify(selectedProviders));
  localStorage.setItem("rucchi-fugu-model-settings", JSON.stringify(selectedModels));
  localStorage.setItem("rucchi-fugu-n8n-enabled", String(n8nEnabled));
  localStorage.setItem("rucchi-fugu-xai-live-search", String(xaiLiveSearch));
  localStorage.setItem("rucchi-fugu-custom-templates", JSON.stringify(customTemplates));
  await fetch("/api/user-settings", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
}
fetch("/api/user-settings").then((response) => response.json()).then((saved) => {
  Object.assign(selectedProviders, saved.providers || {});
  Object.assign(selectedModels, saved.model_overrides || {});
  if (typeof saved.n8n_enabled === "boolean") n8nEnabled = saved.n8n_enabled;
  if (typeof saved.xai_live_search === "boolean") xaiLiveSearch = saved.xai_live_search;
  if (Array.isArray(saved.custom_templates)) customTemplates = saved.custom_templates;
}).catch(() => {});
fetch("/api/costs").then((response) => response.json()).then((costs) => {
  document.querySelector("#header-cost").textContent = formatUsd(costs.monthly_total_usd);
}).catch(() => {});

document.head.insertAdjacentHTML("beforeend", `<style>
#app-dialog{width:min(720px,92vw);max-height:88vh;border:0;border-radius:14px;padding:24px;box-shadow:0 25px 70px #061d3866}.dialog-head{display:flex;justify-content:space-between;align-items:center;gap:20px}.agent-row{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-bottom:1px solid #dbe4ec}.agent-row select{width:160px;padding:8px;border:1px solid #9cafc0;border-radius:6px}.template-toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:14px 0}.template-list{display:grid;gap:10px}.template-card{border:1px solid #d5e0ea;border-radius:9px;padding:14px}.template-card h3{margin:0 0 4px}.template-card p{margin:0;color:#62758a;font-size:13px}.template-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.template-actions button,.template-toolbar button,.template-agent button{border:1px solid #8ba1b8;background:#fff;color:#0b2c50;border-radius:6px;padding:7px 10px;font-weight:700;cursor:pointer}.template-toolbar button{background:#09294a;color:#fff}.template-form label{display:grid;gap:6px;margin:13px 0;font-weight:700;color:#173451}.template-form input,.template-form textarea,.template-agent select{font:inherit;border:1px solid #9cafc0;border-radius:6px;padding:9px}.template-form textarea{min-height:78px;resize:vertical}.template-agent{display:grid;grid-template-columns:1fr 150px auto;gap:8px;border:1px solid #d5e0ea;border-radius:8px;padding:12px;margin:10px 0}.template-agent textarea{grid-column:1/-1;min-height:68px}.template-agent button{grid-column:3}.template-form small{color:#60758c}.template-form-message{color:#bd2934;font-weight:700}@media(max-width:620px){.template-agent{grid-template-columns:1fr}.template-agent button{grid-column:auto}.agent-row{align-items:flex-start;gap:10px}}</style>`);
document.head.insertAdjacentHTML("beforeend", "<style>#app-dialog{background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:12px}#app-dialog .agent-row{border-bottom-color:var(--line)}#app-dialog .agent-row select{background:var(--surface-raised);color:var(--text);border-color:var(--line-strong)}#app-dialog .template-card,#app-dialog .template-agent{border-color:var(--line);background:var(--surface)}#app-dialog .template-card p,#app-dialog .template-form small{color:var(--muted)}#app-dialog .template-actions button,#app-dialog .template-toolbar button,#app-dialog .template-agent button{background:var(--surface-soft);color:var(--text);border-color:var(--line-strong)}#app-dialog .template-form label{color:var(--text)}#app-dialog .template-form input,#app-dialog .template-form textarea,#app-dialog .template-agent select{background:var(--surface-raised);color:var(--text);border-color:var(--line-strong)}#app-dialog .dialog-item{background:var(--surface-soft);color:var(--text);border-color:var(--line-strong)}.cost-list{display:grid;gap:8px;margin-top:12px}.cost-list div{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:7px}</style>");
const historySelect = document.querySelector("#history-select");
const dialog = document.querySelector("#app-dialog");
const dialogTitle = document.querySelector("#dialog-title");
const dialogBody = document.querySelector("#dialog-body");
function openDialog(title, html) { dialogTitle.textContent = title; dialogBody.innerHTML = html; dialog.showModal(); }
document.querySelector("#dialog-close").addEventListener("click", () => dialog.close());
function loadProjects() { return JSON.parse(localStorage.getItem("rucchi-fugu-projects") || "[]"); }
function saveProjects(items) { localStorage.setItem("rucchi-fugu-projects", JSON.stringify(items)); }
function saveCurrentProject() {
  const projects = loadProjects(); let id = localStorage.getItem("rucchi-fugu-current-project"); let project = projects.find((item) => item.id === id);
  if (!project) { id = crypto.randomUUID(); project = {id, createdAt: new Date().toISOString()}; projects.unshift(project); localStorage.setItem("rucchi-fugu-current-project", id); }
  project.name = document.querySelector("#goal").value || "名称未設定のプロジェクト"; project.goal = document.querySelector("#goal").value; project.brief = document.querySelector("#brief").value; project.updatedAt = new Date().toISOString(); saveProjects(projects); return project;
}
function refreshHistorySelect() {
  const projectId = localStorage.getItem("rucchi-fugu-current-project");
  const history = JSON.parse(localStorage.getItem("rucchi-fugu-history") || "[]").filter((item) => !projectId || item.projectId === projectId);
  historySelect.innerHTML = '<option value="">◷　履歴を呼び出す</option>';
  history.forEach((item) => {
    const option = document.createElement("option"); option.value = String(JSON.parse(localStorage.getItem("rucchi-fugu-history") || "[]").indexOf(item)); option.textContent = `${new Date(item.createdAt || 0).toLocaleString("ja-JP")}　${(item.brief || "").slice(0, 24)}`; historySelect.append(option);
  });
}
historySelect.addEventListener("change", () => {
  if (historySelect.value === "") return;
  const item = JSON.parse(localStorage.getItem("rucchi-fugu-history") || "[]")[Number(historySelect.value)]; document.querySelector("#goal").value = item.goal; document.querySelector("#brief").value = item.brief; historySelect.value = "";
});
refreshHistorySelect();

function templateAgentEditor(agent) {
  return `<section class="template-agent" data-template-agent><input data-template-agent-role maxlength="80" value="${escapeHtml(agent.role)}" placeholder="担当名（例：リサーチ）"><select data-template-agent-provider>${providerOptions(agent.provider)}</select><button type="button" data-remove-template-agent>削除</button><textarea data-template-agent-instructions maxlength="2000" placeholder="この担当に任せること">${escapeHtml(agent.instructions)}</textarea></section>`;
}
function readAgentsFromDialog() {
  return [...dialogBody.querySelectorAll("[data-template-agent]")].map((row) => ({
    role: row.querySelector("[data-template-agent-role]").value.trim(),
    provider: row.querySelector("[data-template-agent-provider]").value,
    instructions: row.querySelector("[data-template-agent-instructions]").value.trim(),
  }));
}
function openTemplateEditor(template = {id: "", name: "", goal: "", brief: "", agents: [{role: "リサーチ", provider: "openai", instructions: "依頼内容を整理し、必要な情報と論点をまとめる。"}]}) {
  openDialog(template.id ? "テンプレートを編集" : "新しいテンプレート", `<div class="template-form"><label>テンプレート名<input data-template-name maxlength="80" value="${escapeHtml(template.name)}" placeholder="例：メルマガ原稿"></label><label>制作の目的<input data-template-goal maxlength="300" value="${escapeHtml(template.goal)}" placeholder="例：週刊メルマガを作る"></label><label>依頼内容の初期文<textarea data-template-brief required minlength="10" maxlength="8000" placeholder="テンプレートを選んだ時に入れる依頼文">${escapeHtml(template.brief)}</textarea></label><label>AIチーム<small>担当名・使用AI・担当指示を自由に設定できます。</small></label><div data-template-agent-list>${template.agents.map(templateAgentEditor).join("")}</div><div class="template-actions"><button type="button" data-add-template-agent>＋ 担当を追加</button><button type="button" data-save-template="${escapeHtml(template.id)}">テンプレートを保存</button></div><p class="template-form-message" id="template-form-message"></p></div>`);
}
function openTemplatesDialog() {
  const builtIns = builtInTemplates.map((template) => `<article class="template-card"><h3>${escapeHtml(template.name)}</h3><p>標準テンプレート・${presetAgents[template.id].length}人チーム</p><div class="template-actions"><button data-template-use="${template.id}">使う</button><button data-template-copy="${template.id}">複製して編集</button></div></article>`).join("");
  const customs = customTemplates.length ? customTemplates.map((template) => `<article class="template-card"><h3>${escapeHtml(template.name)}</h3><p>${template.agents.length}人チーム・${escapeHtml(template.goal)}</p><div class="template-actions"><button data-template-use="custom:${template.id}">使う</button><button data-template-edit="${template.id}">編集</button><button data-template-delete="${template.id}">削除</button></div></article>`).join("") : "<p>まだ追加テンプレートはありません。</p>";
  openDialog("テンプレート", `<div class="template-toolbar"><b>標準テンプレート</b><button data-template-new>＋ 新しいテンプレート</button></div><div class="template-list">${builtIns}</div><div class="template-toolbar"><b>追加したテンプレート</b></div><div class="template-list">${customs}</div>`);
}
function openAgentsDialog() {
  const rows = roles.map((role) => {
    const provider = selectedProviders[role] || "openai";
    return `<label class="agent-row"><b>${escapeHtml(role)}<small>${provider === "anthropic" ? "重要な長文にはSonnetを選べます" : "使用AIを選択"}</small></b><span class="agent-controls"><select data-agent-role="${escapeHtml(role)}">${providerOptions(provider)}</select><select data-agent-model="${escapeHtml(role)}">${modelOptions(provider, selectedModels[role] || "")}</select></span></label>`;
  }).join("");
  openDialog("AIエージェント設定", `${rows}<label class="search-switch"><input type="checkbox" data-xai-live-search ${xaiLiveSearch ? "checked" : ""}><span><b>GrokのWeb／X検索を使う</b><small>Grok担当だけが、最新のWeb情報とX上の投稿を検索できます。検索ツールの利用分は別途課金される場合があります。</small></span></label>`);
}
function applyTemplate(template, isCustom = false) {
  selectedTemplate = isCustom ? "custom" : template.id;
  activeAgents = isCustom ? cloneAgents(template.agents) : [];
  const agents = isCustom ? activeAgents : presetAgents[template.id];
  roles = agents.map((agent) => agent.role);
  agents.forEach((agent) => { selectedProviders[agent.role] = agent.provider; });
  document.querySelector("#goal").value = template.goal;
  document.querySelector("#brief").value = template.brief;
  renderSteps();
  persistUserSettings().catch(() => {});
}

document.querySelectorAll("[data-action]").forEach((link) => link.addEventListener("click", async (event) => {
  event.preventDefault(); const action = link.dataset.action; const history = JSON.parse(localStorage.getItem("rucchi-fugu-history") || "[]");
  if (action === "dashboard") return document.querySelector("#workspace").scrollIntoView({behavior: "smooth"});
  if (action === "projects") { const projects = loadProjects(); return openDialog("プロジェクト", projects.length ? projects.map((item, index) => `<button class="dialog-item" data-project="${index}">${escapeHtml(item.name)}</button>`).join("") : "<p>まだプロジェクトはありません。</p>"); }
  if (action === "history") { const projectId = localStorage.getItem("rucchi-fugu-current-project"); const projectHistory = history.filter((item) => !projectId || item.projectId === projectId); return openDialog("実行履歴", projectHistory.length ? projectHistory.map((item) => `<button class="dialog-item" data-history="${history.indexOf(item)}">${new Date(item.createdAt || 0).toLocaleString("ja-JP")}　${escapeHtml((item.brief || "").slice(0, 42))}</button>`).join("") : "<p>このプロジェクトの実行履歴はありません。</p>"); }
  if (action === "templates") return openTemplatesDialog();
  if (action === "agents") return openAgentsDialog();
  if (action === "n8n") { const saved = await fetch("/api/user-settings").then((response) => response.json()).catch(() => ({})); if (typeof saved.n8n_enabled === "boolean") n8nEnabled = saved.n8n_enabled; return openDialog("n8n連携", `<p>${escapeHtml(status.textContent)}</p><label class="agent-row"><b>実行後に自動送信</b><input type="checkbox" data-n8n-toggle ${n8nEnabled ? "checked" : ""}></label><p>オンにした場合だけ、次回実行の成果物をn8nへ送信します。</p><button class="dialog-item" data-save-n8n>設定を保存</button><small id="n8n-save-result"></small>`); }
  if (action === "costs") { const costs = await fetch("/api/costs").then((response) => response.json()); const providers = Object.entries(costs.provider_totals_usd || {}).map(([provider, amount]) => `<div><b>${escapeHtml({openai: "ChatGPT", anthropic: "Claude", gemini: "Gemini", xai: "Grok"}[provider] || provider)}</b><span>${formatUsd(amount)}</span></div>`).join("") || "<p>まだ概算料金の記録はありません。</p>"; return openDialog("API料金（概算）", `<p>当月合計（${escapeHtml(costs.month || "")}）：<b>${formatUsd(costs.monthly_total_usd)}</b></p><p>AI別の累計料金</p><div class="cost-list">${providers}</div><small>各社の標準トークン単価を使用した概算です。実際の請求額ではありません。</small>`); }
  if (action === "settings") { const health = await fetch("/health").then((response) => response.json()); return openDialog("接続設定", `<p>ChatGPT：接続済み</p><p>Claude：${health.providers.anthropic ? "設定済み" : "未設定"}</p><p>Gemini：${health.providers.gemini ? "設定済み" : "未設定"}</p><p>Grok：${health.providers.xai ? `設定済み（${escapeHtml(health.models.xai)}）` : "未設定"}</p>`); }
}));

dialogBody.addEventListener("click", (event) => {
  const button = event.target.closest("button"); if (!button) return;
  if (button.dataset.saveN8n !== undefined) { persistUserSettings().then(() => { document.querySelector("#n8n-save-result").textContent = "保存しました"; }); return; }
  if (button.dataset.templateNew !== undefined) return openTemplateEditor();
  if (button.dataset.templateCopy !== undefined) { const source = builtInTemplates.find((template) => template.id === button.dataset.templateCopy); return openTemplateEditor({...source, id: "", name: `${source.name}（コピー）`, agents: cloneAgents(presetAgents[source.id])}); }
  if (button.dataset.templateEdit !== undefined) { const template = customTemplates.find((item) => item.id === button.dataset.templateEdit); if (template) openTemplateEditor(template); return; }
  if (button.dataset.templateDelete !== undefined) { if (window.confirm("このテンプレートを削除しますか？")) { customTemplates = customTemplates.filter((item) => item.id !== button.dataset.templateDelete); persistUserSettings().then(openTemplatesDialog); } return; }
  if (button.dataset.templateUse !== undefined) { const id = button.dataset.templateUse; if (id.startsWith("custom:")) { const template = customTemplates.find((item) => item.id === id.slice(7)); if (template) applyTemplate(template, true); } else { const template = builtInTemplates.find((item) => item.id === id); if (template) applyTemplate(template); } dialog.close(); return; }
  if (button.dataset.addTemplateAgent !== undefined) { const draft = {id: "", name: dialogBody.querySelector("[data-template-name]").value, goal: dialogBody.querySelector("[data-template-goal]").value, brief: dialogBody.querySelector("[data-template-brief]").value, agents: [...readAgentsFromDialog(), {role: "", provider: "openai", instructions: ""}]}; return openTemplateEditor(draft); }
  if (button.dataset.removeTemplateAgent !== undefined) { const draft = {id: "", name: dialogBody.querySelector("[data-template-name]").value, goal: dialogBody.querySelector("[data-template-goal]").value, brief: dialogBody.querySelector("[data-template-brief]").value, agents: readAgentsFromDialog()}; const index = [...dialogBody.querySelectorAll("[data-remove-template-agent]")].indexOf(button); draft.agents.splice(index, 1); return openTemplateEditor(draft); }
  if (button.dataset.saveTemplate !== undefined) {
    const template = {id: button.dataset.saveTemplate || crypto.randomUUID(), name: dialogBody.querySelector("[data-template-name]").value.trim(), goal: dialogBody.querySelector("[data-template-goal]").value.trim(), brief: dialogBody.querySelector("[data-template-brief]").value.trim(), agents: readAgentsFromDialog()};
    const message = document.querySelector("#template-form-message");
    if (!template.name || !template.goal || template.brief.length < 10 || !template.agents.length || template.agents.some((agent) => !agent.role || !agent.instructions)) { message.textContent = "テンプレート名・目的・10文字以上の依頼内容・各担当の設定を入力してください。"; return; }
    const existingIndex = customTemplates.findIndex((item) => item.id === template.id); if (existingIndex >= 0) customTemplates[existingIndex] = template; else customTemplates.unshift(template);
    persistUserSettings().then(openTemplatesDialog).catch(() => { message.textContent = "保存できませんでした。サーバーの起動状態を確認してください。"; }); return;
  }
  const history = JSON.parse(localStorage.getItem("rucchi-fugu-history") || "[]");
  if (button.dataset.history !== undefined) { const item = history[Number(button.dataset.history)]; document.querySelector("#goal").value = item.goal; document.querySelector("#brief").value = item.brief; if (item.projectId) localStorage.setItem("rucchi-fugu-current-project", item.projectId); }
  if (button.dataset.project !== undefined) { const item = loadProjects()[Number(button.dataset.project)]; document.querySelector("#goal").value = item.goal; document.querySelector("#brief").value = item.brief; localStorage.setItem("rucchi-fugu-current-project", item.id); refreshHistorySelect(); }
  dialog.close();
});
dialogBody.addEventListener("change", (event) => {
  if (event.target.dataset.agentRole) { selectedProviders[event.target.dataset.agentRole] = event.target.value; persistUserSettings(); openAgentsDialog(); }
  if (event.target.dataset.agentModel) { selectedModels[event.target.dataset.agentModel] = event.target.value; persistUserSettings(); }
  if (event.target.dataset.n8nToggle) { n8nEnabled = event.target.checked; persistUserSettings(); }
  if (event.target.dataset.xaiLiveSearch !== undefined) { xaiLiveSearch = event.target.checked; persistUserSettings(); }
});
document.querySelector("#new-project").addEventListener("click", () => { localStorage.removeItem("rucchi-fugu-current-project"); refreshHistorySelect(); document.querySelector("#goal").value = ""; document.querySelector("#brief").value = ""; outputs.innerHTML = ""; document.querySelector("#empty").hidden = false; activity.innerHTML = "<li>新しいプロジェクトを作成しました。依頼内容を入力してください。</li>"; window.scrollTo({top: 0, behavior: "smooth"}); });
function stepIcon(role) {
  const paths = {
    "リサーチ": '<circle cx="12" cy="12" r="5.5"/><path d="m16 16 4 4"/>',
    "構成": '<path d="M6 4h9l3 3v13H6z"/><path d="M9 10h6M9 14h6M9 18h4"/>',
    "文章": '<path d="m6 18 1.7-4.2L16.5 5a2.2 2.2 0 0 1 3.1 3.1l-8.8 8.8L6 18Z"/><path d="m14.8 6.7 2.5 2.5"/>',
    "X投稿": '<path d="M6 5h4.2l3.1 4.5L17.6 5H20l-5.6 6.4L20 19h-4.2l-3.4-4.9L8 19H5.6l5.7-6.5L6 5Z"/>',
    "炎上チェック": '<path d="M12 3.8 19 6.5v5.2c0 4.4-2.9 7.4-7 8.5-4.1-1.1-7-4.1-7-8.5V6.5l7-2.7Z"/><path d="m9.2 12 1.8 1.8 3.8-4"/>',
    "画像プロンプト": '<rect x="4.5" y="5" width="15" height="14" rx="2"/><circle cx="9" cy="10" r="1.4"/><path d="m6.5 16 3.7-3.5 2.8 2.4 2.1-2 2.3 3.1"/>',
    "記事執筆": '<path d="M6 4h12v16H6z"/><path d="M9 9h6M9 13h6M9 17h4"/>',
    "編集・事実確認": '<path d="m6 18 1.7-4.2L16.5 5a2.2 2.2 0 0 1 3.1 3.1l-8.8 8.8L6 18Z"/><path d="m14.8 6.7 2.5 2.5M7 6.5h5"/>',
    "タイトル・アイキャッチ": '<rect x="4.5" y="5" width="15" height="14" rx="2"/><path d="M7.5 16 11 12.5l2.6 2.2 2-1.9 1.9 3"/>',
    "ヒアリング整理": '<path d="M5 5h14v11H9l-4 3V5Z"/><path d="M8 9h8M8 12h5"/>',
    "業務分析": '<path d="M5 19V11M10 19V6M15 19v-9M20 19V4"/>',
    "導線設計": '<circle cx="6" cy="7" r="2"/><circle cx="18" cy="17" r="2"/><path d="M8 7h5a3 3 0 0 1 3 3v3"/>',
    "ステップ配信設計": '<path d="M5 6h14M5 12h14M5 18h14"/><circle cx="7" cy="6" r="1" fill="currentColor"/><circle cx="7" cy="12" r="1" fill="currentColor"/><circle cx="7" cy="18" r="1" fill="currentColor"/>',
    "提案書": '<path d="M6 4h9l3 3v13H6z"/><path d="M9 11h6M9 15h4"/>',
    "リスク確認": '<path d="M12 3.8 19 6.5v5.2c0 4.4-2.9 7.4-7 8.5-4.1-1.1-7-4.1-7-8.5V6.5l7-2.7Z"/><path d="M12 9v4M12 16h.01"/>'
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[role] || paths["構成"]}</svg>`;
}
function renderSteps() { steps.innerHTML = ""; roles.forEach((role, index) => { const item = document.querySelector("#step-template").content.cloneNode(true); item.querySelector("b").textContent = String(index + 1).padStart(2, "0"); item.querySelector("i").innerHTML = stepIcon(role); item.querySelector("strong").textContent = role; steps.append(item); }); }
renderSteps();
function addActivity(message) { const item = document.createElement("li"); item.textContent = message; activity.append(item); }

document.querySelector("#run-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const button = event.currentTarget.querySelector("button"); button.disabled = true; button.textContent = "チームを稼働中…"; outputs.innerHTML = ""; document.querySelector("#empty").hidden = true; activity.innerHTML = ""; status.textContent = "処理中"; document.querySelectorAll(".step small").forEach((node) => (node.textContent = "待機中")); addActivity("チームを招集しました。順番に成果物を引き継ぎます。");
  try {
    const response = await fetch("/api/runs", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({brief: document.querySelector("#brief").value, goal: document.querySelector("#goal").value, providers: selectedProviders, model_overrides: selectedModels, template: selectedTemplate, agents: activeAgents, send_to_n8n: n8nEnabled, xai_live_search: xaiLiveSearch})});
    const data = await response.json(); if (!response.ok || data.status !== "completed") throw new Error(data.n8n?.message || "実行に失敗しました");
    const project = saveCurrentProject(); const history = JSON.parse(localStorage.getItem("rucchi-fugu-history") || "[]"); history.unshift({goal: document.querySelector("#goal").value, brief: document.querySelector("#brief").value, projectId: project.id, projectName: project.name, createdAt: new Date().toISOString()}); localStorage.setItem("rucchi-fugu-history", JSON.stringify(history.slice(0, 10))); refreshHistorySelect();
    data.outputs.forEach((output, index) => { document.querySelectorAll(".step small")[index].textContent = `${output.provider} / ${output.model} 完了`; addActivity(`${output.role}が成果物を渡しました。`); const article = document.createElement("article"); article.innerHTML = `<h3>${escapeHtml(output.role)}<span>${escapeHtml(output.provider)} / ${escapeHtml(output.model)}</span><em>生成内容</em></h3><pre style="display:block !important"></pre>`; article.querySelector("pre").textContent = output.content; outputs.append(article); }); status.textContent = data.n8n.message; runCost.textContent = `今回の実行料金：${formatUsd(data.costs?.run_total_usd)}（概算）\n当月合計：${formatUsd(data.costs?.monthly_total_usd)}（概算）`; document.querySelector("#header-cost").textContent = formatUsd(data.costs?.monthly_total_usd);
  } catch (error) { addActivity(`停止: ${error.message}`); status.textContent = "送信されていません"; }
  finally { button.disabled = false; button.textContent = "チームを動かす"; }
});
