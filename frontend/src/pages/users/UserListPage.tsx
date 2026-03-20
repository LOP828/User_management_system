import { Alert, Button, Card, Segmented, Space, Table, Tag, Typography } from "antd";
import { Link, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { getUsers, type UserListQuery, type UserOrdering } from "../../api/users";
import { PagePlaceholder } from "../../components/PagePlaceholder";
import type { PaginatedResponse, UserListItem } from "../../types/user";
import { formatDateTime } from "../../utils/format";

export function UserListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialOrdering = searchParams.get("ordering") === "priority_score" ? "priority_score" : "-priority_score";
  const [ordering, setOrdering] = useState<UserOrdering>(initialOrdering);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PaginatedResponse<UserListItem> | null>(null);

  useEffect(() => {
    const nextOrdering = searchParams.get("ordering") === "priority_score" ? "priority_score" : "-priority_score";
    if (nextOrdering !== ordering) {
      setOrdering(nextOrdering);
      setPage(1);
    }
  }, [ordering, searchParams]);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const query: UserListQuery = {
          page,
          page_size: pageSize,
          ordering
        };
        const response = await getUsers(query);
        if (!active) {
          return;
        }
        setResult(response);
      } catch (err) {
        if (!active) {
          return;
        }
        const message =
          err instanceof ApiError
            ? `${err.message}（HTTP ${err.status}）`
            : "用户列表加载失败";
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
  }, [ordering, page, pageSize]);

  return (
    <PagePlaceholder
      title="用户列表"
      description="当前页已接通真实用户列表接口，支持基础分页和 priority_score 排序。"
      extra={
        <Space wrap>
          <Tag color="processing">接口：GET /api/v1/users/</Tag>
          <Tag color="processing">排序：ordering=priority_score / -priority_score</Tag>
        </Space>
      }
    >
      <Card>
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Space style={{ justifyContent: "space-between", width: "100%" }}>
            <Typography.Text strong>priority_score 排序</Typography.Text>
            <Segmented<UserOrdering>
              value={ordering}
              onChange={(value) => {
                setOrdering(value);
                setPage(1);
                const nextParams = new URLSearchParams(searchParams);
                nextParams.set("ordering", value);
                setSearchParams(nextParams, { replace: true });
              }}
              options={[
                { label: "优先级降序", value: "-priority_score" },
                { label: "优先级升序", value: "priority_score" }
              ]}
            />
          </Space>
          {error ? (
            <Alert type="error" showIcon message="用户列表加载失败" description={error} />
          ) : null}
          <Table<UserListItem>
            rowKey="id"
            loading={loading}
            pagination={{
              current: result?.page ?? page,
              pageSize: result?.page_size ?? pageSize,
              total: result?.count ?? 0,
              showSizeChanger: true,
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPage);
                setPageSize(nextPageSize);
              }
            }}
            dataSource={result?.results ?? []}
            locale={{ emptyText: error ? "加载失败" : "当前没有可见用户" }}
            columns={[
              {
                title: "用户ID",
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
                dataIndex: "city",
                render: (value: string | undefined) => value || "-"
              },
              {
                title: "年龄",
                dataIndex: "age",
                width: 90,
                render: (value: number | undefined) => value ?? "-"
              },
              {
                title: "当前状态",
                dataIndex: "pool_status_display"
              },
              {
                title: "负责人",
                dataIndex: "owner_name",
                render: (value: string | undefined) => value || "-"
              },
              {
                title: "priority_score",
                dataIndex: "priority_score",
                width: 140,
                render: (value: number | undefined) => value ?? "-"
              },
              {
                title: "最近动作",
                dataIndex: "last_action_at",
                width: 180,
                render: (value: string | null | undefined) => formatDateTime(value)
              },
              {
                title: "操作",
                key: "actions",
                width: 120,
                render: (_, record) => (
                  <Button type="link">
                    <Link to={`/users/${record.id}`}>查看详情</Link>
                  </Button>
                )
              }
            ]}
          />
        </Space>
      </Card>
    </PagePlaceholder>
  );
}
