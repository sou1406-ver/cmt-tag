"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("analysis-form");
const comment = byId("comment");
const selectModel = byId("model");
const submit = byId("submit");
const appStatus = byId("app-status");
const dataView = byId("du-lieu");
const analysisSingle = byId("analysis-single");
const crawlView = byId("phan-tich-crawl");
const analysisModes = [...document.querySelectorAll(".analysis-modes a")];
const pipelineLinks = [...document.querySelectorAll(".pipeline-nav a")];
const pipelineSteps = [...document.querySelectorAll(".pipeline-step")];
const commentsForm = byId("comments-form");
const commentsStatus = byId("comments-status");
const commentsPrev = byId("comments-prev");
const commentsNext = byId("comments-next");
const crawlForm = byId("crawl-form");
const crawlStart = byId("crawl-start");
const crawlContinue = byId("crawl-continue");
const crawlStatus = byId("crawl-status");
const crawlModel = byId("crawl-model");
const crawlLabelSubmit = byId("crawl-label-submit");
const crawlLabelStatus = byId("crawl-label-status");
const integer = new Intl.NumberFormat("vi-VN");
const decimal = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 });
const metric = new Intl.NumberFormat("vi-VN", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
const percent = new Intl.NumberFormat("vi-VN", { style: "percent", maximumFractionDigits: 1 });
const sentiments = [
  { id: "POS", name: "Tích cực" },
  { id: "NEG", name: "Tiêu cực" },
  { id: "NEU", name: "Trung tính" },
];
const samples = [
  "Phim hay thật, đoạn cuối xúc động quá. Diễn xuất đỉnh, xem xong vẫn còn nhớ 😭",
  "Kịch bản nhạt, đoạn cuối xử lý vô lý. Xem mệt mà ko đọng lại gì.",
  "Phim có hai phần, p2 chiếu trên Netflix rồi hả m?",
];
const sections = new Map([
  ["phan-tich", "Phân tích"],
  ["quy-trinh", "Quy trình"],
  ["du-lieu", "Dữ liệu"],
  ["thuc-nghiem", "Thực nghiệm"],
]);
let state = null;
let activeRequest = null;
let latestNormalized = "";
let commentsRequest = null;
let commentsFilters = {};
let commentsPage = 0;
let crawlJob = null;
let crawlTimer;
let crawlRevision = 0;
let crawlLabels = null;
let labelingJobId = null;
const busyCrawlPhases = new Set(["opening", "waiting", "collecting"]);

function navigate() {
  const wanted = location.hash.slice(1);
  if (wanted === "main") return;
  const step = byId(wanted);
  const pipelineStep = step?.classList.contains("pipeline-step") ? step : null;
  const crawlMode = wanted === crawlView.id;
  const section = pipelineStep ? "quy-trinh" : sections.has(wanted) ? wanted : "phan-tich";
  for (const id of sections.keys()) byId(id).hidden = id !== section;
  analysisSingle.hidden = crawlMode;
  crawlView.hidden = !crawlMode;
  for (const link of document.querySelectorAll(".nav a")) {
    if (link.hash === "#" + section) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  const activeStep = pipelineStep || pipelineSteps[0];
  for (const panel of pipelineSteps) panel.hidden = panel !== activeStep;
  for (const link of pipelineLinks) {
    if (link.hash === "#" + activeStep.id) link.setAttribute("aria-current", "step");
    else link.removeAttribute("aria-current");
  }
  for (const link of analysisModes) {
    if (link.hash === "#" + (crawlMode ? crawlView.id : "phan-tich")) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  byId("section-name").textContent = sections.get(section);
  if (sections.has(wanted) || crawlMode) {
    window.scrollTo({ top: 0 });
  }
  if (section === "du-lieu" && state?.dataset && !commentsPage && !commentsRequest) void loadComments(1);
  if (crawlMode) void refreshCrawl();
  else clearTimeout(crawlTimer);
}

for (const link of pipelineLinks) {
  link.addEventListener("click", (event) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (location.hash === link.hash) return;
    history.pushState(null, "", link.hash);
    navigate();
  });
}

function scoreRow({ id, name }, value, max, displayed) {
  const row = document.createElement("div");
  row.className = "score";
  row.dataset.tone = id;
  const caption = document.createElement("strong");
  caption.textContent = id;
  const progress = document.createElement("progress");
  progress.max = max;
  progress.value = value;
  progress.setAttribute("aria-label", name + " " + displayed);
  const output = document.createElement("output");
  output.textContent = displayed;
  row.append(caption, progress, output);
  return row;
}

function showDataset(dataset, models, t2Results) {
  byId("dataset-body").hidden = !dataset;
  byId("dataset-empty").hidden = Boolean(dataset);
  for (const field of document.querySelectorAll("[data-dataset-size]")) {
    const size = dataset?.[field.dataset.datasetSize];
    field.textContent = size == null ? "—" : integer.format(size);
  }
  const consensus = dataset?.consensus;
  const deviations = t2Results?.std;
  for (const section of document.querySelectorAll("[data-consensus-visible]")) {
    section.hidden = !consensus;
  }
  for (const field of document.querySelectorAll("[data-t2-status]")) {
    field.textContent = deviations ? "Đã chấm" : "Chờ kết quả ba seed";
  }
  if (consensus) {
    for (const field of document.querySelectorAll("[data-consensus-size]")) {
      field.textContent = integer.format(consensus[field.dataset.consensusSize]);
    }
    document.querySelector("[data-consensus-rate]").textContent = percent.format(consensus.agreed / consensus.annotated);
    byId("current-model-rows").replaceChildren(...models.map(({ id, name }) => {
      const row = document.createElement("tr");
      const heading = document.createElement("th");
      heading.scope = "row";
      heading.textContent = name;
      row.append(heading);
      const scores = deviations ? t2Results.scores[id] : null;
      for (const key of ["accuracy", "macro_precision", "macro_recall", "macro_f1"]) {
        const value = scores?.[key];
        const spread = deviations?.[id]?.[key];
        row.insertCell().textContent = value == null ? "—"
          : spread == null ? metric.format(value) : metric.format(value) + " ± " + metric.format(spread);
      }
      return row;
    }));
    if (deviations) {
      const seeds = byId("t2-seeds");
      seeds.textContent = "Điểm là trung bình ± độ lệch chuẩn mẫu qua ba seed ("
        + t2Results.seeds.join(", ") + ").";
      seeds.hidden = false;
      if (t2Results.confusion_matrices) setupMatrix(t2Results, models);
    }
  }
  if (!dataset) {
    byId("dataset-empty").textContent = "Cần snapshot train V2 đã khóa để xem phân bố.";
    return;
  }
  const groups = dataset.test_groups;
  if (groups.T_original != null && groups.T_supplement != null) {
    byId("test-splits").textContent = integer.format(groups.T_original) + " gốc · " + integer.format(groups.T_supplement) + " bổ sung";
  }
  byId("train-sha").textContent = dataset.train_sha256;
  byId("label-counts").replaceChildren(...sentiments.map((sentiment) => {
    const count = dataset.train_labels[sentiment.id];
    return scoreRow(sentiment, count, dataset.train_size, integer.format(count));
  }));
}

function setupMatrix(results, models) {
  const model = byId("t2-matrix-model");
  const seed = byId("t2-matrix-seed");
  model.replaceChildren(...models.map(({ name, id }) => new Option(name, id)));
  seed.replaceChildren(...results.seeds.map((value) => new Option(String(value), String(value))));
  model.value = models.reduce((best, candidate) =>
    results.scores[candidate.id].macro_f1 > results.scores[best.id].macro_f1 ? candidate : best).id;
  const render = () => {
    const rows = results.confusion_matrices[model.value][seed.value].map((counts, i) => {
      const row = document.createElement("tr");
      const header = document.createElement("th");
      header.scope = "row";
      header.textContent = results.labels[i];
      row.append(header);
      counts.forEach((count, j) => {
        const cell = row.insertCell();
        cell.textContent = integer.format(count);
        if (i === j) cell.className = "matrix-correct";
      });
      return row;
    });
    byId("t2-matrix-rows").replaceChildren(...rows);
  };
  model.onchange = seed.onchange = render;
  render();
  byId("t2-matrix-panel").hidden = false;
}

function commentRow(text, label, tone) {
  const row = document.createElement("li");
  const badge = document.createElement("span");
  badge.className = "tag comment-label";
  badge.textContent = label;
  if (tone) badge.dataset.tone = tone;
  const body = document.createElement("p");
  body.textContent = text;
  row.append(badge, body);
  return row;
}

async function fetchJson(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Máy chủ chưa trả kết quả.");
  return data;
}

async function loadComments(page) {
  commentsRequest?.abort();
  const request = new AbortController();
  commentsRequest = request;
  commentsPrev.disabled = commentsNext.disabled = true;
  commentsStatus.textContent = "Đang tải bình luận…";
  const query = new URLSearchParams({ ...commentsFilters, page });
  try {
    const data = await fetchJson("/api/comments?" + query, { signal: request.signal });
    if (commentsRequest !== request) return;
    commentsPage = data.page;
    byId("comments-list").replaceChildren(...data.comments.map(({ text, label }) => commentRow(text, label, label)));
    commentsStatus.textContent = data.total
      ? integer.format(data.offset + 1) + "–" + integer.format(data.offset + data.comments.length)
        + " / " + integer.format(data.total) + " bình luận"
      : "Không tìm thấy bình luận phù hợp.";
    commentsPrev.disabled = data.page <= 1;
    commentsNext.disabled = data.page >= data.pages;
  } catch (error) {
    if (commentsRequest !== request) return;
    byId("comments-list").replaceChildren();
    commentsStatus.textContent = error.message || "Không tải được bình luận.";
  } finally {
    if (commentsRequest === request) commentsRequest = null;
  }
}

function showCrawlOutput(job) {
  const result = crawlLabels?.id === job?.id ? crawlLabels : null;
  const comments = result?.comments || job?.comments || [];
  const busy = labelingJobId !== null;
  byId("crawl-output").hidden = !comments.length;
  crawlModel.disabled = busy || !crawlModel.options.length;
  crawlLabelSubmit.disabled = busy || !crawlModel.value || !comments.length;
  byId("crawl-comments").replaceChildren(...comments.map(({ text, kind, label }) =>
    commentRow(text, label || (result ? "Chưa gán" : kind === "reply" ? "Phản hồi" : "Bình luận"), label)));
  if (busy) {
    crawlLabelStatus.textContent = state?.models.find((model) => model.id === crawlModel.value)?.provider === "modal"
      ? "Đang gán nhãn trên Modal. Lượt đầu có thể cần chờ máy khởi động…"
      : "Đang gán nhãn bình luận…";
  } else if (result) {
    const counts = sentiments.map(({ id }) => id + " " + integer.format(comments.filter((row) => row.label === id).length));
    crawlLabelStatus.textContent = "Nhãn dự đoán · " + result.model + " · " + counts.join(" · ");
  } else {
    crawlLabelStatus.textContent = "";
  }
}

function showCrawl(job) {
  if (job?.id !== crawlJob?.id) crawlLabels = null;
  crawlJob = job;
  const busy = busyCrawlPhases.has(job?.phase);
  crawlStart.disabled = busy;
  crawlContinue.hidden = job?.phase !== "waiting";
  crawlContinue.disabled = false;
  showCrawlOutput(job);
  const counts = job?.collected == null ? "" : " Thu " + integer.format(job.collected)
    + " dòng, hiển thị " + integer.format(job.comments.length) + " câu có văn bản.";
  const message = job ? job.message + counts : "";
  if (crawlStatus.textContent !== message) crawlStatus.textContent = message;
  clearTimeout(crawlTimer);
  if (busy && !crawlView.hidden) crawlTimer = setTimeout(refreshCrawl, 1500);
}

async function refreshCrawl() {
  const revision = crawlRevision;
  try {
    const job = await fetchJson("/api/crawl");
    if (revision === crawlRevision) showCrawl(job);
  } catch {
    if (revision !== crawlRevision) return;
    crawlStatus.textContent = "Chưa đọc được trạng thái crawler.";
    clearTimeout(crawlTimer);
    if (!crawlView.hidden) crawlTimer = setTimeout(refreshCrawl, 3000);
  }
}

async function labelCrawl() {
  const id = crawlJob.id;
  labelingJobId = id;
  showCrawlOutput(crawlJob);
  let errorMessage = "";
  try {
    const result = await fetchJson("/api/crawl/labels", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, model: crawlModel.value }),
    });
    if (crawlJob?.id === id) crawlLabels = result;
  } catch (error) {
    errorMessage = error.message || "Không gán được nhãn.";
  } finally {
    labelingJobId = null;
    showCrawlOutput(crawlJob);
    if (errorMessage && crawlJob?.id === id) crawlLabelStatus.textContent = errorMessage;
  }
}

