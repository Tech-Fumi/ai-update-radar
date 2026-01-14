import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const params = new URLSearchParams();

    // クエリパラメータを転送
    const limit = searchParams.get("limit");
    const cursor = searchParams.get("cursor");
    const status = searchParams.get("status");
    const trace_id = searchParams.get("trace_id");
    const since = searchParams.get("since");

    if (limit) params.set("limit", limit);
    if (cursor) params.set("cursor", cursor);
    if (status) params.set("status", status);
    if (trace_id) params.set("trace_id", trace_id);
    if (since) params.set("since", since);

    const queryString = params.toString();
    const url = `${RELAY_API_URL}/runs${queryString ? `?${queryString}` : ""}`;

    const response = await fetch(url, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: `Relay API error: ${error}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching runs:", error);
    return NextResponse.json(
      { error: "Failed to fetch runs" },
      { status: 500 }
    );
  }
}
