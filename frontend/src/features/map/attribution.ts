import type { Attribution } from "@/api/types";

function escapeHtml(text: string): string {
  const element = document.createElement("span");
  element.textContent = text;
  return element.innerHTML;
}

export function attributionHtml(attribution: Attribution): string {
  const text = escapeHtml(attribution.text);
  return attribution.url === null
    ? text
    : `<a href="${escapeHtml(attribution.url)}" target="_blank" rel="noopener">${text}</a>`;
}