async function submitCrawl(path, payload) {
  const revision = ++crawlRevision;
  clearTimeout(crawlTimer);
  crawlStart.disabled = crawlContinue.disabled = true;
  try {
    const job = await fetchJson(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (revision === crawlRevision) showCrawl(job);
  } catch (error) {
    if (revision !== crawlRevision) return;
    showCrawl(crawlJob);
    crawlStatus.textContent = error.message || "Không gửi được yêu cầu crawl.";
  }
}

function setBusy(busy) {
  submit.disabled = busy || state === null;
  form.setAttribute("aria-busy", String(busy));
  submit.textContent = busy ? "Đang phân tích" : state?.models.length ? "Phân tích" : "Chuẩn hóa";
}

function showRuntime() {
  const model = state?.models.find((item) => item.id === selectModel.value);
  const message = byId("model-runtime");
  message.hidden = model?.provider !== "modal";
  message.textContent = "Chạy dự đoán trên Modal. Lượt đầu có thể cần chờ máy khởi động.";
}

function invalidate() {
  activeRequest?.abort();
  activeRequest = null;
  setBusy(false);
  byId("char-count").textContent = integer.format(comment.value.length) + " / 2.000 ký tự";
  byId("form-error").hidden = true;
  byId("result-empty").hidden = false;
  byId("result-data").hidden = true;
  byId("result-tag").hidden = true;
  byId("model-comparison").hidden = true;
  byId("copy").hidden = true;
  byId("copy-status").textContent = "";
  byId("normalized").textContent = "Kết quả chuẩn hóa sẽ hiện ở đây.";
}

function showResult(result, baseline) {
  latestNormalized = result.normalized;
  byId("normalized").textContent = latestNormalized;
  byId("copy").hidden = false;
  byId("copy-status").textContent = result.changed ? "Văn bản đã được chuẩn hóa." : "Văn bản giữ nguyên sau chuẩn hóa.";
  if (!result.label) return;

  const predicted = sentiments.find((item) => item.id === result.label);
  byId("result-empty").hidden = true;
  byId("result-data").hidden = false;
  const badge = byId("result-tag");
  badge.textContent = result.label;
  badge.hidden = false;
  byId("prediction").dataset.label = result.label;
  byId("prediction-name").textContent = predicted.name;
  byId("prediction-model").textContent = result.provider === "modal" ? result.model + " · Modal" : result.model;
  const probability = result.score_kind !== "margin";
  byId("score-kind").textContent = {probability: "Xác suất NB", softmax: "Điểm softmax", margin: "Điểm quyết định SVM"}[result.score_kind];
  byId("score-note").textContent = {
    probability: "Xác suất do mô hình Naive Bayes ước lượng.",
    softmax: "Điểm softmax theo ba lớp, chưa hiệu chỉnh xác suất.",
    margin: "Thanh dài hơn tương ứng với điểm SVM cao hơn. Dấu và giá trị gốc nằm bên phải.",
  }[result.score_kind];
  const radius = Math.max(0.01, ...Object.values(result.scores).map(Math.abs));
  byId("scores").replaceChildren(...sentiments.map((sentiment) => {
    const value = result.scores[sentiment.id];
    return scoreRow(sentiment, probability ? value : value + radius,
      probability ? 1 : 2 * radius, probability ? percent.format(value) : decimal.format(value));
  }));
  if (baseline?.label) {
    const label = sentiments.find((sentiment) => sentiment.id === baseline.label);
    byId("baseline-result").textContent = label.name + " · " + label.id;
    byId("model-comparison").dataset.tone = label.id;
    byId("model-comparison").hidden = false;
  }
}

function requestAnalysis(text, model, signal) {
  return fetchJson("/api/analyze", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, model }), signal,
  });
}

