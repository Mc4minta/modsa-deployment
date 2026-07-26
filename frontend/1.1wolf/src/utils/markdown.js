/**
 * Lightweight Markdown → HTML converter.
 * Supports: bold, italic, inline code, code blocks, links, unordered/ordered lists, headings, line breaks.
 * Sanitizes against XSS.
 */

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function renderMarkdown(text) {
  if (!text) return "";

  let html = escapeHtml(text);

  // Code blocks (``` ... ```)
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    (_, lang, code) =>
      `<pre class="md-code-block"><code class="lang-${lang}">${code.trim()}</code></pre>`
  );

  // Inline code
  html = html.replace(
    /`([^`]+)`/g,
    '<code class="md-inline-code">$1</code>'
  );

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Italic
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // Headings (### ## #)
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>');
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>');

  // Links
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="md-link">$1</a>'
  );

  // Unordered lists
  html = html.replace(/^[\-\*] (.+)$/gm, '<li class="md-li">$1</li>');
  html = html.replace(
    /(<li class="md-li">.*<\/li>\n?)+/g,
    (match) => `<ul class="md-ul">${match}</ul>`
  );

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="md-li-ol">$1</li>');
  html = html.replace(
    /(<li class="md-li-ol">.*<\/li>\n?)+/g,
    (match) => `<ol class="md-ol">${match}</ol>`
  );

  // Line breaks (double newline → paragraph break)
  html = html.replace(/\n\n/g, '</p><p class="md-p">');
  html = html.replace(/\n/g, "<br>");

  // Wrap in paragraph
  html = `<p class="md-p">${html}</p>`;

  // Clean up empty paragraphs
  html = html.replace(/<p class="md-p"><\/p>/g, "");

  return html;
}
