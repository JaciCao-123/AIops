import { useEffect, useState } from 'react';
import { Card, Table, Tag, Input, Select, Space, Button, message, Row, Col, Statistic, Modal, Descriptions, Timeline, Badge, Tabs } from 'antd';
import { SearchOutlined, ReloadOutlined, ApiOutlined, WarningOutlined, ClockCircleOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';

import { traceApi } from '../services/api';
import type { TraceInfo, TraceDetail, ServiceDependency, Span } from '../types';

const { Search } = Input;

const Tracing = () => {
  const [loading, setLoading] = useState(false);
  const [traces, setTraces] = useState<TraceInfo[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [dependency, setDependency] = useState<ServiceDependency | null>(null);
  const [serviceName, setServiceName] = useState('');
  const [lookback, setLookback] = useState('1h');
  const [errorOnly, setErrorOnly] = useState(false);
  const [slowOnly, setSlowOnly] = useState(false);
  const [activeTab, setActiveTab] = useState('traces');

  const fetchTraces = async () => {
    setLoading(true);
    try {
      const result = await traceApi.searchTraces({
        service_name: serviceName || undefined,
        error_only: errorOnly,
        slow_only: slowOnly,
        lookback,
        limit: 50,
      });
      setTraces(result.traces);
    } catch (error) {
      message.error('获取链路数据失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchDependency = async () => {
    try {
      const result = await traceApi.getServiceDependency(lookback);
      setDependency(result);
    } catch (error) {
      message.error('获取服务依赖失败');
    }
  };

  const fetchTraceDetail = async (traceId: string) => {
    try {
      const result = await traceApi.getTraceById(traceId);
      setSelectedTrace(result);
    } catch (error) {
      message.error('获取链路详情失败');
    }
  };

  useEffect(() => {
    if (activeTab === 'traces') {
      fetchTraces();
    } else {
      fetchDependency();
    }
  }, [lookback, errorOnly, slowOnly, activeTab]);

  const getDurationColor = (duration: number) => {
    if (duration > 3000) return 'red';
    if (duration > 1000) return 'orange';
    return 'green';
  };

  const traceColumns = [
    {
      title: 'Trace ID',
      dataIndex: 'traceID',
      key: 'traceID',
      width: 180,
      render: (id: string) => (
        <a onClick={() => fetchTraceDetail(id)} style={{ fontFamily: 'monospace' }}>
          {id.substring(0, 16)}...
        </a>
      ),
    },
    {
      title: '服务',
      dataIndex: 'rootServiceName',
      key: 'rootServiceName',
      width: 150,
    },
    {
      title: '操作',
      dataIndex: 'rootTraceName',
      key: 'rootTraceName',
      ellipsis: true,
    },
    {
      title: '耗时',
      dataIndex: 'durationMs',
      key: 'durationMs',
      width: 100,
      render: (duration: number) => (
        <Tag color={getDurationColor(duration)}>
          {duration > 1000 ? `${(duration / 1000).toFixed(2)}s` : `${duration}ms`}
        </Tag>
      ),
    },
    {
      title: 'Span 数',
      dataIndex: 'spanCount',
      key: 'spanCount',
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'hasError',
      key: 'hasError',
      width: 80,
      render: (hasError: boolean) => (
        hasError ? <Tag color="red">错误</Tag> : <Tag color="green">正常</Tag>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'startTime',
      key: 'startTime',
      width: 180,
      render: (time: string) => dayjs(time).format('YYYY-MM-DD HH:mm:ss'),
    },
  ];

  const getDependencyChartOption = () => {
    if (!dependency) return {};

    const nodes = dependency.nodes.map(n => ({
      name: n.name,
      symbolSize: 30,
      category: 0,
    }));

    const links = dependency.edges.map(e => ({
      source: e.source,
      target: e.target,
      value: e.call_count,
      lineStyle: {
        width: Math.min(e.call_count / 100, 5),
        color: e.error_rate > 5 ? '#ff4d4f' : e.error_rate > 1 ? '#faad14' : '#1890ff',
      },
      label: {
        show: e.error_rate > 0,
        formatter: `${e.error_rate.toFixed(1)}%`,
        color: '#ff4d4f',
      },
    }));

    return {
      title: { text: '服务依赖拓扑', left: 'center' },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            const edge = dependency.edges.find(e => e.source === params.data.source && e.target === params.data.target);
            if (edge) {
              return `${edge.source} → ${edge.target}<br/>
                调用次数: ${edge.call_count}<br/>
                错误率: ${edge.error_rate}%<br/>
                平均延迟: ${edge.avg_latency_ms}ms`;
            }
          }
          return params.name;
        },
      },
      series: [{
        type: 'graph',
        layout: 'force',
        data: nodes,
        links,
        roam: true,
        label: { show: true, position: 'right' },
        force: {
          repulsion: 200,
          edgeLength: 150,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 10 },
        },
      }],
    };
  };

  const renderSpanTree = (spans: Span[]) => {
    const spanMap = new Map<string, Span>();
    const rootSpans: Span[] = [];

    spans.forEach(span => {
      spanMap.set(span.spanID, span);
    });

    spans.forEach(span => {
      if (!span.parentSpanID) {
        rootSpans.push(span);
      }
    });

    const renderSpan = (span: Span, depth: number = 0): JSX.Element => {
      const children = spans.filter(s => s.parentSpanID === span.spanID);
      const durationPercent = selectedTrace ? (span.durationMs / selectedTrace.totalDurationMs * 100) : 0;

      return (
        <div key={span.spanID} style={{ marginLeft: depth * 20 }}>
          <Timeline.Item
            color={span.hasError ? 'red' : 'green'}
            dot={span.hasError ? <WarningOutlined /> : <ClockCircleOutlined />}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Tag color={span.hasError ? 'red' : 'blue'}>{span.serviceName}</Tag>
              <span style={{ fontWeight: 500 }}>{span.operationName}</span>
              <Tag color={getDurationColor(span.durationMs)}>{span.durationMs}ms</Tag>
              <div style={{
                width: `${durationPercent}%`,
                minWidth: 20,
                height: 8,
                backgroundColor: span.hasError ? '#ff4d4f' : '#1890ff',
                borderRadius: 4,
              }} />
            </div>
          </Timeline.Item>
          {children.map(child => renderSpan(child, depth + 1))}
        </div>
      );
    };

    return (
      <Timeline>
        {rootSpans.map(span => renderSpan(span))}
      </Timeline>
    );
  };

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col span={6}>
            <Statistic
              title="总链路数"
              value={traces.length}
              prefix={<ApiOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="错误链路"
              value={traces.filter(t => t.hasError).length}
              valueStyle={{ color: '#cf1322' }}
              prefix={<WarningOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="服务数"
              value={dependency?.total_services || 0}
            />
          </Col>
          <Col span={6} style={{ textAlign: 'right' }}>
            <Space>
              <Select value={lookback} onChange={setLookback} style={{ width: 120 }}>
                <Select.Option value="15m">最近 15 分钟</Select.Option>
                <Select.Option value="1h">最近 1 小时</Select.Option>
                <Select.Option value="6h">最近 6 小时</Select.Option>
                <Select.Option value="24h">最近 24 小时</Select.Option>
              </Select>
              <Button
                type={errorOnly ? 'primary' : 'default'}
                danger={errorOnly}
                onClick={() => setErrorOnly(!errorOnly)}
              >
                仅错误
              </Button>
              <Button
                type={slowOnly ? 'primary' : 'default'}
                onClick={() => setSlowOnly(!slowOnly)}
              >
                仅慢请求
              </Button>
              <Button icon={<ReloadOutlined />} onClick={fetchTraces}>刷新</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'traces', label: '链路列表' },
          { key: 'dependency', label: '服务拓扑' },
        ]}
      />

      {activeTab === 'traces' ? (
        <Card>
          <Search
            placeholder="搜索服务名称"
            allowClear
            enterButton={<SearchOutlined />}
            onSearch={setServiceName}
            style={{ marginBottom: 16 }}
          />
          <Table
            columns={traceColumns}
            dataSource={traces}
            rowKey="traceID"
            loading={loading}
            pagination={{ pageSize: 20 }}
            size="small"
          />
        </Card>
      ) : (
        <Card>
          <ReactECharts option={getDependencyChartOption()} style={{ height: 600 }} />
        </Card>
      )}

      <Modal
        title={`Trace: ${selectedTrace?.traceID?.substring(0, 16)}...`}
        open={!!selectedTrace}
        onCancel={() => setSelectedTrace(null)}
        footer={null}
        width={1000}
      >
        {selectedTrace && (
          <div>
            <Descriptions column={4} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="总耗时">
                <Tag color={getDurationColor(selectedTrace.totalDurationMs)}>
                  {selectedTrace.totalDurationMs}ms
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Span 数">{selectedTrace.spans.length}</Descriptions.Item>
              <Descriptions.Item label="服务数">{selectedTrace.services.length}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Badge status={selectedTrace.hasError ? 'error' : 'success'} text={selectedTrace.hasError ? '有错误' : '正常'} />
              </Descriptions.Item>
            </Descriptions>

            <Tabs
              items={[
                {
                  key: 'tree',
                  label: '调用树',
                  children: renderSpanTree(selectedTrace.spans),
                },
                {
                  key: 'table',
                  label: 'Span 列表',
                  children: (
                    <Table
                      dataSource={selectedTrace.spans}
                      rowKey="spanID"
                      size="small"
                      pagination={false}
                      columns={[
                        { title: '服务', dataIndex: 'serviceName', width: 120 },
                        { title: '操作', dataIndex: 'operationName', ellipsis: true },
                        { title: '耗时', dataIndex: 'durationMs', width: 80, render: (d: number) => <Tag color={getDurationColor(d)}>{d}ms</Tag> },
                        { title: '状态', dataIndex: 'hasError', width: 60, render: (e: boolean) => e ? <Tag color="red">错误</Tag> : <Tag color="green">OK</Tag> },
                      ]}
                    />
                  ),
                },
                {
                  key: 'errors',
                  label: `错误 (${selectedTrace.errorSpans?.length || 0})`,
                  children: (
                    <Table
                      dataSource={selectedTrace.errorSpans || []}
                      rowKey="spanID"
                      size="small"
                      pagination={false}
                      columns={[
                        { title: '服务', dataIndex: 'serviceName', width: 120 },
                        { title: '操作', dataIndex: 'operationName', ellipsis: true },
                        { title: '错误信息', dataIndex: ['tags', 'error'], ellipsis: true },
                      ]}
                    />
                  ),
                },
              ]}
            />
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Tracing;
