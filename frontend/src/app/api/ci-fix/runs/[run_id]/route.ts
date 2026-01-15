import { NextRequest, NextResponse } from "next/server";

const LEDGER_API = process.env.LEDGER_API || "http://18.176.47.143:8002";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ run_id: string }> }
) {
  const { run_id } = await params;

  try {
    const response = await fetch(`${LEDGER_API}/api/ci-fix/runs/${encodeURIComponent(run_id)}`);
    if (!response.ok) {
      return NextResponse.json(
        { error: "Run not found" },
        { status: response.status }
      );
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "Ledger API unavailable" },
      { status: 503 }
    );
  }
}
