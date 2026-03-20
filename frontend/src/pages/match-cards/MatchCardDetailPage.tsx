import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  List,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message
} from "antd";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  createMatchedFollowUp,
  getFollowUpDetail,
  getMatchCardMatchedFollowUps,
  updateFollowUp
} from "../../api/followUps";
import { getMatchCardDetail } from "../../api/matchCards";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import { authStore } from "../../store/auth";
import type {
  FollowUpRecord,
  MatchCardDetail,
  FollowUpUpdatePayload,
  MatchedFollowUpCreatePayload
} from "../../types/matchCard";
import { formatDateTime } from "../../utils/format";

interface MatchedFollowUpFormValues {
  user_id?: number;
  content?: string;
  is_still_contact?: "yes" | "no" | "unknown";
  risk_status?: "none" | "watching" | "high_risk";
  next_remind_mode?: "manual" | "default";
  next_remind_at?: string;
}

interface MatchedFollowUpEditValues {
  content?: string;
  next_remind_mode?: "manual" | "default";
  next_remind_at?: string;
}

interface ActionFeedback {
  type: "success" | "error";
  message: string;
  description?: string;
}

const CONTACT_STATUS_OPTIONS = [
  { value: "yes", label: "仍联系" },
  { value: "no", label: "已不联系" },
  { value: "unknown", label: "待确认" }
] as const;

const RISK_STATUS_OPTIONS = [
  { value: "none", label: "无风险" },
  { value: "watching", label: "关注中" },
  { value: "high_risk", label: "高风险" }
] as const;

const NEXT_REMIND_MODE_OPTIONS = [
  { value: "default", label: "默认节奏" },
  { value: "manual", label: "手动提醒" }
] as const;

