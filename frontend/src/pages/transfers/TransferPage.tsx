import { Alert, Button, Card, Input, List, Space, Spin, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { approveTransferRequest, getTransferRequests, rejectTransferRequest } from "../../api/transfers";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import { authStore } from "../../store/auth";
import type { TransferRequestItem } from "../../types/transfer";
import { formatDateTime } from "../../utils/format";

interface ActionFeedback {
  type: "success" | "error";
  message: string;
  description?: string;
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? `${err.message}（HTTP ${err.status}）` : fallback;
}

function getStatusColor(status: TransferRequestItem["status"]) {
  if (status === "approved") {
    return "success";
  }
  if (status === "rejected") {
    return "error";
  }
  return "processing";
}

export function TransferPage() {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);
  const [requests, setRequests] = useState<TransferRequestItem[]>([]);
  const [rejectDrafts, setRejectDrafts] = useState<Record<number, string>>({});

  async function loadTransferRequests() {
    setLoading(true);
    try {
      const response = await getTransferRequests("pending");
      setRequests(response);
      setError(null);
    } catch (err) {
      setRequests([]);
      setError(getErrorMessage(err, "transfer request 列表加载失败"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      authStore.setToken(token);
    }

    void loadTransferRequests();
  }, [searchParams]);

  async function handleApprove(requestId: number) {
    setApprovingId(requestId);
    setActionFeedback(null);
    try {
      const response = await approveTransferRequest(requestId);
      setRequests((current) => current.filter((item) => item.id !== requestId));
      setActionFeedback({
        type: "success",
        message: "transfer request 审批通过",
        description: response.affected_match_cards?.length
          ? `申请 #${response.id} 已通过，联动更新 ${response.affected_match_cards.length} 张配对卡。`
          : `申请 #${response.id} 已通过。`
      });
      message.success("审批通过成功");
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "transfer request 审批失败",
        description: getErrorMessage(err, "审批失败")
      });
    } finally {
      setApprovingId(null);
    }
  }

  async function handleReject(requestId: number) {
    const reviewNote = rejectDrafts[requestId]?.trim();
    if (!reviewNote) {
      setActionFeedback({
        type: "error",
        message: "transfer request 驳回失败",
        description: "请输入驳回原因。"
      });
      return;
    }

    setRejectingId(requestId);
    setActionFeedback(null);
    try {
      const response = await rejectTransferRequest(requestId, reviewNote);
      setRequests((current) => current.filter((item) => item.id !== requestId));
      setRejectDrafts((current) => ({ ...current, [requestId]: "" }));
      setActionFeedback({
        type: "success",
        message: "transfer request 已驳回",
        description: response.review_note ?? `申请 #${response.id} 已驳回。`
      });
      message.success("驳回成功");
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "transfer request 驳回失败",
        description: getErrorMessage(err, "驳回失败")
      });
    } finally {
      setRejectingId(null);
    }
  }

  return (
    <PagePlaceholder
      title="Transfer 审批"
      description="当前页最小接入 transfer request 列表与 approve/reject，用于真实 dev API 联调。"
      extra={
        <Space wrap>
          <Tag color="processing">GET /api/v1/transfer-requests/?status=pending</Tag>
          <Tag color="processing">POST /approve /reject</Tag>
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
            message="transfer request 列表加载失败"
            description={error}
          />
        ) : null}

        <Card title={`transfer request（${requests.length}）`}>
          <Spin spinning={loading}>
            <List
              locale={{ emptyText: "当前没有 transfer request" }}
              dataSource={requests}
              renderItem={(item) => (
                <List.Item
                  key={item.id}
                  actions={[
                    item.status === "pending" ? (
                      <Button
                        key="approve"
                        type="primary"
                        size="small"
                        loading={approvingId === item.id}
                        onClick={() => void handleApprove(item.id)}
                      >
                        通过
                      </Button>
                    ) : null
                  ].filter(Boolean)}
                >
                  <List.Item.Meta
                    title={
                      <Space wrap>
                        <Tag>#{item.id}</Tag>
                        <Tag color={getStatusColor(item.status)}>{item.status}</Tag>
                        <Tag>user #{item.user_id}</Tag>
                        <Tag>{item.from_staff_name ?? item.from_staff_id}</Tag>
                        <Typography.Text>→</Typography.Text>
                        <Tag>{item.to_staff_name ?? item.to_staff_id}</Tag>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={8} style={{ width: "100%" }}>
                        <Typography.Paragraph style={{ marginBottom: 0 }}>
                          申请原因：{item.reason}
                        </Typography.Paragraph>
                        <Typography.Text type="secondary">
                          创建时间：{formatDateTime(item.created_at)}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          审核时间：{formatDateTime(item.reviewed_at)}
                        </Typography.Text>
                        {item.review_note ? (
                          <Typography.Text type="secondary">
                            驳回备注：{item.review_note}
                          </Typography.Text>
                        ) : null}
                        <Space wrap>
                          <Link to={`/users/${item.user_id}`}>查看用户</Link>
                        </Space>
                        {item.status === "pending" ? (
                          <Space wrap>
                            <Input
                              value={rejectDrafts[item.id] ?? ""}
                              placeholder="输入驳回原因"
                              style={{ width: 280 }}
                              onChange={(event) =>
                                setRejectDrafts((current) => ({
                                  ...current,
                                  [item.id]: event.target.value
                                }))
                              }
                            />
                            <Button
                              danger
                              loading={rejectingId === item.id}
                              onClick={() => void handleReject(item.id)}
                            >
                              驳回
                            </Button>
                          </Space>
                        ) : null}
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