async function analyze() {
  if (!state || !comment.value.trim()) return;
  invalidate();
  const controller = new AbortController();
  activeRequest = controller;
  setBusy(true);
  try {
    const model = state.models.find((item) => item.id === selectModel.value);
    const result = requestAnalysis(comment.value, model?.id || null, controller.signal);
    const baseline = model?.provider === "modal"
      ? requestAnalysis(comment.value, "tfidf_word_svm", controller.signal).catch(() => null)
      : null;
    const [payload, reference] = await Promise.all([result, baseline]);
    if (activeRequest === controller) showResult(payload, reference);
  } catch (error) {
    if (activeRequest !== controller) return;
    const message = byId("form-error");
    message.textContent = error.message || "Không phân tích được bình luận.";
    message.hidden = false;
  } finally {
    if (activeRequest === controller) {
      activeRequest = null;
      setBusy(false);
    }
  }
}

async function initialize() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("Không kết nối được máy chủ.");
    state = await response.json();
    const groups = new Map();
    for (const model of state.models) {
      if (!groups.has(model.provider)) {
        const group = document.createElement("optgroup");
        group.label = model.provider === "modal" ? "BERT trên Modal" : "Baseline trên máy";
        groups.set(model.provider, group);
      }
      groups.get(model.provider).append(new Option(model.name, model.id));
    }
    selectModel.replaceChildren(...groups.values());
    crawlModel.replaceChildren(...Array.from(groups.values(), (group) => group.cloneNode(true)));
    showCrawlOutput(crawlJob);
    if (state.models.length) {
      selectModel.disabled = false;
      appStatus.classList.add("ready");
      appStatus.textContent = state.models.length + " mô hình sẵn sàng";
    } else {
      selectModel.add(new Option("Chưa có snapshot train", ""));
      appStatus.classList.add("missing");
      appStatus.textContent = "Có thể chuẩn hóa câu";
    }
    showDataset(state.dataset, state.models, state.t2_results);
    if (state.dataset && !dataView.hidden && !commentsRequest) void loadComments(1);
    showRuntime();
    setBusy(false);
    if (!comment.value && !byId("phan-tich").hidden && !analysisSingle.hidden) {
      comment.value = samples[0];
      await analyze();
    }
  } catch {
    appStatus.classList.add("missing");
    appStatus.textContent = "Mất kết nối máy chủ";
    byId("dataset-empty").textContent = "Không kết nối được máy chủ.";
  }
}

