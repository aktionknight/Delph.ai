"use client";
import { useCallback } from "react";
import { title } from "@/lib/api";

export function useAgentJob(setProgress: (message: string) => void) {
  return useCallback((jobId: string) => {
  return new Promise<void>((resolve, reject) => {
        const stream = new EventSource(`/api/jobs/${jobId}/stream`);
        const timer = setTimeout(() => { stream.close(); reject(new Error("Agent operation timed out. Check activity and reload before retrying.")); }, 16 * 60 * 1000);
        function close() { clearTimeout(timer); stream.close(); }
        stream.addEventListener("progress", (event) => { const data = JSON.parse((event as MessageEvent).data); setProgress(`${title(data.role)} · ${data.status}`); });
        stream.addEventListener("complete", (event) => { const data = JSON.parse((event as MessageEvent).data); close(); data.status === "completed" ? resolve() : reject(new Error(data.error || "Agent operation failed.")); });
        stream.onerror = () => { close(); reject(new Error("Progress connection closed. The job may still be running; reload the campaign before retrying.")); };
      });
  }, [setProgress]);
}
