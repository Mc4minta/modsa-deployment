import http from "node:http";

const server = http.createServer((request, response) => {
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type");
  response.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");

  if (request.method === "OPTIONS") {
    response.writeHead(204);
    response.end();
    return;
  }

  if (request.url === "/health") {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (request.url !== "/chat/ask" || request.method !== "POST") {
    response.writeHead(404);
    response.end();
    return;
  }

  let body = "";
  request.on("data", (chunk) => {
    body += chunk;
  });
  request.on("end", () => {
    let payload = {};
    try {
      payload = JSON.parse(body);
    } catch {
      // The frontend owns malformed-response handling; keep this fixture simple.
    }

    const question = String(payload.question || "");
    const status = question.includes("422") ? 422 : question.includes("429") ? 429 : question.includes("500") ? 500 : 200;
    const responseBody = question.includes("malformed")
      ? { answer: 42, sources: "invalid" }
      : status === 200
      ? {
          answer: "## Admissions\n\n| ไทย | English |\n| --- | --- |\n| รับสมัคร | Admissions |\n\n[Safe source](https://example.com/doc) [Unsafe](javascript:alert(1))",
          sources: question.includes("no-source")
            ? []
            : [{ title: "KMUTT guide", url: "https://example.com/doc", page: 2 }],
        }
      : { detail: `Mock HTTP ${status}` };

    const finish = () => {
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(responseBody));
    };
    if (question.includes("delay")) setTimeout(finish, 10000);
    else if (question.includes("timeout")) setTimeout(finish, 47000);
    else finish();
  });
});

server.listen(8000, "127.0.0.1", () => {
  console.log("Mock browser API listening on http://127.0.0.1:8000");
});
