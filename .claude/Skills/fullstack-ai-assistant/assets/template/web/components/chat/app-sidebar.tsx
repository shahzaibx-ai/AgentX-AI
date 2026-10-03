"use client";

import { useMemo, useState } from "react";
import {
  CheckIcon,
  EllipsisIcon,
  MonitorIcon,
  MoonIcon,
  PanelLeftIcon,
  SearchIcon,
  SquarePenIcon,
  SunIcon,
  Trash2Icon,
} from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { APP_CONFIG, initialsOf } from "@/lib/config";
import { cn } from "@/lib/utils";
import type { Conversation } from "@/lib/types";

const DAY = 86_400_000;

function groupByDate(list: Conversation[]) {
  const today = new Date().setHours(0, 0, 0, 0);
  const groups: [string, Conversation[]][] = [
    ["Today", []],
    ["Yesterday", []],
    ["Previous 7 days", []],
    ["Previous 30 days", []],
    ["Older", []],
  ];
  for (const c of list) {
    const t = c.updatedAt;
    const i = t >= today ? 0 : t >= today - DAY ? 1 : t >= today - 7 * DAY ? 2 : t >= today - 30 * DAY ? 3 : 4;
    groups[i][1].push(c);
  }
  return groups.filter(([, items]) => items.length);
}

export function AppSidebar({
  conversations,
  activeId,
  onNewChat,
  onOpen,
  onDelete,
  onClearAll,
  onCollapse,
  apiOnline,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onNewChat: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
  onCollapse?: () => void;
  apiOnline: boolean;
}) {
  const [query, setQuery] = useState("");
  const { theme, setTheme } = useTheme();

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = [...conversations]
      .filter(
        (c) =>
          !q ||
          c.title.toLowerCase().includes(q) ||
          c.messages.some((m) => m.content.toLowerCase().includes(q)),
      )
      .sort((a, b) => b.updatedAt - a.updatedAt);
    return groupByDate(list);
  }, [conversations, query]);

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <div className="flex items-center gap-2.5 pl-1 font-semibold tracking-tight">
          <span className="grid size-7 place-items-center rounded-lg bg-foreground">
            <span className="size-2.5 rounded-sm bg-background" />
          </span>
          {APP_CONFIG.appName}
        </div>
        {onCollapse && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Close sidebar" onClick={onCollapse}>
                <PanelLeftIcon />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">Close sidebar</TooltipContent>
          </Tooltip>
        )}
      </div>

      <div className="flex flex-col gap-1.5 px-3 pb-2">
        <Button variant="outline" className="justify-start bg-background" onClick={onNewChat}>
          <SquarePenIcon />
          New chat
          <kbd className="ml-auto hidden text-xs font-normal text-muted-foreground md:inline">
            Ctrl ⇧ O
          </kbd>
        </Button>
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="chat-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
            className="border-transparent bg-transparent pl-8 shadow-none hover:bg-sidebar-accent focus-visible:bg-background dark:bg-transparent"
          />
        </div>
      </div>

      <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {groups.length === 0 && (
          <p className="px-3 py-4 text-sm text-muted-foreground">
            {query ? "No chats match your search." : "Your conversations will appear here."}
          </p>
        )}
        {groups.map(([label, items]) => (
          <section key={label} className="mt-3">
            <h3 className="px-3 pb-1 text-xs font-medium text-muted-foreground">{label}</h3>
            <ul>
              {items.map((c) => {
                const active = c.id === activeId;
                return (
                  <li key={c.id} className="group/item relative">
                    <button
                      type="button"
                      onClick={() => onOpen(c.id)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "w-full truncate rounded-md py-1.5 pr-9 pl-3 text-left text-sm transition-colors hover:bg-sidebar-accent",
                        active && "bg-sidebar-accent font-medium",
                      )}
                    >
                      {c.title}
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          aria-label={`Options for ${c.title}`}
                          className={cn(
                            "absolute top-1/2 right-1 -translate-y-1/2 opacity-0 group-hover/item:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100",
                            active && "[@media(hover:none)]:opacity-100",
                          )}
                        >
                          <EllipsisIcon />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start">
                        <DropdownMenuItem variant="destructive" onSelect={() => onDelete(c.id)}>
                          <Trash2Icon />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </nav>

      <div className="border-t p-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex w-full items-center gap-2.5 rounded-md p-2 text-left text-sm hover:bg-sidebar-accent"
            >
              <span className="grid size-8 place-items-center rounded-full bg-foreground text-xs font-semibold text-background">
                {initialsOf(APP_CONFIG.user.name)}
              </span>
              <span className="flex min-w-0 flex-col leading-tight">
                <span className="truncate font-medium">{APP_CONFIG.user.name}</span>
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      apiOnline ? "bg-success" : "bg-destructive",
                    )}
                  />
                  {apiOnline ? "Connected" : "API offline"}
                </span>
              </span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-(--radix-dropdown-menu-trigger-width)">
            <DropdownMenuLabel>Appearance</DropdownMenuLabel>
            {(
              [
                ["light", "Light", SunIcon],
                ["dark", "Dark", MoonIcon],
                ["system", "System", MonitorIcon],
              ] as const
            ).map(([value, label, Icon]) => (
              <DropdownMenuItem key={value} onSelect={() => setTheme(value)}>
                <Icon />
                {label}
                {theme === value && <CheckIcon className="ml-auto" />}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              disabled={!conversations.length}
              onSelect={onClearAll}
            >
              <Trash2Icon />
              Delete all chats
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
