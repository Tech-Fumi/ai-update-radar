import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ run_id: string; filename: string }> }
) {
  try {
    const { run_id, filename } = await params;

    // 許可ファイル名のみ
    const allowed = ["patch.diff", "stdout.log", "stderr.log", "result.json"];
    if (!allowed.includes(filename)) {
      return NextResponse.json(
        { error: "Invalid filename" },
        { status: 400 }
      );
    }

    const url = `${RELAY_API_URL}/runs/${run_id}/artifacts/${filename}`;

    const response = await fetch(url);

    if (!response.ok) {
      return NextResponse.json(
        { error: "File not found" },
        { status: response.status }
      );
    }

    const content = await response.text();

    // Content-Type を決定
    let contentType = "text/plain";
    if (filename.endsWith(".json")) contentType = "application/json";
    else if (filename.endsWith(".diff")) contentType = "text/x-diff";

    return new NextResponse(content, {
      headers: { "Content-Type": contentType },
    });
  } catch (error) {
    console.error("Error fetching artifact:", error);
    return NextResponse.json(
      { error: "Failed to fetch artifact" },
      { status: 500 }
    );
  }
}
