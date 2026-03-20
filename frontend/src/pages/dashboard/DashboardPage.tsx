import { Alert, Card, Col, Descriptions, List, Row, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getAdminDashboard, getMatchmakerDashboard } from "../../api/dashboard";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import { authStore } from "../../store/auth";
import type { AdminDashboardResponse, MatchmakerDashboardResponse } from "../../types/dashboard";
import { formatDateTime } from "../../utils/format";

type DashboardMode = "admin" | "matchmaker";

interface DashboardState {
  mode: DashboardMode;
  data: AdminDashboardResponse | MatchmakerDashboardResponse;
}

function getErrorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? `${err.message}（HTTP ${err.status}）` : fallback;
}

function isApi403(err: unknown) {
  return err instanceof ApiError && err.status === 403;
}

function StatCard({ title, value }: { title: string; value: number }) {
  return (
    <Card size="small">
      <Typography.Text type="secondary">{title}</Typography.Text>
      <Typography.Title level={3} style={{ margin: "8px 0 0" }}>
        {value}
      </Typography.Title>
    </Card>
  );
}

export function DashboardPage() {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardState | null>(null);

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      authStore.setToken(token);
    }

    async function loadDashboard() {
      setLoading(true);
      try {
        const adminData = await getAdminDashboard();
        setDashboard({ mode: "admin", data: adminData });
        setError(null);
      } catch (err) {
        if (!isApi403(err)) {
          setDashboard(null);
          setError(getErrorMessage(err, "dashboard 加载失败"));
          setLoading(false);
          return;
        }

        try {
          const matchmakerData = await getMatchmakerDashboard();
          setDashboard({ mode: "matchmaker", data: matchmakerData });
          setError(null);
        } catch (matchmakerErr) {
          setDashboard(null);
          setError(getErrorMessage(matchmakerErr, "dashboard 加载失败"));
        }
      } finally {
        setLoading(false);
      }
    }

    void loadDashboard();
  }, [searchParams]);

  const mode = dashboard?.mode;
  const data = dashboard?.data;

  return (
    <PagePlaceholder
      title="Dashboard"
      description="当前页最小接入 dashboard 统计与 items 明细，优先使用管理员口径，403 时回退红娘口径。"
      extra={
        <Space wrap>
          <Tag color="processing">GET /api/v1/dashboard/admin/</Tag>
          <Tag color="processing">GET /api/v1/dashboard/matchmaker/</Tag>
          {mode ? <Tag color="blue">当前口径：{mode}</Tag> : null}
        </Space>
      }
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {error ? <Alert type="error" showIcon message="dashboard 加载失败" description={error} /> : null}

        <Spin spinning={loading}>
          {!data ? (
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              当前没有可展示的 dashboard 数据。
            </Typography.Paragraph>
          ) : (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Card title="基础统计">
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                  <Descriptions bordered size="small" column={3}>
                    <Descriptions.Item label="新用户待处理">{data.user_pool.new_pending}</Descriptions.Item>
                    <Descriptions.Item label="已沟通待推荐">{data.user_pool.communicated_pending_recommend}</Descriptions.Item>
                    <Descriptions.Item label="已推荐待选择">{data.user_pool.recommended_pending_select}</Descriptions.Item>
                    <Descriptions.Item label="已选择待见面">{data.user_pool.selected_pending_meet}</Descriptions.Item>
                    <Descriptions.Item label="见面不继续">{data.user_pool.met_not_continue}</Descriptions.Item>
                    <Descriptions.Item label="已暂停">{data.user_pool.paused}</Descriptions.Item>
                  </Descriptions>

                  <Row gutter={[16, 16]}>
                    <Col xs={24} sm={12} md={8}>
                      <StatCard title="活跃配对卡" value={data.match_cards.active} />
                    </Col>
                    <Col xs={24} sm={12} md={8}>
                      <StatCard title="成功待审核" value={data.match_cards.success_pending_review} />
                    </Col>
                    <Col xs={24} sm={12} md={8}>
                      <StatCard title="待处理提醒" value={data.reminders.pending} />
                    </Col>
                    {mode === "admin" ? (
                      <>
                        <Col xs={24} sm={12} md={8}>
                          <StatCard title="成功案例" value={data.match_cards.success} />
                        </Col>
                        <Col xs={24} sm={12} md={8}>
                          <StatCard title="高风险配对" value={data.match_cards.high_risk} />
                        </Col>
                        <Col xs={24} sm={12} md={8}>
                          <StatCard title="待审批转移" value={data.pending_approvals.transfer_count} />
                        </Col>
                        <Col xs={24} sm={12} md={8}>
                          <StatCard title="待审批成功" value={data.pending_approvals.success_count} />
                        </Col>
                      </>
                    ) : (
                      <Col xs={24} sm={12} md={8}>
                        <StatCard title="今日处理 followup" value={data.today_processed.count} />
                      </Col>
                    )}
                  </Row>
                </Space>
              </Card>

              {mode === "admin" ? (
                <Card title={`超时明细（${data.overdue_summary.total_overdue_users}）`}>
                  <List
                    locale={{ emptyText: "当前没有 dashboard items" }}
                    dataSource={data.overdue_summary.by_staff}
                    renderItem={(item) => (
                      <List.Item key={item.staff_id}>
                        <List.Item.Meta
                          title={
                            <Space wrap>
                              <Tag>staff #{item.staff_id}</Tag>
                              <Typography.Text>{item.staff_name}</Typography.Text>
                            </Space>
                          }
                          description={`超时数量：${item.overdue_count}`}
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              ) : (
                <>
                  <Card title={`未配对超时（${data.unmatched_overdue.count}）`}>
                    <List
                      locale={{ emptyText: "当前没有 dashboard items" }}
                      dataSource={data.unmatched_overdue.items}
                      renderItem={(item) => (
                        <List.Item key={item.user_id}>
                          <List.Item.Meta
                            title={
                              <Space wrap>
                                <Tag>user #{item.user_id}</Tag>
                                <Typography.Text>{item.user_name}</Typography.Text>
                                <Tag>{item.pool_status_display ?? "-"}</Tag>
                              </Space>
                            }
                            description={`超时天数：${item.overdue_days}；优先级：${item.priority_score ?? "-"}`}
                          />
                        </List.Item>
                      )}
                    />
                  </Card>

                  <Card title={`待回访配对（${data.matched_pending_visit.count}）`}>
                    <List
                      locale={{ emptyText: "当前没有 dashboard items" }}
                      dataSource={data.matched_pending_visit.items}
                      renderItem={(item) => (
                        <List.Item key={item.match_card_id}>
                          <List.Item.Meta
                            title={
                              <Space wrap>
                                <Tag>match_card #{item.match_card_id}</Tag>
                                <Typography.Text>{item.male_name ?? "-"}</Typography.Text>
                                <Typography.Text>vs</Typography.Text>
                                <Typography.Text>{item.female_name ?? "-"}</Typography.Text>
                              </Space>
                            }
                            description={
                              <Space direction="vertical" size={4}>
                                <Typography.Text type="secondary">
                                  阶段：{item.stage_display ?? "-"} / 风险：{item.risk_level_display ?? "-"}
                                </Typography.Text>
                                <Typography.Text type="secondary">
                                  最后回访：{formatDateTime(item.last_visit_at)} / 下次提醒：{formatDateTime(item.next_remind_at)}
                                </Typography.Text>
                                <Link to={`/match-cards/${item.match_card_id}`}>查看配对卡</Link>
                              </Space>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  </Card>

                  <Card title={`最近新增（${data.recent_new.count}）`}>
                    <List
                      locale={{ emptyText: "当前没有 dashboard items" }}
                      dataSource={data.recent_new.items}
                      renderItem={(item) => (
                        <List.Item key={item.user_id}>
                          <List.Item.Meta
                            title={
                              <Space wrap>
                                <Tag>user #{item.user_id}</Tag>
                                <Typography.Text>{item.user_name}</Typography.Text>
                              </Space>
                            }
                            description={
                              <Space direction="vertical" size={4}>
                                <Typography.Text type="secondary">
                                  创建时间：{formatDateTime(item.created_at)}
                                </Typography.Text>
                                <Link to={`/users/${item.user_id}`}>查看用户</Link>
                              </Space>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  </Card>
                </>
              )}
            </Space>
          )}
        </Spin>
      </Space>
    </PagePlaceholder>
  );
}
