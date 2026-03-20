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
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  approveSuccessApplication,
  getSuccessApplications,
  getSuccessCaseDetail,
  getSuccessCases,
  getSuccessInvalidateReasons,
  invalidateSuccessCase,
  rejectSuccessApplication
} from "../../api/success";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import { authStore } from "../../store/auth";
import type {
  ReasonEnumItem,
  SuccessApplicationItem,
  SuccessCaseDetail,
  SuccessCaseListItem
} from "../../types/success";
import { formatDateTime } from "../../utils/format";

interface ActionFeedback {
  type: "success" | "error";
  message: string;
  description?: string;
}

interface InvalidateValues {
  reason_id?: number;
  reason_note?: string;
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? `${err.message}（HTTP ${err.status}）` : fallback;
}

function getStatusColor(status: string) {
  if (status === "approved" || status === "active") {
    return "success";
  }
  if (status === "rejected" || status === "invalidated") {
    return "error";
  }
  return "processing";
}

export function SuccessPage() {
  const [searchParams] = useSearchParams();
  const [invalidateForm] = Form.useForm<InvalidateValues>();
  const [loadingApplications, setLoadingApplications] = useState(false);
  const [loadingCases, setLoadingCases] = useState(false);
  const [loadingCaseDetail, setLoadingCaseDetail] = useState(false);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [invalidatingId, setInvalidatingId] = useState<number | null>(null);
  const [applicationError, setApplicationError] = useState<string | null>(null);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [caseDetailError, setCaseDetailError] = useState<string | null>(null);
  const [applications, setApplications] = useState<SuccessApplicationItem[]>([]);
  const [cases, setCases] = useState<SuccessCaseListItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [selectedCaseDetail, setSelectedCaseDetail] = useState<SuccessCaseDetail | null>(null);
  const [invalidateReasons, setInvalidateReasons] = useState<ReasonEnumItem[]>([]);
  const [rejectDrafts, setRejectDrafts] = useState<Record<number, string>>({});
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);

  async function loadApplications() {
    setLoadingApplications(true);
    try {
      const response = await getSuccessApplications("pending");
      setApplications(response.results);
      setApplicationError(null);
    } catch (err) {
      setApplications([]);
      setApplicationError(getErrorMessage(err, "success application 加载失败"));
    } finally {
      setLoadingApplications(false);
    }
  }

  async function loadCases() {
    setLoadingCases(true);
    try {
      const [caseResponse, reasonResponse] = await Promise.all([
        getSuccessCases(),
        getSuccessInvalidateReasons()
      ]);
      setCases(caseResponse.results);
      setInvalidateReasons(reasonResponse.results);
      setCaseError(null);
    } catch (err) {
      setCases([]);
      setCaseError(getErrorMessage(err, "success case 加载失败"));
    } finally {
      setLoadingCases(false);
    }
  }

  async function loadCaseDetail(caseId: number) {
    setLoadingCaseDetail(true);
    try {
      const response = await getSuccessCaseDetail(caseId);
      setSelectedCaseDetail(response);
      setCases((current) =>
        current.map((item) =>
          item.id === response.id
            ? {
                ...item,
                status: response.status,
                invalidated_at: response.invalidated_at,
                invalidated_reason_id: response.invalidated_reason_id,
                invalidated_reason_label: response.invalidated_reason_label,
                invalidated_reason_note: response.invalidated_reason_note,
                updated_at: response.updated_at
              }
            : item
        )
      );
      setCaseDetailError(null);
    } catch (err) {
      setSelectedCaseDetail(null);
      setCaseDetailError(getErrorMessage(err, "success case 详情加载失败"));
    } finally {
      setLoadingCaseDetail(false);
    }
  }

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      authStore.setToken(token);
    }

    void Promise.all([loadApplications(), loadCases()]);
  }, [searchParams]);

  async function refreshAll() {
    await Promise.all([loadApplications(), loadCases()]);
    if (selectedCaseId) {
      await loadCaseDetail(selectedCaseId);
    }
  }

  async function handleApprove(applicationId: number) {
    setApprovingId(applicationId);
    setActionFeedback(null);
    try {
      const response = await approveSuccessApplication(applicationId);
      setApplications((current) => current.filter((item) => item.id !== applicationId));
      if (response.success_case_id) {
        setSelectedCaseId(response.success_case_id);
        setCases((current) => [
          {
            id: response.success_case_id,
            application_id: response.id,
            match_card_id: applications.find((item) => item.id === applicationId)?.match_card_id ?? 0,
            status: "active",
            approved_at: response.reviewed_at ?? null,
            invalidated_reason_id: null,
            invalidated_reason_label: null,
            invalidated_reason_note: null,
            invalidated_at: null,
            updated_at: response.reviewed_at ?? null
          },
          ...current.filter((item) => item.id !== response.success_case_id)
        ]);
        await loadCaseDetail(response.success_case_id);
      }
      setActionFeedback({
        type: "success",
        message: "success application 审批通过",
        description: response.success_case_id
          ? `申请 #${response.id} 已通过，success case #${response.success_case_id} 已生成。`
          : `申请 #${response.id} 已通过。`
      });
      message.success("审批通过成功");
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "success application 审批失败",
        description: getErrorMessage(err, "审批失败")
      });
    } finally {
      setApprovingId(null);
    }
  }

  async function handleReject(applicationId: number) {
    const reviewNote = rejectDrafts[applicationId]?.trim();
    if (!reviewNote) {
      setActionFeedback({
        type: "error",
        message: "success application 驳回失败",
        description: "请输入驳回原因。"
      });
      return;
    }
    setRejectingId(applicationId);
    setActionFeedback(null);
    try {
      const response = await rejectSuccessApplication(applicationId, reviewNote);
      await loadApplications();
      setRejectDrafts((current) => ({ ...current, [applicationId]: "" }));
      setActionFeedback({
        type: "success",
        message: "success application 已驳回",
        description: response.review_note ?? `申请 #${response.id} 已驳回。`
      });
      message.success("驳回成功");
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "success application 驳回失败",
        description: getErrorMessage(err, "驳回失败")
      });
    } finally {
      setRejectingId(null);
    }
  }

  async function handleInvalidate(values: InvalidateValues) {
    if (!selectedCaseId) {
      return;
    }
    setInvalidatingId(selectedCaseId);
    setActionFeedback(null);
    try {
      const response = await invalidateSuccessCase(selectedCaseId, values.reason_id!, values.reason_note);
      const selectedReason = invalidateReasons.find((item) => item.id === values.reason_id);
      setCases((current) =>
        current.map((item) =>
          item.id === selectedCaseId
            ? {
                ...item,
                status: "invalidated",
                invalidated_reason_id: values.reason_id ?? null,
                invalidated_reason_label: selectedReason?.label ?? null,
                invalidated_reason_note: values.reason_note?.trim() || null,
                invalidated_at: response.invalidated_at ?? null,
                updated_at: response.invalidated_at ?? null
              }
            : item
        )
      );
      setSelectedCaseDetail((current) =>
        current && current.id === selectedCaseId
          ? {
              ...current,
              status: "invalidated",
              match_card_stage: "ended",
              invalidated_reason_id: values.reason_id ?? null,
              invalidated_reason_label: selectedReason?.label ?? null,
              invalidated_reason_note: values.reason_note?.trim() || null,
              invalidated_at: response.invalidated_at ?? null,
              updated_at: response.invalidated_at ?? null
            }
          : current
      );
      invalidateForm.resetFields();
      setActionFeedback({
        type: "success",
        message: "success case 已作废",
        description: response.message ?? `success case #${response.id} 已作废。`
      });
      message.success("作废成功");
    } catch (err) {
      setActionFeedback({
        type: "error",
        message: "success case 作废失败",
        description: getErrorMessage(err, "作废失败")
      });
    } finally {
      setInvalidatingId(null);
    }
  }

  return (
    <PagePlaceholder
      title="Success 审批"
      description="当前页最小接入 success application 列表、approve/reject 和 success case invalidate。"
      extra={
        <Space wrap>
          <Tag color="processing">GET /api/v1/success-applications/</Tag>
          <Tag color="processing">POST /approve /reject /invalidate</Tag>
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

        {applicationError ? (
          <Alert type="error" showIcon message="success application 加载失败" description={applicationError} />
        ) : null}

        <Card title={`success application（${applications.length}）`}>
          <Spin spinning={loadingApplications}>
            <List
              locale={{ emptyText: "当前没有 success application" }}
              dataSource={applications}
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
                        <Tag color="processing">match_card #{item.match_card_id}</Tag>
                        <Typography.Text>{item.applicant_name ?? item.applicant_id ?? "-"}</Typography.Text>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={8} style={{ width: "100%" }}>
                        <Typography.Paragraph style={{ marginBottom: 0 }}>
                          申请备注：{item.apply_note ?? "-"}
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
                          <Link to={`/match-cards/${item.match_card_id}`}>查看配对卡</Link>
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

        {caseError ? (
          <Alert type="error" showIcon message="success case 加载失败" description={caseError} />
        ) : null}

        <Card title={`success case（${cases.length}）`}>
          <Spin spinning={loadingCases}>
            <List
              locale={{ emptyText: "当前没有 success case" }}
              dataSource={cases}
              renderItem={(item) => (
                <List.Item
                  key={item.id}
                  actions={[
                    <Button
                      key="view"
                      type="link"
                      onClick={() => {
                        setSelectedCaseId(item.id);
                        void loadCaseDetail(item.id);
                      }}
                    >
                      查看
                    </Button>
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space wrap>
                        <Tag>#{item.id}</Tag>
                        <Tag color={getStatusColor(item.status)}>{item.status}</Tag>
                        <Tag color="processing">match_card #{item.match_card_id}</Tag>
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={4}>
                        <Typography.Text type="secondary">
                          审批通过：{formatDateTime(item.approved_at)}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          作废时间：{formatDateTime(item.invalidated_at)}
                        </Typography.Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Spin>
        </Card>

        <Card title={selectedCaseId ? `success case 详情 #${selectedCaseId}` : "success case 详情"}>
          {caseDetailError ? (
            <Alert type="error" showIcon message="success case 详情加载失败" description={caseDetailError} />
          ) : null}
          <Spin spinning={loadingCaseDetail}>
            {selectedCaseDetail ? (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Descriptions bordered column={2}>
                  <Descriptions.Item label="case ID">{selectedCaseDetail.id}</Descriptions.Item>
                  <Descriptions.Item label="状态">
                    {selectedCaseDetail.status}
                  </Descriptions.Item>
                  <Descriptions.Item label="match_card">
                    <Link to={`/match-cards/${selectedCaseDetail.match_card_id}`}>
                      {selectedCaseDetail.match_card_id}
                    </Link>
                  </Descriptions.Item>
                  <Descriptions.Item label="阶段">
                    {selectedCaseDetail.match_card_stage ?? "-"}
                  </Descriptions.Item>
                  <Descriptions.Item label="approved_at">
                    {formatDateTime(selectedCaseDetail.approved_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="invalidated_at">
                    {formatDateTime(selectedCaseDetail.invalidated_at)}
                  </Descriptions.Item>
                </Descriptions>

                <List
                  header={`success followup（${selectedCaseDetail.follow_ups?.length ?? 0}）`}
                  locale={{ emptyText: "当前没有 success followup" }}
                  dataSource={selectedCaseDetail.follow_ups ?? []}
                  renderItem={(item) => (
                    <List.Item key={item.id}>
                      <List.Item.Meta
                        title={
                          <Space wrap>
                            <Tag>#{item.id}</Tag>
                            <Tag>{item.staff_name ?? "-"}</Tag>
                            <Tag>{item.is_still_contact ?? "-"}</Tag>
                            <Tag>{item.next_remind_mode ?? "-"}</Tag>
                            {item.is_valid_visit ? <Tag color="success">有效回访</Tag> : null}
                          </Space>
                        }
                        description={
                          <Space direction="vertical" size={4}>
                            <Typography.Paragraph style={{ marginBottom: 0 }}>
                              {item.content ?? "-"}
                            </Typography.Paragraph>
                            <Typography.Text type="secondary">
                              创建时间：{formatDateTime(item.created_at)}
                            </Typography.Text>
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />

                {selectedCaseDetail.status === "active" ? (
                  <Form
                    form={invalidateForm}
                    layout="vertical"
                    onFinish={(values) => void handleInvalidate(values)}
                  >
                    <Form.Item
                      label="作废原因"
                      name="reason_id"
                      rules={[{ required: true, message: "请选择作废原因" }]}
                    >
                      <Select
                        placeholder="选择 success_invalidate 原因"
                        options={invalidateReasons.map((item) => ({
                          value: item.id,
                          label: item.label
                        }))}
                      />
                    </Form.Item>
                    <Form.Item label="补充说明" name="reason_note">
                      <Input.TextArea rows={3} maxLength={500} showCount />
                    </Form.Item>
                    <Button type="primary" danger htmlType="submit" loading={invalidatingId === selectedCaseDetail.id}>
                      标记失效
                    </Button>
                  </Form>
                ) : null}
              </Space>
            ) : (
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                请选择一个 success case 查看详情。
              </Typography.Paragraph>
            )}
          </Spin>
        </Card>
      </Space>
    </PagePlaceholder>
  );
}
