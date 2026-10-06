"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

export interface ConfirmRequest {
  title: string;
  description: React.ReactNode;
  action: string;
  run: () => Promise<void> | void;
}

/** One confirm dialog per page: `ask({...})` opens it. */
export function useConfirm() {
  const [req, setReq] = useState<ConfirmRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const dialog = (
    <Dialog open={!!req} onOpenChange={(o) => !o && !busy && setReq(null)}>
      <DialogContent className="max-w-md">
        <DialogTitle>{req?.title}</DialogTitle>
        <DialogDescription>{req?.description}</DialogDescription>
        <div className="flex justify-end gap-2">
          <Button variant="outline" disabled={busy} onClick={() => setReq(null)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await req?.run();
              } finally {
                setBusy(false);
                setReq(null);
              }
            }}
          >
            {busy ? "Working…" : req?.action}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
  return { ask: setReq, dialog };
}
