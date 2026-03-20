import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Space,
  Table,
  Tag,
  Typography
} from "antd";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  createMatchCard,
  createRecommendationBatch,
  getCandidateSearch,
  getRecommendationHistory,
  selectRecommendationCandidate
} from "../../api/recommendations";
import { getUserDetail } from "../../api/users";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import { authStore } from "../../store/auth";
import type {
  CandidateSearchItem,
  CandidateSearchResponse,
  MatchCardSummary,
  RecommendationBatchCreateResponse,
  RecommendationCandidateItem,
  RecommendationHistoryItem
} from "../../types/recommendation";
import { formatDateTime } from "../../utils/format";

interface CandidateSearchFormValues {
  user_id?: number;
  search?: string;
}

interface HistoryFormValues {
  user_id?: number;
}

interface ActionFeedback {
  type: "success" | "error";
  message: string;
  description?: string;
}

function parseIdList(rawValue: string | null) {
  if (!rawValue) {
    return [];
  }

  return rawValue
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item) && item > 0);
}

export function RecommendationPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [candidateForm] = Form.useForm<CandidateSearchFormValues>();
  const [historyForm] = Form.useForm<HistoryFormValues>();
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [createBatchLoading, setCreateBatchLoading] = useState(false);
  const [selectingCandidateId, setSelectingCandidateId] = useState<number | null>(null);
  const [creatingMatchCardCandidateId, setCreatingMatchCardCandidateId] = useState<number | null>(null);
  const [candidateError, setCandidateError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [candidateResult, setCandidateResult] = useState<CandidateSearchResponse | null>(null);
  const [historyResult, setHistoryResult] = useState<RecommendationHistoryItem[] | null>(null);
  const [selectedCandidateUserIds, setSelectedCandidateUserIds] = useState<number[]>([]);
  const [latestBatch, setLatestBatch] = useState<RecommendationBatchCreateResponse | null>(null);
  const [createdMatchCard, setCreatedMatchCard] = useState<MatchCardSummary | null>(null);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);
  const automationRef = useRef<string | null>(null);

  useEffect(() => {
    const token = searchParams.get("token");
    const candidateUserId = searchParams.get("candidate_user_id");
    const historyUserId = searchParams.get("history_user_id");
    const keyword = searchParams.get("search") ?? "";

    if (token) {
      authStore.setToken(token);
    }

    candidateForm.setFieldsValue({
      user_id: candidateUserId ? Number(candidateUserId) : undefined,
      search: keyword
    });
    historyForm.setFieldsValue({
      user_id: historyUserId ? Number(historyUserId) : undefined
    });

    if (candidateUserId) {
      void loadCandidateSearch({
        user_id: Number(candidateUserId),
        search: keyword
      });
    }

    if (historyUserId) {
      void loadRecommendationHistory(Number(historyUserId));
    }
  }, [candidateForm, historyForm, searchParams]);

  useEffect(() => {
    if (!candidateResult) {
      setSelectedCandidateUserIds([]);
      return;
    }

    const validIds = new Set(candidateResult.results.map((item) => item.id));
    setSelectedCandidateUserIds((current) => current.filter((id) => validIds.has(id)));
  }, [candidateResult]);

  useEffect(() => {
    const autoCreateCandidateUserIds = parseIdList(searchParams.get("create_candidate_user_ids"));
    const autoSelectCandidateUserId = Number(searchParams.get("auto_select_candidate_user_id") || 0);
    const autoBuildCandidateUserId = Number(searchParams.get("auto_build_candidate_user_id") || 0);
    const targetUserId = Number(searchParams.get("candidate_user_id") || 0);
    const automationKey = [
      targetUserId,
      autoCreateCandidateUserIds.join(","),
      autoSelectCandidateUserId,
      autoBuildCandidateUserId
    ].join("|");

    if (!targetUserId || autoCreateCandidateUserIds.length === 0) {
      automationRef.current = null;
      return;
    }
    if (automationRef.current === automationKey) {
      return;
    }

    automationRef.current = automationKey;

    void (async () => {
      try {
        const batch = await handleCreateBatchByValues({
          user_id: targetUserId,
          candidate_user_ids: autoCreateCandidateUserIds
        });

        if (!batch || !autoSelectCandidateUserId) {
          return;
        }

        const selectedCandidate = batch.candidates.find(
          (candidate) => candidate.candidate_user_id === autoSelectCandidateUserId
        );
        if (!selectedCandidate) {
          return;
        }

        const nextBatch = await handleSelectCandidate(batch, selectedCandidate);
        if (!nextBatch || !autoBuildCandidateUserId || selectedCandidate.candidate_user_id !== autoBuildCandidateUserId) {
          return;
        }

        const buildCandidate =
          nextBatch.candidates.find((candidate) => candidate.candidate_user_id === autoBuildCandidateUserId) ||
          selectedCandidate;
        await handleCreateMatchCard(nextBatch, buildCandidate);
      } catch {
        // Action-level feedback is already set in the called handlers.
      }
    })();
  }, [searchParams]);

  async function loadCandidateSearch(values: CandidateSearchFormValues) {
    if (!values.user_id) {
      setCandidateResult(null);
      return null;
    }
    setCandidateLoading(true);
    setCandidateError(null);
    try {
      const response = await getCandidateSearch({
        user_id: values.user_id,
        search: values.search?.trim() || undefined
      });
      setCandidateResult(response);
      return response;
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `${err.message}（HTTP ${err.status}）`
          : "候选搜索加载失败";
      setCandidateError(message);
      setCandidateResult(null);
      return null;
    } finally {
      setCandidateLoading(false);
    }
  }

  async function loadRecommendationHistory(userId: number) {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const response = await getRecommendationHistory(userId);
      setHistoryResult(response);
      return response;
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `${err.message}（HTTP ${err.status}）`
          : "推荐历史加载失败";
      setHistoryError(message);
      setHistoryResult(null);
      return null;
    } finally {
      setHistoryLoading(false);
    }
  }

  async function refreshHistoryForUser(userId: number) {
    const response = await loadRecommendationHistory(userId);
    return response;
  }

  async function handleCreateBatchByValues(payload: {
    user_id: number;
    candidate_user_ids: number[];
  }) {
    if (payload.candidate_user_ids.length === 0) {
      setActionFeedback({
        type: "error",
        message: "创建 recommendation 失败",
        description: "请至少勾选一个候选人。"
      });
      return null;
    }

    setCreateBatchLoading(true);
    setActionFeedback(null);
    setCreatedMatchCard(null);
    try {
      const response = await createRecommendationBatch(payload);
      setLatestBatch(response);
      await refreshHistoryForUser(payload.user_id);
      historyForm.setFieldsValue({ user_id: payload.user_id });
      setActionFeedback({
        type: "success",
        message: "recommendation 创建成功",
        description: response.warnings?.length
          ? `批次 ${response.batch_no} 已创建，存在重复推荐提示。`
          : `批次 ${response.batch_no} 已创建。`
      });
      return response;
    } catch (err) {
      const description =
        err instanceof ApiError
          ? `${err.message}（HTTP ${err.status}）`
          : "创建 recommendation 失败";
      setActionFeedback({
        type: "error",
        message: "recommendation 创建失败",
        description
      });
      return null;
    } finally {
      setCreateBatchLoading(false);
    }
  }

  async function handleCreateBatch() {
    const values = await candidateForm.validateFields();
    if (!values.user_id) {
      return;
    }
    const batch = await handleCreateBatchByValues({
      user_id: values.user_id,
      candidate_user_ids: selectedCandidateUserIds
    });
    if (!batch) {
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("history_user_id", String(values.user_id));
    setSearchParams(nextParams, { replace: true });
  }

  async function handleSelectCandidate(batch: RecommendationHistoryItem, candidate: RecommendationCandidateItem) {
    setSelectingCandidateId(candidate.id);
    setActionFeedback(null);
    setCreatedMatchCard(null);
    try {
      const response = await selectRecommendationCandidate(candidate.id);
      const refreshed = await refreshHistoryForUser(batch.user_id);
      const nextBatch = refreshed?.find((item) => item.id === batch.id) || {
        ...batch,
        candidates: batch.candidates.map((item) =>
          item.id === response.id ? { ...item, is_selected: response.is_selected } : item
        )
      };
      setLatestBatch(nextBatch as RecommendationBatchCreateResponse);
      setActionFeedback({
        type: "success",
        message: "candidate 选中成功",
        description: `${response.candidate_user_name} 已标记为 selected_pending_meet。`
      });
      return nextBatch;
    } catch (err) {
      const description =
        err instanceof ApiError
          ? `${err.message}（HTTP ${err.status}）`
          : "候选选中失败";
      setActionFeedback({
        type: "error",
        message: "candidate 选中失败",
        description
      });
      return null;
    } finally {
      setSelectingCandidateId(null);
    }
  }

  async function handleCreateMatchCard(batch: RecommendationHistoryItem, candidate: RecommendationCandidateItem) {
    setCreatingMatchCardCandidateId(candidate.id);
    setActionFeedback(null);
    try {
      const [targetUser, candidateUser] = await Promise.all([
        getUserDetail(String(batch.user_id)),
        getUserDetail(String(candidate.candidate_user_id))
      ]);

      const maleUserId = targetUser.gender === "male" ? targetUser.id : candidateUser.id;
      const femaleUserId = targetUser.gender === "female" ? targetUser.id : candidateUser.id;

      const response = await createMatchCard({
        male_user_id: maleUserId,
        female_user_id: femaleUserId,
        candidate_id: candidate.id
      });

      setCreatedMatchCard(response);
      setActionFeedback({
        type: "success",
        message: "建卡成功",
        description: `已生成配对卡 #${response.id}。`
      });
      return response;
    } catch (err) {
      const description =
        err instanceof ApiError
          ? `${err.message}（HTTP ${err.status}）`
          : "建卡失败";
      setActionFeedback({
        type: "error",
        message: "建卡失败",
        description
      });
      return null;
    } finally {
      setCreatingMatchCardCandidateId(null);
    }
  }

  const handleCandidateSubmit = async () => {
    const values = await candidateForm.validateFields();
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("candidate_user_id", String(values.user_id));
    nextParams.set("search", values.search?.trim() || "");
    setSearchParams(nextParams, { replace: true });
    await loadCandidateSearch(values);
  };

  const handleHistorySubmit = async () => {
    const values = await historyForm.validateFields();
    if (!values.user_id) {
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("history_user_id", String(values.user_id));
    setSearchParams(nextParams, { replace: true });
    await loadRecommendationHistory(values.user_id);
  };

  return (
    <PagePlaceholder
      title="推荐搜索与推荐历史"
      description="本页只接入 recommendation 创建、候选选中、建卡，以及当前轮最小联调验证所需的 candidate-search / history。"
      extra={
        <Space wrap>
          <Tag color="processing">GET /api/v1/recommendations/candidate-search/</Tag>
          <Tag color="processing">POST /api/v1/recommendations/</Tag>
          <Tag color="processing">POST /api/v1/recommendations/candidates/{'{id}'}/select/</Tag>
          <Tag color="processing">POST /api/v1/match-cards/</Tag>
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

        {createdMatchCard ? (
          <Card title="最新建卡结果">
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
              <Space wrap>
                <Tag color="success">match_card #{createdMatchCard.id}</Tag>
                <Tag>{createdMatchCard.stage_display ?? createdMatchCard.stage}</Tag>
                <Typography.Text>
                  男方：{createdMatchCard.male_user_name ?? createdMatchCard.male_user_id}
                </Typography.Text>
                <Typography.Text>
                  女方：{createdMatchCard.female_user_name ?? createdMatchCard.female_user_id}
                </Typography.Text>
              </Space>
              <Typography.Text type="secondary">
                下一次提醒：{formatDateTime(createdMatchCard.next_remind_at)}
              </Typography.Text>
              <Link to={`/match-cards/${createdMatchCard.id}`}>查看配对卡详情</Link>
            </Space>
          </Card>
        ) : null}

        <Card title="candidate-search">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Form layout="inline" form={candidateForm}>
              <Form.Item
                label="目标用户ID（系统会返回其可推荐异性候选，不包含本人）"
                name="user_id"
                rules={[{ required: true, message: "请输入 user_id" }]}
              >
                <InputNumber min={1} precision={0} placeholder="如 1" />
              </Form.Item>
              <Form.Item label="关键词" name="search">
                <Input placeholder="姓名 / 手机 / 微信，可留空" allowClear style={{ width: 220 }} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" loading={candidateLoading} onClick={() => void handleCandidateSubmit()}>
                  查询候选
                </Button>
              </Form.Item>
              <Form.Item>
                <Button
                  loading={createBatchLoading}
                  onClick={() => void handleCreateBatch()}
                  disabled={selectedCandidateUserIds.length === 0}
                >
                  创建 recommendation
                </Button>
              </Form.Item>
            </Form>

            <Typography.Text type="secondary">
              已勾选候选数：{selectedCandidateUserIds.length}
            </Typography.Text>

            {candidateError ? (
              <Alert type="error" showIcon message="候选搜索失败" description={candidateError} />
            ) : null}

            <Table<CandidateSearchItem>
              rowKey="id"
              loading={candidateLoading}
              pagination={false}
              dataSource={candidateResult?.results ?? []}
              rowSelection={{
                selectedRowKeys: selectedCandidateUserIds,
                onChange: (keys) => setSelectedCandidateUserIds(keys.map((key) => Number(key)))
              }}
              locale={{
                emptyText: candidateResult
                  ? "当前没有候选搜索结果"
                  : "请输入 user_id 后执行候选搜索"
              }}
              columns={[
                {
                  title: "候选ID",
                  dataIndex: "id",
                  width: 100
                },
                {
                  title: "姓名",
                  dataIndex: "name",
                  render: (_, record) => <Link to={`/users/${record.id}`}>{record.name}</Link>
                },
                {
                  title: "城市",
                  dataIndex: "city"
                },
                {
                  title: "年龄",
                  dataIndex: "age",
                  width: 80
                },
                {
                  title: "会员等级",
                  dataIndex: "payment_level_name",
                  render: (value?: string | null) => value || "-"
                },
                {
                  title: "状态",
                  dataIndex: "pool_status_display",
                  render: (value?: string | null) => value || "-"
                },
                {
                  title: "资料完整",
                  dataIndex: "is_profile_complete",
                  width: 100,
                  render: (value: boolean) => (value ? "是" : "否")
                },
                {
                  title: "重复推荐提示",
                  dataIndex: "duplicate_warning",
                  render: (value?: CandidateSearchItem["duplicate_warning"]) => {
                    if (!value) {
                      return "-";
                    }
                    return (
                      <Space direction="vertical" size={4}>
                        <Tag color={value.level === "danger" ? "error" : "warning"}>{value.level}</Tag>
                        <Typography.Text>{value.message}</Typography.Text>
                      </Space>
                    );
                  }
                }
              ]}
            />
          </Space>
        </Card>

        <Card title="recommendation history">
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Form layout="inline" form={historyForm}>
              <Form.Item
                label="用户ID"
                name="user_id"
                rules={[{ required: true, message: "请输入 user_id" }]}
              >
                <InputNumber min={1} precision={0} placeholder="如 1" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" loading={historyLoading} onClick={() => void handleHistorySubmit()}>
                  查询历史
                </Button>
              </Form.Item>
            </Form>

            {historyError ? (
              <Alert type="error" showIcon message="推荐历史加载失败" description={historyError} />
            ) : null}

            {historyResult && historyResult.length === 0 ? (
              <Empty description="当前用户没有推荐历史数据" />
            ) : (
              <List
                loading={historyLoading}
                locale={{ emptyText: "请输入 user_id 后执行历史查询" }}
                dataSource={historyResult ?? []}
                renderItem={(item) => (
                  <List.Item key={item.id}>
                    <Card style={{ width: "100%" }}>
                      <Space direction="vertical" size={8} style={{ width: "100%" }}>
                        <Space wrap>
                          <Tag color="processing">batch #{item.batch_no}</Tag>
                          <Tag>{item.status}</Tag>
                          <Typography.Text>目标用户：{item.user_name}</Typography.Text>
                          <Typography.Text>发起红娘：{item.staff_name}</Typography.Text>
                        </Space>
                        <Typography.Text type="secondary">
                          创建时间：{formatDateTime(item.created_at)}
                        </Typography.Text>
                        <Typography.Text>候选数：{item.candidate_count}</Typography.Text>
                        <List
                          size="small"
                          dataSource={item.candidates}
                          renderItem={(candidate) => (
                            <List.Item
                              actions={[
                                candidate.is_selected ? (
                                  <Tag color="success">已选中</Tag>
                                ) : (
                                  <Button
                                    type="link"
                                    loading={selectingCandidateId === candidate.id}
                                    disabled={item.status !== "open"}
                                    onClick={() => void handleSelectCandidate(item, candidate)}
                                  >
                                    选中
                                  </Button>
                                ),
                                <Button
                                  type="link"
                                  loading={creatingMatchCardCandidateId === candidate.id}
                                  disabled={!candidate.is_selected}
                                  onClick={() => void handleCreateMatchCard(item, candidate)}
                                >
                                  建卡
                                </Button>
                              ]}
                            >
                              <Space wrap>
                                <Typography.Text>{candidate.candidate_user_name}</Typography.Text>
                                <Tag>candidate #{candidate.id}</Tag>
                                <Tag>user #{candidate.candidate_user_id}</Tag>
                                {candidate.is_selected ? <Tag color="success">selected</Tag> : null}
                              </Space>
                            </List.Item>
                          )}
                        />
                      </Space>
                    </Card>
                  </List.Item>
                )}
              />
            )}
          </Space>
        </Card>
      </Space>
    </PagePlaceholder>
  );
}
