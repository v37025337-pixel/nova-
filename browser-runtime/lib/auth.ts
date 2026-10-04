import { timingSafeEqual } from "node:crypto";

export function authorized(request: Request): boolean {
  const expected = process.env.BROWSER_BRIDGE_SECRET || "";
  const supplied = request.headers.get("authorization") || "";
  const prefix = "Bearer ";
  if (!expected || !supplied.startsWith(prefix)) return false;

  const got = Buffer.from(supplied.slice(prefix.length));
  const want = Buffer.from(expected);
  if (got.length !== want.length) return false;

  return timingSafeEqual(got, want);
}
