import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ run_id: string }> }
) {
  try {
    const { run_id } = await params;

    // リクエストボディを取得（オプション）
    let body = {};
    try {
      body = await request.json();
    } catch {
      // ボディなしでもOK
    }

    const url = `${RELAY_API_URL}/runs/${run_id}/fix-task`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
    console.error("Error creating fix task:", error);
    return NextResponse.json(
      { error: "Failed to create fix task" },
      { status: 500 }
    );
  }
}
