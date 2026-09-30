/** Minimal RFC 4180 CSV reading/writing for batch input and export. */

export function parseCsv(input: string): string[][] {
  const text = input.replace(/^﻿/, "");
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') {
        quoted = false;
      } else {
        field += c;
      }
    } else if (c === '"' && field === "") {
      quoted = true; // a quote only opens a quoted field at its start (5" screen stays literal)
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += c;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.some((f) => f.trim() !== ""));
}

const TEXT_COLUMNS = ["text", "review", "sentence", "comment", "content", "message", "tweet", "headline"];

/**
 * Texts from an uploaded file: a CSV's text column (by header name, else the first
 * column), or one text per line for plain text files.
 */
export function textsFromFile(name: string, content: string): string[] {
  const clean = (s: string) => s.replace(/\s+/g, " ").trim();
  if (!/\.csv$/i.test(name)) {
    return content.split(/\r?\n/).map(clean).filter(Boolean);
  }
  const rows = parseCsv(content);
  if (rows.length === 0) return [];
  const header = rows[0].map((h) => h.trim().toLowerCase());
  const column = header.findIndex((h) => TEXT_COLUMNS.includes(h));
  const body = column === -1 ? rows : rows.slice(1);
  const index = column === -1 ? 0 : column;
  return body.map((r) => clean(r[index] ?? "")).filter(Boolean);
}

const quote = (value: string | number): string => {
  let s = String(value);
  // Stop spreadsheets from running cells as formulas (CSV injection): =, +, -, @, tab, CR.
  if (typeof value === "string" && /^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function toCsv(header: string[], rows: (string | number)[][]): string {
  return [header, ...rows].map((r) => r.map(quote).join(",")).join("\r\n");
}

export function downloadFile(filename: string, content: string, type = "text/csv;charset=utf-8") {
  const url = URL.createObjectURL(new Blob(["﻿", content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