function searchComments() {
  commentsFilters = Object.fromEntries(new FormData(commentsForm));
  void loadComments(1);
}

commentsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchComments();
});
byId("comments-label").addEventListener("change", searchComments);
commentsPrev.addEventListener("click", () => void loadComments(commentsPage - 1));
commentsNext.addEventListener("click", () => void loadComments(commentsPage + 1));
crawlForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const fields = Object.fromEntries(new FormData(crawlForm));
  void submitCrawl("/api/crawl", { ...fields, limit: Number(fields.limit) });
});
crawlContinue.addEventListener("click", () => {
  if (crawlJob) void submitCrawl("/api/crawl/continue", { id: crawlJob.id });
});
byId("crawl-label-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (crawlJob?.comments?.length && crawlModel.value && labelingJobId === null) void labelCrawl();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void analyze();
});
comment.addEventListener("input", invalidate);
selectModel.addEventListener("change", () => {
  invalidate();
  showRuntime();
});
for (const button of document.querySelectorAll("[data-sample]")) {
  button.addEventListener("click", () => {
    comment.value = samples[Number(button.dataset.sample)];
    if (state) void analyze();
    else invalidate();
  });
}
byId("copy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(latestNormalized);
    byId("copy-status").textContent = "Đã sao chép.";
  } catch {
    byId("copy-status").textContent = "Hãy bôi đen và sao chép văn bản.";
  }
});
window.addEventListener("hashchange", navigate);
navigate();
void initialize();
