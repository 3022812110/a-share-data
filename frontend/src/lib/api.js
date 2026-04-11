const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function buildHttpError(response, message) {
  const error = new Error(message || `request failed: ${response.status}`);
  error.status = response.status;
  return error;
}

export async function request(path, options) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = await response.json().catch(() => null);
      const detail = payload?.detail ?? payload?.message ?? payload?.error;
      if (typeof detail === "string" && detail.trim()) {
        throw buildHttpError(response, detail.trim());
      }
      if (detail && typeof detail === "object") {
        throw buildHttpError(response, JSON.stringify(detail));
      }
      if (payload) {
        throw buildHttpError(response, JSON.stringify(payload));
      }
    }

    const text = await response.text();
    throw buildHttpError(response, text || `request failed: ${response.status}`);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

export async function requestStream(path, options = {}) {
  const { onEvent, ...fetchOptions } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(fetchOptions.headers ?? {}),
    },
    ...fetchOptions,
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = await response.json().catch(() => null);
      const detail = payload?.detail ?? payload?.message ?? payload?.error;
      if (typeof detail === "string" && detail.trim()) {
        throw buildHttpError(response, detail.trim());
      }
      if (detail && typeof detail === "object") {
        throw buildHttpError(response, JSON.stringify(detail));
      }
      if (payload) {
        throw buildHttpError(response, JSON.stringify(payload));
      }
    }

    const text = await response.text();
    throw buildHttpError(response, text || `request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const emitEvent = (rawEvent) => {
    if (!rawEvent.trim()) return;
    const lines = rawEvent.split("\n");
    let event = "message";
    const dataLines = [];

    for (const rawLine of lines) {
      const line = rawLine.trimEnd();
      if (!line) continue;
      if (line.startsWith("event:")) {
        event = line.slice(6).trim() || "message";
        continue;
      }
      if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    if (!dataLines.length || typeof onEvent !== "function") return;
    const rawData = dataLines.join("\n");
    try {
      onEvent({ event, data: JSON.parse(rawData) });
    } catch {
      onEvent({ event, data: rawData });
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done }).replace(/\r\n/g, "\n");

    let splitIndex = buffer.indexOf("\n\n");
    while (splitIndex !== -1) {
      const rawEvent = buffer.slice(0, splitIndex);
      buffer = buffer.slice(splitIndex + 2);
      emitEvent(rawEvent);
      splitIndex = buffer.indexOf("\n\n");
    }

    if (done) {
      if (buffer.trim()) emitEvent(buffer);
      break;
    }
  }
}
