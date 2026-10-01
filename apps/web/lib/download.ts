/** Download only authenticated, same-origin API resources. */
export async function downloadFile(path: string, filename: string, expectedType?: string): Promise<void> {
  if (!path.startsWith("/api/") || path.includes("\\") || new URL(path, window.location.origin).origin !== window.location.origin) {
    throw new Error("The download address is invalid.");
  }
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", cache: "no-store", redirect: "error" });
  } catch {
    throw new Error("The download could not reach the server. Please retry.");
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : `Download failed (${response.status}). Please retry.`);
  }
  const contentType = response.headers.get("content-type")?.split(";")[0].trim();
  if (expectedType && contentType !== expectedType) {
    throw new Error("The server did not return the expected file. Please retry.");
  }
  const blob = await response.blob();
  if (!blob.size) throw new Error("The downloaded file is empty. Please retry.");
  saveBlob(blob, filename);
}

export function saveText(text: string, filename: string): void {
  saveBlob(new Blob([text], { type: "text/plain;charset=utf-8" }), filename);
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-");
  document.body.appendChild(link);
  try { link.click(); } finally {
    link.remove();
    // Allow the browser to start consuming the download before releasing its URL.
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
}
