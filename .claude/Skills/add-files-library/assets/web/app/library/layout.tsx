import type { Metadata } from "next";

import { LibraryShell } from "@/components/library/shell";

export const metadata: Metadata = { title: "Library" };

export default function LibraryLayout({ children }: LayoutProps<"/library">) {
  return <LibraryShell>{children}</LibraryShell>;
}
