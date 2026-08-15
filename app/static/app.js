const form = document.querySelector("#match-form");
const results = document.querySelector("#results");
const button = form.querySelector("button");

const escapeHtml = (value = "") => value.replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));

function renderMatch(match) {
  const trial = match.trial;
  const locations = trial.locations.slice(0, 3).map(location => [location.facility, location.city, location.state, location.country].filter(Boolean).join(", "));
  return `<article class="trial-card">
    <div class="score">#${match.rank} · ${(match.score * 100).toFixed(1)}% combined match</div>
    <h2><a href="${escapeHtml(trial.source_url)}" target="_blank" rel="noopener">${escapeHtml(trial.title)}</a></h2>
    <div class="meta">
      <span class="pill">${escapeHtml(trial.nct_id)}</span>
      <span class="pill">${escapeHtml(trial.overall_status.replaceAll("_", " "))}</span>
      ${trial.phases.map(phase => `<span class="pill">${escapeHtml(phase)}</span>`).join("")}
    </div>
    <p class="explanation">${escapeHtml(match.explanation)}</p>
    <p class="summary">${escapeHtml(trial.brief_summary.slice(0, 480))}${trial.brief_summary.length > 480 ? "…" : ""}</p>
    <div class="tags">${trial.conditions.slice(0, 4).map(item => `<span class="pill">${escapeHtml(item)}</span>`).join("")}</div>
    ${locations.length ? `<p class="summary"><strong>Locations:</strong> ${locations.map(escapeHtml).join(" · ")}</p>` : ""}
  </article>`;
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  button.disabled = true;
  button.textContent = "Searching…";
  results.innerHTML = '<div class="empty-state"><h2>Retrieving matches</h2><p>Ranking semantic evidence and applying filters.</p></div>';
  const status = document.querySelector("#status").value;
  const ageValue = document.querySelector("#age").value;
  const payload = {
    query: document.querySelector("#query").value,
    age: ageValue ? Number(ageValue) : null,
    condition: document.querySelector("#condition").value || null,
    location: document.querySelector("#location").value || null,
    recruitment_status: status ? [status] : [],
    top_k: 10
  };
  try {
    const response = await fetch("/match", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Search failed");
    results.innerHTML = data.matches.length ? data.matches.map(renderMatch).join("") : '<div class="empty-state"><h2>No matches found</h2><p>Try broadening one or more structured filters.</p></div>';
  } catch (error) {
    results.innerHTML = `<div class="error"><strong>Unable to search.</strong> ${escapeHtml(error.message)}</div>`;
  } finally {
    button.disabled = false;
    button.textContent = "Find matching trials";
  }
});
