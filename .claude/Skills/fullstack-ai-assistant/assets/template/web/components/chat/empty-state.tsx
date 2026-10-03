"use client";

import { useEffect, useState } from "react";
import { CodeIcon, LightbulbIcon, MailIcon, ListChecksIcon } from "lucide-react";

import { APP_CONFIG, firstNameOf } from "@/lib/config";

const SUGGESTIONS = [
  {
    icon: CodeIcon,
    title: "Write code",
    sub: "A debounce utility in TypeScript",
    prompt: "Write a debounce function in TypeScript and explain how it works.",
  },
  {
    icon: MailIcon,
    title: "Draft an email",
    sub: "Follow up with a client after a demo",
    prompt: "Draft a short, friendly follow-up email to a client after a product demo.",
  },
  {
    icon: LightbulbIcon,
    title: "Explain a concept",
    sub: "How large language models work",
    prompt: "Explain how large language models work in simple terms.",
  },
  {
    icon: ListChecksIcon,
    title: "Plan a project",
    sub: "Launch plan for a new SaaS feature",
    prompt: "Create a launch plan for a new SaaS feature, with milestones and owners.",
  },
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function EmptyState() {
  // Time-based text differs between server and client, so render it after mount.
  const [hello, setHello] = useState("Hello");
  useEffect(() => setHello(greeting()), []);

  return (
    <div className="px-4 pb-6 text-center">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
        {hello}, {firstNameOf(APP_CONFIG.user.name)}
      </h1>
      <p className="mt-2 text-muted-foreground">How can I help you today?</p>
    </div>
  );
}

export function SuggestionGrid({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="mx-auto mt-4 grid w-full max-w-3xl grid-cols-1 gap-2.5 text-left sm:grid-cols-2">
      {SUGGESTIONS.map(({ icon: Icon, title, sub, prompt }, i) => (
        <button
          key={title}
          type="button"
          onClick={() => onPick(prompt)}
          className={
            "flex items-start gap-3 rounded-xl border bg-card p-3.5 text-left transition-colors hover:bg-accent " +
            (i > 1 ? "hidden sm:flex" : "")
          }
        >
          <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <span>
            <span className="block text-sm font-medium">{title}</span>
            <span className="block text-[13px] text-muted-foreground">{sub}</span>
          </span>
        </button>
      ))}
    </div>
  );
}
