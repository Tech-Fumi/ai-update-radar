import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${RELAY_API_URL}/learning/signals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: `Failed to send learning signal: ${error}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error sending learning signal:", error);
    return NextResponse.json(
      { error: "Failed to send learning signal" },
      { status: 500 }
    );
  }
}
