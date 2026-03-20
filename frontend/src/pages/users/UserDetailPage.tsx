import { Alert, Card, Descriptions, List, Space, Spin, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { getUserDetail } from "../../api/users";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import type { UserDetail } from "../../types/user";
import { formatDateTime } from "../../utils/format";

export function UserDetailPage() {
  const params = useParams();
  const userId = params.id ?? "-";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<UserDetail | null>(null);

  useEffect(() => {
    if (!params.id) {
      return;
    }

    let active = true;

    async function load() {
      const id = params.id;
      if (!id) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await getUserDetail(id);
        if (!active) {
          return;
        }
        setDetail(response);
      } catch (err) {
        if (!active) {
          return;
        }
        const message =
          err instanceof ApiError
            ? `${err.message}（HTTP ${err.status}）`
            : "用户详情加载失败";
        setError(message);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [params.id]);

  return (
    <PagePlaceholder
      title={`用户详情 #${userId}`}
      description="当前页已接通真实用户详情接口，包含 stats、最近跟进和 active_match_card 摘要。"
      extra={
        <Space wrap>
          <Tag color="processing">接口：GET /api/v1/users/{'{id}'}/</Tag>
          <Tag color="processing">字段：recent_follow_ups / active_match_card / stats</Tag>
        </Space>
      }
    >
      {error ? (
        <Alert
          type="error"
          showIcon
          message="用户详情加载失败"
          description={error}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Spin spinning={loading}>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card title="基础详情">
            <Descriptions column={2} bordered>
              <Descriptions.Item label="姓名">{detail?.name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="城市">{detail?.city ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="年龄">{detail?.age ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="当前状态">{detail?.pool_status_display ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="负责人">{detail?.owner_name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="会员等级">{detail?.payment_level_name ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="手机号">{detail?.phone ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="微信">{detail?.wechat ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="最近动作">{formatDateTime(detail?.last_action_at)}</Descriptions.Item>
              <Descriptions.Item label="最近未配对活跃时间">{formatDateTime(detail?.last_unmatched_active_at)}</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="stats">
            <Descriptions column={3} bordered>
              <Descriptions.Item label="推荐次数">{detail?.stats?.total_recommendations ?? 0}</Descriptions.Item>
              <Descriptions.Item label="见面次数">{detail?.stats?.total_meetings ?? 0}</Descriptions.Item>
              <Descriptions.Item label="配对卡数">{detail?.stats?.total_match_cards ?? 0}</Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="active_match_card">
            {detail?.active_match_card ? (
              <Descriptions column={2} bordered>
                <Descriptions.Item label="配对卡ID">{detail.active_match_card.id}</Descriptions.Item>
                <Descriptions.Item label="详情入口">
                  <Link to={`/match-cards/${detail.active_match_card.id}`}>查看配对卡详情</Link>
                </Descriptions.Item>
                <Descriptions.Item label="阶段">
                  {detail.active_match_card.stage_display ?? detail.active_match_card.stage ?? "-"}
                </Descriptions.Item>
                <Descriptions.Item label="男方">{detail.active_match_card.male_user_name ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="女方">{detail.active_match_card.female_user_name ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="主负责红娘">{detail.active_match_card.primary_staff_name ?? "-"}</Descriptions.Item>
                <Descriptions.Item label="下一次提醒">
                  {formatDateTime(detail.active_match_card.next_remind_at)}
                </Descriptions.Item>
              </Descriptions>
            ) : (
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                当前没有进行中的配对卡。
              </Typography.Paragraph>
            )}
          </Card>

          <Card title="recent_follow_ups">
            <List
              locale={{ emptyText: "当前没有最近跟进记录" }}
              dataSource={detail?.recent_follow_ups ?? []}
              renderItem={(item) => (
                <List.Item key={item.id}>
                  <List.Item.Meta
                    title={
                      <Space wrap>
                        <Tag>{item.scene ?? "-"}</Tag>
                        <Typography.Text>{item.staff_name ?? "-"}</Typography.Text>
                        <Typography.Text type="secondary">
                          {formatDateTime(item.created_at)}
                        </Typography.Text>
                      </Space>
                    }
                    description={item.content ?? "-"}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Space>
      </Spin>
    </PagePlaceholder>
  );
}
