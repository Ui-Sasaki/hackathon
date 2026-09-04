let handler: (() => void) | null = null;

export function setUnauthorizedHandler(h: (() => void) | null): void {
  handler = h;
}

export function triggerUnauthorized(): void {
  try {
    handler?.();
  } catch {
    // swallow errors from handlers to avoid breaking API error paths
  }
}

export default {
  setUnauthorizedHandler,
  triggerUnauthorized,
};
