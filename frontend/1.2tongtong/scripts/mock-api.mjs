import { createServer } from "node:http";

const PORT = 8000;

const server = createServer((request, response) => {
  response.setHeader("Access-Control-Allow-Origin", "http://127.0.0.1:5173");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type, Accept-Language");
  response.setHeader("Content-Type", "application/json; charset=utf-8");

  if (request.method === "OPTIONS") {
    response.statusCode = 204;
    response.end();
    return;
  }

  if (request.method === "GET" && request.url === "/health") {
    response.end(JSON.stringify({ status: "ok", ingestion: { status: "indexed" } }));
    return;
  }

  if (request.method === "POST" && request.url === "/chat/ask") {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      const thai = request.headers["accept-language"] === "th";
      const answer = thai
        ? "### ตัวอย่างกำหนดการ\n\n| วันที่ | สิ่งที่ต้องทำ |\n| --- | --- |\n| 1 ส.ค. | ตรวจสอบประกาศล่าสุด |\n| 5 ส.ค. | ติดต่อสำนักงานทะเบียน |\n\n1. ตรวจสอบข้อมูลจากแหล่งอ้างอิง\n2. ยืนยันกับหน่วยงานก่อนดำเนินการ"
        : "### Example schedule\n\n| Date | Action |\n| --- | --- |\n| 1 Aug | Check the latest announcement |\n| 5 Aug | Contact the Registration Office |\n\n1. Review the cited source.\n2. Confirm with the responsible office before acting.";

      response.end(
        JSON.stringify({
          answer,
          confidence: "high",
          sources: [
            {
              title: "Academic Calendar",
              source: "academic-calendar.json",
              department: "Registration Office",
              page: 1,
              url: "https://www.kmutt.ac.th/",
            },
            {
              title: "Registration Manual",
              source: "registration-manual.json",
              department: "Registration Office",
              page: 4,
            },
            {
              title: "Student Affairs Guide",
              source: "student-affairs-guide.json",
              department: "Student Affairs",
              page: 2,
            },
          ],
        }),
      );
    });
    return;
  }

  response.statusCode = 404;
  response.end(JSON.stringify({ detail: "Not found" }));
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`MOD-SA mock API listening on http://127.0.0.1:${PORT}`);
});
