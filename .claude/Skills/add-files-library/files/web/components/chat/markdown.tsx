"use client";

import { memo, useMemo, useState } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="not-prose overflow-hidden rounded-lg border bg-muted/50">
      <div className="flex items-center justify-between border-b py-1 pr-1 pl-3.5">
        <span className="font-mono text-xs text-muted-foreground">{language || "text"}</span>
        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={copy}>
          {copied ? <CheckIcon /> : <CopyIcon />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-6">
        <code>{code}</code>
      </pre>
    </div>
  );
}

const components: Components = {
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => {
    const match = /language-([\w+#.-]+)/.exec(className ?? "");
    const text = String(children ?? "");
    // Fenced blocks have a language class or contain a newline; the rest are inline.
    if (match || text.includes("\n")) {
      return <CodeBlock language={match?.[1] ?? ""} code={text.replace(/\n$/, "")} />;
    }
    return <code>{children}</code>;
  },
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto rounded-lg border">
      <table>{children}</table>
    </div>
  ),
};

/** `[3]` → a link the citation renderer turns into a button (only for real source numbers). */
function linkCitations(content: string, count: number): string {
  return content.replace(/\[(\d{1,2})\](?!\()/g, (m, n: string) =>
    Number(n) >= 1 && Number(n) <= count ? `[${n}](#cite-${n})` : m,
  );
}

export const Markdown = memo(function Markdown({
  content,
  citations = 0,
  onCite,
}: {
  content: string;
  /** Number of sources; [n] markers up to this become buttons. */
  citations?: number;
  onCite?: (n: number) => void;
}) {
  const withCites = useMemo<Components>(
    () => ({
      ...components,
      a: ({ href, children }) => {
        const m = /^#cite-(\d+)$/.exec(href ?? "");
        if (m && onCite) {
          const n = Number(m[1]);
          return (
            <button
              type="button"
              onClick={() => onCite(n)}
              aria-label={`Source ${n}`}
              className="mx-px inline-grid h-[18px] min-w-[18px] translate-y-[-2px] place-items-center rounded-md border bg-muted px-1 align-middle font-mono text-[11px] leading-none text-muted-foreground no-underline hover:bg-foreground hover:text-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {n}
            </button>
          );
        }
        return (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        );
      },
    }),
    [onCite],
  );
  const text = citations && onCite ? linkCitations(content, citations) : content;
  return (
    <div className="prose-chat">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={citations ? withCites : components}>
        {text}
      </ReactMarkdown>
    </div>
  );
});
