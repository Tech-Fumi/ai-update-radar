import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const since = searchParams.get("since") || "7d";

    const response = await fetch(
      `${RELAY_API_URL}/learning/stats?since=${encodeURIComponent(since)}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: `Failed to get learning stats: ${error}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error getting learning stats:", error);
    return NextResponse.json(
      { error: "Failed to get learning stats" },
      { status: 500 }
    );
  }
}
