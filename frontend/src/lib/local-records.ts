import type { Document } from "../types/index";

/** Bounded RFC 4180-style reader. All processing stays in the browser. */
export function parseCsv(text: string): string[][] {
  if (text.length > 256_000) throw new Error("CSV content must be at most 256 KB for browser storage.");
  const rows: string[][] = [];
  let row: string[] = [], cell = "", quoted = false, closedQuote = false;
  const pushCell = () => { row.push(cell.trim()); cell = ""; closedQuote = false; };
  const pushRow = () => {
    pushCell();
    if (row.some(Boolean)) rows.push(row);
    row = [];
    if (rows.length > 501) throw new Error("CSV files may contain at most 500 data rows.");
  };
  text = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else if (quoted) { quoted = false; closedQuote = true; }
      else if (!cell.trim() && !closedQuote) quoted = true;
      else throw new Error("Invalid CSV quote. Quote the entire cell.");
    } else if (char === "," && !quoted) pushCell();
    else if ((char === "\n" || char === "\r") && !quoted) {
      pushRow();
      if (char === "\r" && text[i + 1] === "\n") i++;
    } else {
      if (closedQuote && char.trim()) throw new Error("Invalid text after a quoted CSV cell.");
      cell += char;
    }
  }
  if (quoted) throw new Error("CSV has an unclosed quoted cell.");
  if (cell || row.length) pushRow();
  if (rows.length < 2 || !rows[0].every(Boolean)) throw new Error("CSV needs a header and at least one data row.");
  if (new Set(rows[0].map(header => header.toLowerCase())).size !== rows[0].length) throw new Error("CSV headers must be unique.");
  if (rows.some(row => row.length !== rows[0].length)) throw new Error("CSV rows must have the same number of columns as the header.");
  return rows;
}

export function csvRecordText(text: string): string {
  const [headers, ...rows] = parseCsv(text);
  const result = rows.map(row => headers.map((header, i) => `${header}: ${row[i]}`).join(" · ")).join("\n");
  if (result.length > 128_000) throw new Error("Parsed CSV exceeds the 128 KB local record limit. Split it into smaller files.");
  return result;
}

const stopWords = new Set("what which where when why how did does the a an is are was were for of in on to and my field records show tell me about".split(" "));
function terms(text: string): string[] {
  return [...new Set((text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []).filter(term => term.length > 1 && !stopWords.has(term)))];
}

/** Deterministic lexical retrieval; scores rank matches, never causal confidence. */
export function searchRecords(question: string, documents: Document[], limit = 6): Document[] {
  const words = terms(question);
  return documents.filter(doc => doc.ingest_status === "ready")
    .map((doc, index) => {
      const title = terms(doc.label), content = terms(doc.extracted_text ?? "");
      const date = doc.date_of_event ?? doc.uploaded_at.slice(0, 10);
      const score = words.reduce((sum, word) => sum + (title.includes(word) ? 3 : 0) + (content.includes(word) ? 1 : 0) + (date.includes(word) ? 2 : 0), 0);
      return { doc, index, score };
    })
    .filter(item => !words.length || item.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .slice(0, limit).map(item => item.doc);
}
