import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

function generateRandomId(length: number = 8): string {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ run_id: string }> }
) {
  try {
    const { run_id } = await params;

    // 1. 元のタスク情報を取得
    const taskUrl = `${RELAY_API_URL}/runs/${run_id}/task`;
    const taskResponse = await fetch(taskUrl, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });

    if (!taskResponse.ok) {
      const error = await taskResponse.text();
      return NextResponse.json(
        { error: `Failed to get original task: ${error}` },
        { status: taskResponse.status }
      );
    }

    const taskData = await taskResponse.json();
    const { payload } = taskData;

    // 2. 新しい trace_id を生成（tr_rerun_<old_run_id>_<rand>）
    const newTraceId = `tr_rerun_${run_id}_${generateRandomId()}`;

    // 3. POST /tasks に送信
    const submitUrl = `${RELAY_API_URL}/tasks`;
    const submitResponse = await fetch(submitUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: payload.user_id,
        target: payload.target,
        content: payload.content,
        project_root: payload.project_root,
        trace_id: newTraceId,
        parent_run_id: run_id,
      }),
    });

    if (!submitResponse.ok) {
      const error = await submitResponse.text();
      return NextResponse.json(
        { error: `Failed to submit task: ${error}` },
        { status: submitResponse.status }
      );
    }

    const submitData = await submitResponse.json();

    return NextResponse.json({
      success: true,
      task_id: submitData.task_id,
      trace_id: newTraceId,
      parent_run_id: run_id,
    });
  } catch (error) {
    console.error("Error rerunning task:", error);
    return NextResponse.json(
      { error: "Failed to rerun task" },
      { status: 500 }
    );
  }
}
