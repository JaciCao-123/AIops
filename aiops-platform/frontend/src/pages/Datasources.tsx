import { useEffect, useState } from 'react';
import {
  Row, Col, Card, Statistic, Table, Tag, Button, Space, Modal,
  Input, message, Spin, Typography, Alert, Descriptions, Divider
} from 'antd';
import {
  ApiOutlined, LinkOutlined, PlayCircleOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined
} from '@ant-design/icons';
import { mcpApi } from '../services/api';
import type { McpStatus, McpToolInfo, McpCallResult } from '../types';

const { TextArea } = Input;
const { Title, Paragraph, Text } = Typography;

const Datasources = () => {
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [tools, setTools] = useState<McpToolInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState<string | null>(null);

  // 试运行弹窗
  const [modalVisible, setModalVisible] = useState(false);
  const [currentTool, setCurrentTool] = useState<McpToolInfo | null>(null);
  const [toolParams, setToolParams] = useState<Record<string, string>>({});
  const [callResult, setCallResult] = useState<McpCallResult | null>(null);
  const [callLoading, setCallLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statusData, toolsData] = await Promise.all([
        mcpApi.getStatus(),
        mcpApi.getTools(),
      ]);
      setStatus(statusData);
      setTools(toolsData.tools);
    } catch (error) {
      message.error('获取 MCP 数据源状态失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // ── 试运行 ──

  const handleRunTool = (tool: McpToolInfo) => {
    setCurrentTool(tool);
    setToolParams({});
    setCallResult(null);
    setModalVisible(true);
  };

  const handleExecute = async () => {
    if (!currentTool) return;
    setCallLoading(true);
    setExecuting(currentTool.name);
    try {
      const result = await mcpApi.callTool(currentTool.name, toolParams);
      setCallResult(result);
    } catch (error) {
      setCallResult({ success: false, error: '调用失败' });
    } finally {
      setCallLoading(false);
      setExecuting(null);
    }
  };

  // ── 工具列表列 ──

  const toolColumns = [
    {
      title: '工具名',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string) => <Text code>{name}</Text>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '必填参数',
      key: 'params',
      width: 200,
      render: (_: unknown, record: McpToolInfo) => {
        const required = record.inputSchema?.required || [];
        return (
          <Space size={4} wrap>
            {required.length > 0
              ? required.map(p => <Tag key={p} color="blue">{p}</Tag>)
              : <Text type="secondary">无</Text>
            }
          </Space>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: McpToolInfo) => (
        <Button
          type="link"
          icon={<PlayCircleOutlined />}
          onClick={() => handleRunTool(record)}
          loading={executing === record.name}
        >
          试运行
        </Button>
      ),
    },
  ];

  if (loading && !status) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />;
  }

  return (
    <div>
      {/* ── 标题 ── */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>MCP 数据源</Title>
        <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>刷新</Button>
      </div>

      {/* ── 状态概览卡片 ── */}
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic
              title="MCP Server"
              value={status?.status === 'running' ? '运行中' : '已停止'}
              valueStyle={{ color: status?.status === 'running' ? '#52c41a' : '#ff4d4f' }}
              prefix={status?.status === 'running' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Grafana 连接"
              value={status?.grafana_connected ? '已连接' : '断开'}
              valueStyle={{ color: status?.grafana_connected ? '#52c41a' : '#ff4d4f' }}
              prefix={status?.grafana_connected ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="可用工具"
              value={status?.tool_count || 0}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="可用资源"
              value={status?.resource_count || 0}
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* ── 服务器信息 ── */}
      {status && (
        <Card style={{ marginTop: 16 }}>
          <Descriptions size="small" column={3}>
            <Descriptions.Item label="Server">{status.server}</Descriptions.Item>
            <Descriptions.Item label="Version">{status.version}</Descriptions.Item>
            <Descriptions.Item label="Grafana URL">
              <a href={status.grafana_url} target="_blank" rel="noopener noreferrer">
                {status.grafana_url} <LinkOutlined />
              </a>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* ── 工具列表 ── */}
      <Card title="工具列表" style={{ marginTop: 16 }}>
        <Table
          columns={toolColumns}
          dataSource={tools}
          rowKey="name"
          pagination={false}
          size="small"
        />
      </Card>

      {/* ── Grafana 快捷链接 ── */}
      {status?.grafana_url && (
        <Card title="Grafana 快捷链接" style={{ marginTop: 16 }}>
          <Space>
            <Button
              type="primary"
              icon={<LinkOutlined />}
              href={`${status.grafana_url}/explore`}
              target="_blank"
            >
              打开 Grafana Explore
            </Button>
            <Button
              icon={<LinkOutlined />}
              href={`${status.grafana_url}/dashboards`}
              target="_blank"
            >
              仪表盘列表
            </Button>
            <Button
              icon={<LinkOutlined />}
              href={`${status.grafana_url}/alerting/list`}
              target="_blank"
            >
              告警中心
            </Button>
          </Space>
        </Card>
      )}

      {/* ── 工具未就绪提示 ── */}
      {!status?.grafana_connected && (
        <Alert
          style={{ marginTop: 16 }}
          message="Grafana 连接异常"
          description="MCP Server 无法连接到 Grafana，请检查 GRAFANA_URL 和 GRAFANA_API_KEY 配置是否正确。"
          type="warning"
          showIcon
        />
      )}

      {/* ── 试运行弹窗 ── */}
      <Modal
        title={`试运行: ${currentTool?.name || ''}`}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        width={800}
        footer={
          <Space>
            <Button onClick={() => setModalVisible(false)}>关闭</Button>
            <Button type="primary" onClick={handleExecute} loading={callLoading}>
              执行
            </Button>
          </Space>
        }
      >
        {currentTool && (
          <>
            <Paragraph type="secondary">{currentTool.description}</Paragraph>
            <Divider orientation="left" style={{ fontSize: 12 }}>参数</Divider>
            {Object.entries(currentTool.inputSchema?.properties || {}).map(([key, prop]) => (
              <div key={key} style={{ marginBottom: 12 }}>
                <Text strong>
                  {key}
                  {(currentTool.inputSchema?.required || []).includes(key) && (
                    <Text type="danger"> *</Text>
                  )}
                </Text>
                <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                  {prop.description}
                </Text>
                <TextArea
                  style={{ marginTop: 4 }}
                  rows={2}
                  placeholder={`输入 ${key} 的值`}
                  value={toolParams[key] || ''}
                  onChange={(e) => setToolParams({ ...toolParams, [key]: e.target.value })}
                />
              </div>
            ))}

            <Divider orientation="left" style={{ fontSize: 12 }}>结果</Divider>
            {callLoading && <Spin />}
            {callResult && !callLoading && (
              callResult.success ? (
                <div>
                  {callResult.result_count !== undefined && (
                    <Tag color="green" style={{ marginBottom: 8 }}>
                      返回 {callResult.result_count} 条结果
                    </Tag>
                  )}
                  <pre style={{
                    maxHeight: 300,
                    overflow: 'auto',
                    background: '#f5f5f5',
                    padding: 12,
                    borderRadius: 4,
                    fontSize: 12,
                  }}>
                    {JSON.stringify(callResult, null, 2)}
                  </pre>
                </div>
              ) : (
                <Alert message="调用失败" description={callResult.error} type="error" showIcon />
              )
            )}
          </>
        )}
      </Modal>
    </div>
  );
};

export default Datasources;
