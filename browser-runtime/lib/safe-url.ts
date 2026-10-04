import { isIP } from "node:net";

function privateIpv4(host: string): boolean {
  const p = host.split(".").map(Number);
  if (p.length !== 4 || p.some((x) => !Number.isInteger(x) || x < 0 || x > 255)) return false;
  return (
    p[0] === 10 ||
    p[0] === 127 ||
    p[0] === 0 ||
    (p[0] === 169 && p[1] === 254) ||
    (p[0] === 172 && p[1] >= 16 && p[1] <= 31) ||
    (p[0] === 192 && p[1] === 168)
  );
}

export function safeHttpsUrl(raw: string): URL {
  const url = new URL(raw);
  if (url.protocol !== "https:") throw new Error("HTTPS only");
  if (url.username || url.password) throw new Error("credential-bearing URL blocked");

  const host = url.hostname.toLowerCase();
  if (
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host.endsWith(".local") ||
    host.endsWith(".internal") ||
    host === "metadata.google.internal"
  ) {
    throw new Error("local/private hostname blocked");
  }

  const ipKind = isIP(host);
  if (ipKind === 4 && privateIpv4(host)) throw new Error("private IPv4 blocked");
  if (ipKind === 6) throw new Error("literal IPv6 blocked");

  return url;
}
