import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const since = searchParams.get("since");

    const url = new URL(`${RELAY_API_URL}/runs/stats`);
    if (since) url.searchParams.set("since", since);

    const response = await fetch(url.toString());

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch stats" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching runs stats:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
