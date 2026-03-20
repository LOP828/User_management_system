import { Button, Card, Input, Space, Tag, Typography, message } from "antd";
import { useState } from "react";

import { authStore } from "../store/auth";

export function TokenAccessBar() {
  const [draft, setDraft] = useState(authStore.getToken() || "");
  const hasToken = Boolean(authStore.getToken());

  const handleSave = () => {
    if (!draft.trim()) {
      message.warning("请输入 token 后再保存");
      return;
    }
    authStore.setToken(draft.trim());
    message.success("token 已保存到本地");
  };

  const handleClear = () => {
    authStore.clearToken();
    setDraft("");
    message.success("token 已清空");
  };

  return (
    <Card size="small">
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Space wrap>
          <Typography.Text strong>访问令牌</Typography.Text>
          <Tag color={hasToken ? "success" : "default"}>
            {hasToken ? "已设置" : "未设置"}
          </Tag>
          <Typography.Text type="secondary">
            当前只预留 token 注入，不做完整登录流。
          </Typography.Text>
        </Space>
        <Space.Compact style={{ width: "100%" }}>
          <Input.Password
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="粘贴 Bearer token 的原始值"
          />
          <Button type="primary" onClick={handleSave}>
            保存
          </Button>
          <Button onClick={handleClear}>清空</Button>
        </Space.Compact>
      </Space>
    </Card>
  );
}
