// Powers the "Try it" forms that the openapi shortcode renders.
//
// Each form describes one API operation. On submit, this script builds the
// request from the form fields, sends it, and shows the response.
//
// Where the request goes depends on the mode set in the shortcode:
//   "mock"  A mock script (window.openapiMock) answers in the browser.
//   "live"  The request goes to the API server with fetch(). If the server
//           is unreachable, the mock answers instead and the result says so.
(() => {
  "use strict";

  const configElement = document.getElementById("oa-config");
  if (!configElement) return;
  const config = JSON.parse(configElement.textContent);

  // fetch() reports no status text over HTTP/2, so supply the phrases here.
  const STATUS_TEXT = {
    200: "OK",
    201: "Created",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
  };

  // The response headers worth showing. Browsers hide most others from
  // cross-origin scripts unless the server exposes them.
  const SHOWN_HEADERS = ["content-type", "location", "retry-after"];

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Collects the form fields into a request description.
  function readForm(form) {
    const request = {
      operationId: form.dataset.oaOperation,
      method: form.dataset.oaMethod,
      pathParams: {},
      query: {},
      headers: {},
      body: null,
    };

    for (const field of form.querySelectorAll("[data-oa-in]")) {
      const name = field.dataset.oaName;
      const value = field.value.trim();
      switch (field.dataset.oaIn) {
        case "path":
          request.pathParams[name] = value;
          break;
        case "query":
          if (value) request.query[name] = value;
          break;
        case "header":
          if (value) request.headers[name] = value;
          break;
        case "body":
          request.body = field.value;
          request.headers["Content-Type"] = field.dataset.oaType;
          break;
      }
    }

    const path = form.dataset.oaPath.replace(/\{(\w+)\}/g, (_, name) =>
      encodeURIComponent(request.pathParams[name] ?? ""),
    );
    const query = new URLSearchParams(request.query).toString();
    request.url = config.server + path + (query ? `?${query}` : "");
    return request;
  }

  function askMock(request, source) {
    if (typeof window.openapiMock !== "function") {
      throw new Error("No mock is available for this API.");
    }
    return { ...window.openapiMock(request, config), source };
  }

  async function askServer(request) {
    const started = performance.now();
    const response = await fetch(request.url, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });
    const text = await response.text();
    const elapsed = Math.round(performance.now() - started);

    const headers = {};
    for (const name of SHOWN_HEADERS) {
      const value = response.headers.get(name);
      if (value) headers[name] = value;
    }

    let body = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }
    return { status: response.status, headers, body, elapsed, source: "live" };
  }

  async function send(request) {
    if (config.mode !== "live") return askMock(request, "mock");
    try {
      return await askServer(request);
    } catch (error) {
      // fetch() rejects only when no response arrived: the server is down,
      // DNS failed, or the browser blocked the call.
      if (typeof window.openapiMock !== "function") throw error;
      return askMock(request, "fallback");
    }
  }

  // Finds rows to show as a table: the body itself when it's a list of
  // objects, or the first property that is one.
  function findRows(body) {
    const isRows = (value) =>
      Array.isArray(value) &&
      value.length > 0 &&
      value.every((row) => row && typeof row === "object" && !Array.isArray(row));

    if (isRows(body)) return body;
    if (body && typeof body === "object") {
      return Object.values(body).find(isRows) ?? null;
    }
    return null;
  }

  function buildTable(rows) {
    const columns = Object.keys(rows[0]);
    const wrapper = element("div", "table-responsive");
    const table = element("table", "table table-sm table-striped oa-rows");

    const headRow = element("tr");
    for (const column of columns) {
      const cell = element("th", "", column);
      cell.scope = "col";
      headRow.append(cell);
    }
    const head = element("thead");
    head.append(headRow);

    const body = element("tbody");
    for (const row of rows) {
      const tableRow = element("tr");
      for (const column of columns) {
        const value = row[column];
        const text = value !== null && typeof value === "object" ? JSON.stringify(value) : value ?? "";
        tableRow.append(element("td", "", String(text)));
      }
      body.append(tableRow);
    }

    table.append(head, body);
    wrapper.append(table);
    return wrapper;
  }

  function statusClass(status) {
    if (status < 300) return "text-bg-success";
    if (status < 500) return "text-bg-warning";
    return "text-bg-danger";
  }

  function showResult(container, request, result) {
    const summary = element("div", "oa-result-summary");
    summary.append(
      element(
        "span",
        `badge ${statusClass(result.status)}`,
        `${result.status} ${STATUS_TEXT[result.status] ?? ""}`.trim(),
      ),
    );
    if (result.source === "live") {
      summary.append(element("span", "oa-result-note", `${result.elapsed} ms`));
    } else if (result.source === "fallback") {
      summary.append(
        element(
          "span",
          "oa-result-note",
          "The API didn't answer, so this response comes from the mock in your browser.",
        ),
      );
    } else {
      summary.append(element("span", "oa-result-note", "Mock response from your browser"));
    }

    const requestLine = element("pre", "oa-result-request");
    requestLine.append(element("code", "", `${request.method} ${request.url}`));

    const parts = [summary, requestLine];

    const rows = findRows(result.body);
    if (rows) parts.push(buildTable(rows));

    const lines = Object.entries(result.headers ?? {}).map(([name, value]) => `${name}: ${value}`);
    if (result.body !== null && result.body !== undefined) {
      if (lines.length) lines.push("");
      lines.push(typeof result.body === "string" ? result.body : JSON.stringify(result.body, null, 2));
    }
    if (lines.length) {
      const response = element("pre", "oa-result-response");
      response.append(element("code", "", lines.join("\n")));
      parts.push(response);
    }

    container.replaceChildren(...parts);
    container.hidden = false;
  }

  function showFailure(container, error) {
    container.replaceChildren(
      element("div", "alert alert-danger mb-0", `The request couldn't be sent. ${error.message}`),
    );
    container.hidden = false;
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.classList.contains("oa-try")) return;
    event.preventDefault();

    const container = form.parentElement.querySelector(".oa-result");
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const request = readForm(form);
      showResult(container, request, await send(request));
    } catch (error) {
      showFailure(container, error);
    } finally {
      button.disabled = false;
    }
  });
})();
