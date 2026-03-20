import { Alert, Card, Space, Typography } from "antd";
import type { ReactNode } from "react";

interface PagePlaceholderProps {
  title: string;
  description: string;
  extra?: ReactNode;
  children?: ReactNode;
}

export function PagePlaceholder(props: PagePlaceholderProps) {
  const { title, description, extra, children } = props;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space direction="vertical" size={8}>
          <Typography.Title level={3} style={{ margin: 0 }}>
            {title}
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
            {description}
          </Typography.Paragraph>
          {extra}
        </Space>
      </Card>
      <Alert
        type="info"
        showIcon
        message="当前为前端骨架阶段"
        description="页面已预留路由、布局和 API 封装。下一步可直接接入用户列表、用户详情和 priority_score 排序。"
      />
      {children}
    </Space>
  );
}
