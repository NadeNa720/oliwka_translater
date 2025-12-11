const textarea = document.getElementById("entries");
const translateBtn = document.getElementById("translate-btn");
const resultsEl = document.getElementById("results");
const savedList = document.getElementById("saved-list");
const refreshSavedBtn = document.getElementById("refresh-saved");
const statusBanner = document.getElementById("status-banner");

function createExampleBlock(example) {
  const wrapper = document.createElement("div");
  wrapper.className = "example";
  const source = document.createElement("p");
  source.textContent = example.source;
  const target = document.createElement("p");
  target.className = "muted";
  target.textContent = example.target || "(translation unavailable right now)";
  wrapper.appendChild(source);
  wrapper.appendChild(target);
  return wrapper;
}

function createEntry(entry) {
  const container = document.createElement("div");
  container.className = "entry";
  const heading = document.createElement("h4");
  heading.textContent = `${entry.word} → ${entry.translations || ""}`;
  container.appendChild(heading);

  entry.examples.forEach((ex) => container.appendChild(createExampleBlock(ex)));

  const saveBtn = document.createElement("button");
  saveBtn.textContent = "Save this word";
  saveBtn.className = "secondary";
  saveBtn.addEventListener("click", async () => {
    await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
    saveBtn.textContent = "Saved";
    saveBtn.disabled = true;
    loadSaved();
  });
  container.appendChild(saveBtn);
  return container;
}

function renderResults(grouped) {
  resultsEl.innerHTML = "";
  const order = ["nouns", "verbs", "adjectives", "adverbs", "phrases"];
  const labels = {
    nouns: "Nouns",
    verbs: "Verbs",
    adjectives: "Adjectives",
    adverbs: "Adverbs",
    phrases: "Phrases / other",
  };

  order.forEach((key) => {
    const section = document.createElement("div");
    section.className = "result-block";
    const title = document.createElement("h3");
    title.textContent = labels[key];
    section.appendChild(title);

    const entries = grouped[key] || [];
    if (!entries.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Nothing yet.";
      section.appendChild(empty);
    } else {
      entries.forEach((entry) => section.appendChild(createEntry(entry)));
    }
    resultsEl.appendChild(section);
  });
}

async function translate() {
  const text = textarea.value.trim();
  if (!text) return;
  resultsEl.innerHTML = "<p class='muted'>Translating…</p>";
  const response = await fetch("/api/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = await response.json();
  renderResults(data);
}

async function loadSaved() {
  savedList.innerHTML = "<li class='muted'>Loading…</li>";
  const response = await fetch("/api/saved");
  const data = await response.json();
  savedList.innerHTML = "";
  if (!data.length) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "Nothing saved yet.";
    savedList.appendChild(li);
    return;
  }
  data.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `${item.word} → ${item.translations}`;
    savedList.appendChild(li);
  });
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    if (data.deepseek_configured) {
      statusBanner.textContent = "DeepSeek API key detected: translations ready.";
      statusBanner.classList.remove("warn", "muted");
      statusBanner.classList.add("ok");
    } else {
      statusBanner.textContent =
        "DeepSeek API key is NOT configured. Set DEEPSEEK_API_KEY in Railway/env so translations can run.";
      statusBanner.classList.remove("ok");
      statusBanner.classList.add("warn");
    }
  } catch (error) {
    statusBanner.textContent = "Unable to check DeepSeek key status.";
    statusBanner.classList.add("warn");
  }
}

translateBtn.addEventListener("click", translate);
refreshSavedBtn.addEventListener("click", loadSaved);
loadStatus();
loadSaved();
