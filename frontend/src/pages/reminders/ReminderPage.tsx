import { Alert, Button, Card, List, Space, Spin, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getReminderList, processReminder } from "../../api/reminders";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import { authStore } from "../../store/auth";
import type { ReminderItem } from "../../types/reminder";
import { formatDateTime } from "../../utils/format";

interface ActionFeedback {
  type: "success" | "error";
  message: string;
  description?: string;
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? `${err.message}（HTTP ${err.status}）` : fallback;
}

function getStatusColor(status: ReminderItem["status"]) {
  if (status === "processed") {
    return "success";
  }
  if (status === "expired") {
    return "default";
  }
  if (status === "sent") {
    return "processing";
  }
  return "warning";
}

export function ReminderPage() {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);
  const [reminders, setReminders] = useState<ReminderItem[]>([]);

  async function loadReminders() {
    setLoading(true);
    try {
      const response = await getReminderList();
      setReminders(response.results);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, "reminder 列表加载失败"));
      setReminders([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      authStore.setToken(token);
    }

    void loadReminders();
  }, [searchParams]);

  async function handleProcess(reminderId: number) {
    setProcessingId(reminderId);
    setActionFeedback(null);
    try {
      const response = await processReminder(reminderId);
      await loadReminders();
      setActionFeedback({
        type: "success",
        message: "reminder 处理成功",
        description: response.created_follow_up_id
          ? `提醒 #${response.id} 已处理，并生成 followup #${response.created_follow_up_id}。`
          : `提醒 #${response.id} 已处理。`
      });
      message.success("reminder 处理成功");
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "reminder 处理失败",
        description: getErrorMessage(err, "reminder 处理失败")
      });
    } finally {
      setProcessingId(null);
    }
  }

  return (
    <PagePlaceholder
      title="我的提醒"
      description="当前页最小接入 reminder 列表和 process 闭环，用于真实 dev API 联调。"
      extra={
        <Space wrap>
          <Tag color="processing">接口：GET /api/v1/reminders/</Tag>
          <Tag color="processing">接口：POST /api/v1/reminders/{'{id}'}/process/</Tag>
        </Space>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {actionFeedback ? (
          <Alert
            type={actionFeedback.type}
            showIcon
            message={actionFeedback.message}
            description={actionFeedback.description}
          />
        ) : null}

        {error ? (
          <Alert
            type="error"
            showIcon
            message="reminder 列表加载失败"
            description={error}
          />
        ) : null}

        <Card title={`reminder 列表（${reminders.length}）`}>
          <Spin spinning={loading}>
            <List
              locale={{ emptyText: "当前没有 reminder" }}
              dataSource={reminders}
              renderItem={(item) => (
                <List.Item
                  key={item.id}
                  actions={[
                    item.status === "pending" ? (
                      <Button
                        key="process"
                        type="primary"
                        size="small"
                        loading={processingId === item.id}
                        onClick={() => void handleProcess(item.id)}
                      >
                        标记已处理
                      </Button>
                    ) : null
                  ].filter(Boolean)}
                >
                  <List.Item.Meta
                    title={
                      <Space wrap>
                        <Tag>#{item.id}</Tag>
                        <Tag color={getStatusColor(item.status)}>{item.status}</Tag>
                        <Tag>{item.remind_type_display ?? item.remind_type}</Tag>
                        <Tag>{item.target_type}</Tag>
                        {item.is_manual ? <Tag color="blue">manual</Tag> : null}
                        <Typography.Text>
                          {item.target_name ?? item.target_id}
                        </Typography.Text>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={4} style={{ width: "100%" }}>
                        <Typography.Text type="secondary">
                          提醒时间：{formatDateTime(item.remind_at)}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          目标摘要：{item.target_summary ?? "-"}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          创建时间：{formatDateTime(item.created_at)}
                        </Typography.Text>
                        {item.processed_at ? (
                          <Typography.Text type="secondary">
                            处理时间：{formatDateTime(item.processed_at)}
                          </Typography.Text>
                        ) : null}
                        {item.target_type === "user" ? (
                          <Link to={`/users/${item.target_id}`}>查看用户</Link>
                        ) : (
                          <Link to={`/match-cards/${item.target_id}`}>查看配对卡</Link>
                        )}
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Spin>
        </Card>
      </Space>
    </PagePlaceholder>
  );
}