function toDatetimeLocalValue(value?: string | null) {
  if (!value) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function toApiDateTime(value?: string) {
  if (!value) {
    return undefined;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toISOString();
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? `${err.message}（HTTP ${err.status}）` : fallback;
}

export function MatchCardDetailPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const [createForm] = Form.useForm<MatchedFollowUpFormValues>();
  const [editForm] = Form.useForm<MatchedFollowUpEditValues>();
  const matchCardId = params.id ?? "-";
  const [loading, setLoading] = useState(false);
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [followUpError, setFollowUpError] = useState<string | null>(null);
  const [detail, setDetail] = useState<MatchCardDetail | null>(null);
  const [followUps, setFollowUps] = useState<FollowUpRecord[]>([]);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);
  const [editingFollowUpId, setEditingFollowUpId] = useState<number | null>(null);

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      authStore.setToken(token);
    }

    if (!params.id) {
      setError("未提供 match_card id");
      setDetail(null);
      return;
    }

    let active = true;

    async function loadDetail() {
      setLoading(true);
      try {
        const response = await getMatchCardDetail(params.id!);
        if (!active) {
          return;
        }
        setError(null);
        setDetail(response);
        const currentValues = createForm.getFieldsValue();
        createForm.setFieldsValue({
          user_id: currentValues.user_id ?? response.male_user_id,
          next_remind_mode: currentValues.next_remind_mode ?? "default",
          is_still_contact: currentValues.is_still_contact ?? "yes",
          risk_status: currentValues.risk_status ?? "none"
        });
      } catch (err) {
        if (!active) {
          return;
        }
        setError(getErrorMessage(err, "配对卡详情加载失败"));
        setDetail(null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    async function loadFollowUps() {
      setFollowUpLoading(true);
      try {
        const response = await getMatchCardMatchedFollowUps(params.id!);
        if (!active) {
          return;
        }
        setFollowUps(response.results);
        setFollowUpError(null);
      } catch (err) {
        if (!active) {
          return;
        }
        setFollowUpError(getErrorMessage(err, "matched followup 加载失败"));
        setFollowUps([]);
      } finally {
        if (active) {
          setFollowUpLoading(false);
        }
      }
    }

    setError(null);
    setActionFeedback(null);
    void loadDetail();
    void loadFollowUps();

    return () => {
      active = false;
    };
  }, [createForm, params.id, searchParams]);

  async function reloadMatchedFollowUps() {
    if (!params.id) {
      return;
    }
    setFollowUpLoading(true);
    try {
      const response = await getMatchCardMatchedFollowUps(params.id);
      setFollowUps(response.results);
      setFollowUpError(null);
    } catch (err) {
      setFollowUpError(getErrorMessage(err, "matched followup 加载失败"));
    } finally {
      setFollowUpLoading(false);
    }
  }

  async function reloadDetail() {
    if (!params.id) {
      return;
    }
    try {
      const response = await getMatchCardDetail(params.id);
      setError(null);
      setDetail(response);
    } catch (err) {
      setError(getErrorMessage(err, "配对卡详情加载失败"));
    }
  }

  const isMatchedStageEditable =
    detail?.stage === "initial_contact" || detail?.stage === "stable_contact";

  const canCreateMatchedFollowUp = Boolean(detail && isMatchedStageEditable);

  async function handleCreate(values: MatchedFollowUpFormValues) {
    if (!detail) {
      return;
    }

    const payload: MatchedFollowUpCreatePayload = {
      scene: "matched",
      match_card_id: detail.id,
      user_id: values.user_id!,
      content: values.content!.trim(),
      is_still_contact: values.is_still_contact!,
      risk_status: values.risk_status!,
      next_remind_mode: values.next_remind_mode!
    };

    const nextRemindAt = toApiDateTime(values.next_remind_at);
    if (payload.next_remind_mode === "manual") {
      payload.next_remind_at = nextRemindAt;
    }

    setCreating(true);
    setActionFeedback(null);
    try {
      const response = await createMatchedFollowUp(payload);
      await Promise.all([reloadMatchedFollowUps(), reloadDetail()]);
      createForm.resetFields(["content", "next_remind_at"]);
      createForm.setFieldValue("user_id", values.user_id);
      createForm.setFieldValue("is_still_contact", values.is_still_contact);
      createForm.setFieldValue("risk_status", values.risk_status);
      createForm.setFieldValue("next_remind_mode", values.next_remind_mode);
      setActionFeedback({
        type: "success",
        message: "matched followup 创建成功",
        description: `已创建 followup #${response.id}。`
      });
      message.success("matched followup 创建成功");
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "matched followup 创建失败",
        description: getErrorMessage(err, "matched followup 创建失败")
      });
    } finally {
      setCreating(false);
    }
  }

  async function handleStartEdit(followUpId: number) {
    setEditingFollowUpId(followUpId);
    setActionFeedback(null);
    try {
      const detailResponse = await getFollowUpDetail(followUpId);
      editForm.setFieldsValue({
        content: detailResponse.content ?? undefined,
        next_remind_mode:
          detailResponse.next_remind_mode === "manual" ? "manual" : "default",
        next_remind_at: toDatetimeLocalValue(detailResponse.next_remind_at)
      });
      setFollowUpError(null);
    } catch (err) {
      setEditingFollowUpId(null);
      setActionFeedback({
        type: "error",
        message: "followup 加载失败",
        description: getErrorMessage(err, "followup 加载失败")
      });
    }
  }

  function handleCancelEdit() {
    setEditingFollowUpId(null);
    editForm.resetFields();
  }

  async function handleEdit(values: MatchedFollowUpEditValues) {
    if (!editingFollowUpId) {
      return;
    }

    const payload: FollowUpUpdatePayload = {
      content: values.content?.trim(),
      next_remind_mode: values.next_remind_mode
    };
    if (values.next_remind_mode === "manual") {
      payload.next_remind_at = toApiDateTime(values.next_remind_at);
    } else if (values.next_remind_mode === "default") {
      payload.next_remind_at = null;
    }

    setEditing(true);
    setActionFeedback(null);
    try {
      const response = await updateFollowUp(editingFollowUpId, payload);
      await Promise.all([reloadMatchedFollowUps(), reloadDetail()]);
      setActionFeedback({
        type: "success",
        message: "matched followup 编辑成功",
        description: `已更新 followup #${response.id}。`
      });
      message.success("matched followup 编辑成功");
      handleCancelEdit();
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "matched followup 编辑失败",
        description: getErrorMessage(err, "matched followup 编辑失败")
      });
    } finally {
      setEditing(false);
    }
  }

  return (
    <PagePlaceholder
      title={`配对卡详情 #${matchCardId}`}
      description="当前页在真实 match card 详情基础上，最小接入 matched followup 创建、展示和编辑。"
      extra={
        <Space wrap>
          <Tag color="processing">接口：GET /api/v1/match-cards/{'{id}'}/</Tag>
          <Tag color="processing">接口：POST/PATCH/GET /api/v1/follow-ups/</Tag>
        </Space>
      }
    >
      {!detail && error ? (
        <Alert
          type="error"
          showIcon
          message="配对卡详情加载失败"
          description={error}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Spin spinning={loading}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card title="核心详情">
            {detail ? (
              <Descriptions column={2} bordered>
                <Descriptions.Item label="配对卡ID">{detail.id}</Descriptions.Item>
                <Descriptions.Item label="阶段">
                  {detail.stage_display ?? detail.stage ?? "-"}
                </Descriptions.Item>
                <Descriptions.Item label="男方">
                  <Link to={`/users/${detail.male_user_id}`}>
                    {detail.male_user_name ?? detail.male_user_id}
                  </Link>
                </Descriptions.Item>
                <Descriptions.Item label="女方">
                  <Link to={`/users/${detail.female_user_id}`}>
                    {detail.female_user_name ?? detail.female_user_id}
                  </Link>
                </Descriptions.Item>
                <Descriptions.Item label="主负责红娘">
                  {detail.primary_staff_name ?? detail.primary_staff_id ?? "-"}
                </Descriptions.Item>
                <Descriptions.Item label="风险等级">
                  {detail.risk_level_display ?? detail.risk_level ?? "-"}
                </Descriptions.Item>
                <Descriptions.Item label="下一次提醒">
                  {formatDateTime(detail.next_remind_at)}
                </Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {formatDateTime(detail.created_at)}
                </Descriptions.Item>
                <Descriptions.Item label="有效回访数">
                  {detail.valid_visit_count ?? followUps.filter((item) => item.is_valid_visit).length}
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                当前没有可展示的配对卡详情。
              </Typography.Paragraph>
            )}
          </Card>

          <Card
            title="matched followup"
            extra={
              detail ? (
                <Space wrap>
                  <Tag color={isMatchedStageEditable ? "success" : "default"}>
                    当前阶段：{detail.stage_display ?? detail.stage}
                  </Tag>
                  <Tag color="processing">只支持 initial_contact / stable_contact</Tag>
                </Space>
              ) : null
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

              {!canCreateMatchedFollowUp && detail ? (
                <Alert
                  type="info"
                  showIcon
                  message="当前阶段不开放 matched followup 创建"
                  description="本轮只支持 initial_contact / stable_contact。"
                />
              ) : null}

              {followUpError ? (
                <Alert
                  type="error"
                  showIcon
                  message="matched followup 加载失败"
                  description={followUpError}
                />
              ) : null}

              {canCreateMatchedFollowUp ? (
                <Form
                  form={createForm}
                  layout="vertical"
                  onFinish={(values) => void handleCreate(values)}
                  initialValues={{
                    user_id: detail?.male_user_id,
                    is_still_contact: "yes",
                    risk_status: "none",
                    next_remind_mode: "default"
                  }}
                >
                  <Descriptions column={2} bordered size="small" style={{ marginBottom: 16 }}>
                    <Descriptions.Item label="男方">
                      {detail?.male_user_name ?? detail?.male_user_id ?? "-"}
                    </Descriptions.Item>
                    <Descriptions.Item label="女方">
                      {detail?.female_user_name ?? detail?.female_user_id ?? "-"}
                    </Descriptions.Item>
                  </Descriptions>

                  <Form.Item
                    label="回访归属"
                    name="user_id"
                    rules={[{ required: true, message: "请选择回访归属" }]}
                  >
                    <Select
                      options={[
                        {
                          value: detail?.male_user_id,
                          label: `男方：${detail?.male_user_name ?? detail?.male_user_id ?? "-"}`
                        },
                        {
                          value: detail?.female_user_id,
                          label: `女方：${detail?.female_user_name ?? detail?.female_user_id ?? "-"}`
                        }
                      ]}
                    />
                  </Form.Item>

                  <Form.Item
                    label="跟进内容"
                    name="content"
                    rules={[{ required: true, message: "请输入跟进内容" }]}
                  >
                    <Input.TextArea rows={4} maxLength={500} showCount />
                  </Form.Item>

                  <Space size={16} align="start" wrap style={{ width: "100%" }}>
                    <Form.Item
                      label="是否仍联系"
                      name="is_still_contact"
                      rules={[{ required: true, message: "请选择联系状态" }]}
                      style={{ minWidth: 180, marginBottom: 0 }}
                    >
                      <Select options={[...CONTACT_STATUS_OPTIONS]} />
                    </Form.Item>
                    <Form.Item
                      label="风险状态"
                      name="risk_status"
                      rules={[{ required: true, message: "请选择风险状态" }]}
                      style={{ minWidth: 180, marginBottom: 0 }}
                    >
                      <Select options={[...RISK_STATUS_OPTIONS]} />
                    </Form.Item>
                    <Form.Item
                      label="提醒方式"
                      name="next_remind_mode"
                      rules={[{ required: true, message: "请选择提醒方式" }]}
                      style={{ minWidth: 180, marginBottom: 0 }}
                    >
                      <Select options={[...NEXT_REMIND_MODE_OPTIONS]} />
                    </Form.Item>
                    <Form.Item
                      noStyle
                      shouldUpdate={(prev, current) =>
                        prev.next_remind_mode !== current.next_remind_mode
                      }
                    >
                      {({ getFieldValue }) =>
                        getFieldValue("next_remind_mode") === "manual" ? (
                          <Form.Item
                            label="手动提醒时间"
                            name="next_remind_at"
                            rules={[{ required: true, message: "请输入手动提醒时间" }]}
                            style={{ minWidth: 240, marginBottom: 0 }}
                          >
                            <Input type="datetime-local" />
                          </Form.Item>
                        ) : null
                      }
                    </Form.Item>
                  </Space>

                  <Button type="primary" htmlType="submit" loading={creating} style={{ marginTop: 16 }}>
                    创建 matched followup
                  </Button>
                </Form>
              ) : null}

              <Spin spinning={followUpLoading}>
                <List
                  header={`已创建 followup（${followUps.length}）`}
                  locale={{ emptyText: "当前没有 matched followup" }}
                  dataSource={followUps}
                  renderItem={(item) => (
                    <List.Item
                      key={item.id}
                      actions={
                        isMatchedStageEditable
                          ? [
                              <Button
                                key="edit"
                                type="link"
                                onClick={() => void handleStartEdit(item.id)}
                              >
                                编辑
                              </Button>
                            ]
                          : []
                      }
                    >
                      <List.Item.Meta
                        title={
                          <Space wrap>
                            <Tag>#{item.id}</Tag>
                            <Tag color="processing">{item.staff_name ?? "-"}</Tag>
                            {item.user_id === detail?.male_user_id ? <Tag color="blue">男方侧</Tag> : null}
                            {item.user_id === detail?.female_user_id ? <Tag color="magenta">女方侧</Tag> : null}
                            <Tag>{item.is_still_contact ?? "-"}</Tag>
                            <Tag color={item.risk_status === "high_risk" ? "error" : item.risk_status === "watching" ? "warning" : "success"}>
                              {item.risk_status ?? "-"}
                            </Tag>
                            <Tag>{item.next_remind_mode ?? "-"}</Tag>
                            {item.is_valid_visit ? <Tag color="success">有效回访</Tag> : null}
                            <Typography.Text type="secondary">
                              {formatDateTime(item.created_at)}
                            </Typography.Text>
                          </Space>
                        }
                        description={
                          <Space direction="vertical" size={4} style={{ width: "100%" }}>
                            <Typography.Paragraph style={{ marginBottom: 0 }}>
                              {item.content ?? "-"}
                            </Typography.Paragraph>
                            <Typography.Text type="secondary">
                              下次提醒：{formatDateTime(item.next_remind_at)}
                            </Typography.Text>
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
              </Spin>

              {editingFollowUpId ? (
                <Card size="small" title={`编辑 followup #${editingFollowUpId}`}>
                  <Form
                    form={editForm}
                    layout="vertical"
                    onFinish={(values) => void handleEdit(values)}
                    initialValues={{ next_remind_mode: "default" }}
                  >
                    <Form.Item
                      label="跟进内容"
                      name="content"
                      rules={[{ required: true, message: "请输入跟进内容" }]}
                    >
                      <Input.TextArea rows={4} maxLength={500} showCount />
                    </Form.Item>
                    <Space size={16} align="start" wrap>
                      <Form.Item
                        label="提醒方式"
                        name="next_remind_mode"
                        rules={[{ required: true, message: "请选择提醒方式" }]}
                        style={{ minWidth: 180, marginBottom: 0 }}
                      >
                        <Select options={[...NEXT_REMIND_MODE_OPTIONS]} />
                      </Form.Item>
                      <Form.Item
                        noStyle
                        shouldUpdate={(prev, current) =>
                          prev.next_remind_mode !== current.next_remind_mode
                        }
                      >
                        {({ getFieldValue }) =>
                          getFieldValue("next_remind_mode") === "manual" ? (
                            <Form.Item
                              label="手动提醒时间"
                              name="next_remind_at"
                              rules={[{ required: true, message: "请输入手动提醒时间" }]}
                              style={{ minWidth: 240, marginBottom: 0 }}
                            >
                              <Input type="datetime-local" />
                            </Form.Item>
                          ) : null
                        }
                      </Form.Item>
                    </Space>
                    <Space style={{ marginTop: 16 }}>
                      <Button type="primary" htmlType="submit" loading={editing}>
                        保存编辑
                      </Button>
                      <Button onClick={handleCancelEdit}>取消</Button>
                    </Space>
                  </Form>
                </Card>
              ) : null}
            </Space>
          </Card>
        </Space>
      </Spin>
    </PagePlaceholder>
  );
}
