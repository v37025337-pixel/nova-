export const runtime = "nodejs";

export async function GET() {
  return Response.json({
    ok: true,
    service: "mind-core-browser-runtime",
    version: "0.1.0",
    engine: "verified-ungoogled-chromium-sandbox"
  });
}
