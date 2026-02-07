import { NextRequest, NextResponse } from "next/server";

const RELAY_API_URL = process.env.RELAY_API_URL || "http://localhost:8050";

interface ActionItem {
  task: string;
  source_feature: string;
  priority: number;
  project: string;
  category: "dev" | "business";
}

interface SubmitRequest {
  version: string;
  items: ActionItem[];
}

export async function POST(request: NextRequest) {
  try {
    const body: SubmitRequest = await request.json();
    const { version, items } = body;

    if (!items || items.length === 0) {
      return NextResponse.json(
        { success: false, error: "No items to submit" },
        { status: 400 }
      );
    }

    const results: Array<{
      task_id?: string;
      success: boolean;
      error?: string;
      item: ActionItem;
    }> = [];

    // 各アイテムを個別のタスクとして送信
    for (const item of items) {
      const taskContent = `## ${item.category === "dev" ? "開発タスク" : "経営タスク"} (${version})

**プロジェクト**: ${item.project}
**優先度**: ${item.priority}
**根拠**: ${item.source_feature}

### タスク内容
${item.task}

---
_AI Update Radar から自動送信_`;

      try {
        const response = await fetch(`${RELAY_API_URL}/tasks`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            user_id: "ai-update-radar",
            target: "auto",
            content: taskContent,
            project_root: `/home/fumi/${item.project}`,
          }),
        });

        if (response.ok) {
          const data = await response.json();
          results.push({
            task_id: data.task_id,
            success: true,
            item,
          });
        } else {
          const errorText = await response.text();
          results.push({
            success: false,
            error: `HTTP ${response.status}: ${errorText}`,
            item,
          });
        }
      } catch (error) {
        results.push({
          success: false,
          error: error instanceof Error ? error.message : "Unknown error",
          item,
        });
      }
    }

    const successCount = results.filter((r) => r.success).length;
    const failedCount = results.filter((r) => !r.success).length;

    return NextResponse.json({
      success: failedCount === 0,
      message: `${successCount}件のタスクを送信しました${failedCount > 0 ? `（${failedCount}件失敗）` : ""}`,
      results,
      submitted_at: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Submit tasks error:", error);
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

// ヘルスチェック用
export async function GET() {
  try {
    const response = await fetch(`${RELAY_API_URL}/health`, {
      method: "GET",
    });

    if (response.ok) {
      return NextResponse.json({
        relay_api: "connected",
        url: RELAY_API_URL,
      });
    } else {
      return NextResponse.json({
        relay_api: "unhealthy",
        status: response.status,
      });
    }
  } catch {
    return NextResponse.json({
      relay_api: "not_running",
      url: RELAY_API_URL,
      hint: "Relay API を起動してください: cd ~/infra-automation/claude-relay-bridge && ./scripts/dev_up.sh",
    });
  }
}
