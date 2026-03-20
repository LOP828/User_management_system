import { Layout, Menu, Space, Tag, Typography } from "antd";
import { AppstoreOutlined, BellOutlined, CheckCircleOutlined, SearchOutlined, SwapOutlined, TeamOutlined, UserOutlined } from "@ant-design/icons";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useLayoutEffect } from "react";

import { TokenAccessBar } from "../components/TokenAccessBar";
import { authStore } from "../store/auth";

const { Header, Sider, Content } = Layout;

const menuItems = [
  {
    key: "/dashboard",
    icon: <AppstoreOutlined />,
    label: <Link to="/dashboard">Dashboard</Link>
  },
  {
    key: "/users",
    icon: <TeamOutlined />,
    label: <Link to="/users">用户列表</Link>
  },
  {
    key: "/recommendations",
    icon: <SearchOutlined />,
    label: <Link to="/recommendations">推荐搜索</Link>
  },
  {
    key: "/reminders",
    icon: <BellOutlined />,
    label: <Link to="/reminders">提醒列表</Link>
  },
  {
    key: "/success",
    icon: <CheckCircleOutlined />,
    label: <Link to="/success">Success审批</Link>
  },
  {
    key: "/transfers",
    icon: <SwapOutlined />,
    label: <Link to="/transfers">Transfer审批</Link>
  }
];

export function AppLayout() {
  const location = useLocation();

  useLayoutEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get("token");
    if (!token) {
      return;
    }
    authStore.setToken(token);
  }, [location.search]);

  return (
    <Layout className="app-shell">
      <Sider width={232} theme="light" className="app-sider">
        <div className="brand-block">
          <Typography.Title level={4} className="brand-title">
            AI红娘后台
          </Typography.Title>
          <Typography.Paragraph className="brand-subtitle">
            PC 管理后台骨架
          </Typography.Paragraph>
        </div>
        <Menu mode="inline" selectedKeys={[location.pathname]} items={menuItems} />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space size="middle">
            <UserOutlined />
            <Typography.Text>当前阶段：前端骨架初始化</Typography.Text>
            <Tag color="processing">React + Ant Design</Tag>
          </Space>
        </Header>
        <Content className="app-content">
          <div style={{ marginBottom: 16 }}>
            <TokenAccessBar />
          </div>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
