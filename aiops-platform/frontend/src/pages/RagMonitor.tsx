import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Row, Col, Card, Statistic, Progress, Table, Tag, Button, Space,
  message, Spin, Typography, Tabs, Alert, Descriptions, Tooltip
} from 'antd';
import {
  ReloadOutlined, LinkOutlined, CheckCircleOutlined,
  WarningOutlined, CloseCircleOutlined, ThunderboltOutlined
} from '@ant-design/icons';
import { mcpApi } from '../services/api';
import type { OverviewSnapshot } from '../types';

const { Title, Text } = Typography;

// ─── 数值格式化工具 ───

/** 兼容 number / [{value}] / null */
const num = (v: unknown): number | null => {
  if (v === null || v === undefined) return null;
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const n = parseFloat(v);
    return isNaN(n) ? null : n;
  }
  if (Array.isArray(v) && v.length > 0) {
    const first = v[0] as Record<string, unknown>;
    return num(first?.value);
  }
  return null;
};

const fmtPct = (v: unknown, digits = 1): string => {
  const n = num(v);
  return n === null ? '-' : `${n.toFixed(digits)}%`;
};

const fmtNum = (v: unknown, digits = 1): string => {
  const n = num(v);
  return n === null ? '-' : n.toFixed(digits);
};

const fmtBytes = (v: unknown): string => {
  const n = num(v);
  if (n === null) return '-';
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)}GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)}MB`;
  return `${(n / 1024).toFixed(1)}KB`;
};

const fmtSpeed = (v: unknown): string => {
  const n = num(v);
  return n === null ? '-' : `${(n / 1024 ** 2).toFixed(2)} MB/s`;
};

const statusColor = (status: string): string =>
  status === 'HEALTHY' ? '#52c41a' : status === 'WARNING' ? '#faad14' : '#ff4d4f';

const StatusIcon = ({ status }: { status: string }) =>
  status === 'HEALTHY' ? <CheckCircleOutlined /> :
  status === 'WARNING' ? <WarningOutlined /> : <CloseCircleOutlined />;

// ─── 列表转换 ───

/** 把 multi-series 指标转成 [{label, value}] */
const toList = (v: unknown): Array<Record<string, unknown>> =>
  Array.isArray(v) ? (v as Array<Record<string, unknown>>) : [];

// ─── 页面组件 ───

const RagMonitor = () => {
  const [rag, setRag] = useState<OverviewSnapshot | null>(null);
  const [gpu, setGpu] = useState<OverviewSnapshot | null>(null);
  const [vllm, setVllm] = useState<OverviewSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const [r, g, v] = await Promise.all([
        mcpApi.callTool('get_rag_overview', {}),
        mcpApi.callTool('get_gpu_overview', {}),
        mcpApi.callTool('get_vllm_overview', {}),
      ]);
      setRag(r as OverviewSnapshot);
      setGpu(g as OverviewSnapshot);
      setVllm(v as OverviewSnapshot);
    } catch (error) {
      message.error('获取监控快照失败');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchData]);

  // 自动刷新（30s）
  useEffect(() => {
    if (autoRefresh) {
      timerRef.current = setInterval(() => fetchData(false), 30000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [autoRefresh, fetchData]);

  const ragMetrics = rag?.metrics || {};
  const gpuMetrics = gpu?.metrics || {};
  const vllmMetrics = vllm?.metrics || {};

  const renderGrafanaLink = (snapshot: OverviewSnapshot | null, text: string) =>
    snapshot?.dashboard_url ? (
      <Button size="small" icon={<LinkOutlined />} href={snapshot.dashboard_url} target="_blank">
        {text}
      </Button>
    ) : null;

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Title level={4} style={{ margin: 0 }}>RAG 监控</Title>
        <Space>
          <Tag color={autoRefresh ? 'green' : 'default'}
            onClick={() => setAutoRefresh(!autoRefresh)} style={{ cursor: 'pointer' }}>
            {autoRefresh ? '自动刷新 30s' : '自动刷新关闭'}
          </Tag>
          <Button icon={<ReloadOutlined />} onClick={() => fetchData()} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      {loading && !rag && (
        <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
      )}

      {/* ── 状态概览 ── */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="RAG 服务"
              value={rag?.status ?? '未获取'}
              valueStyle={{ color: statusColor(rag?.status || '') }}
              prefix={<StatusIcon status={rag?.status || ''} />}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              {rag?.summary}
            </Text>
            {rag && renderGrafanaLink(rag, '打开 RAG Dashboard')}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="系统与 GPU"
              value={gpu?.status ?? '未获取'}
              valueStyle={{ color: statusColor(gpu?.status || '') }}
              prefix={<StatusIcon status={gpu?.status || ''} />}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              {gpu?.summary}
            </Text>
            {gpu && renderGrafanaLink(gpu, '打开 GPU Dashboard')}
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="vLLM 推理引擎"
              value={vllm?.status ?? '未获取'}
              valueStyle={{ color: statusColor(vllm?.status || '') }}
              prefix={<StatusIcon status={vllm?.status || ''} />}
            />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              {vllm?.summary}
            </Text>
            {vllm && renderGrafanaLink(vllm, '打开 vLLM Dashboard')}
          </Card>
        </Col>
      </Row>

      {/* ── 告警/警告汇总 ── */}
      {(rag?.warnings?.length || gpu?.warnings?.length || vllm?.warnings?.length) ? (
        <Alert
          style={{ marginTop: 16 }}
          type="warning"
          showIcon
          message="监控告警"
          description={
            <Space direction="vertical" size={2}>
              {[...(rag?.warnings || []), ...(gpu?.warnings || []), ...(vllm?.warnings || [])]
                .map((w, i) => <div key={i}>• {w}</div>)}
            </Space>
          }
        />
      ) : null}

      <Tabs
        style={{ marginTop: 16 }}
        items={[
          {
            key: 'rag',
            label: <span><ThunderboltOutlined /> RAG 服务</span>,
            children: <RagDetail metrics={ragMetrics} errors={rag?.errors || []} />,
          },
          {
            key: 'gpu',
            label: <span><ThunderboltOutlined /> 系统与 GPU</span>,
            children: <GpuDetail metrics={gpuMetrics} />,
          },
          {
            key: 'vllm',
            label: <span><ThunderboltOutlined /> vLLM 引擎</span>,
            children: <VllmDetail metrics={vllmMetrics} />,
          },
        ]}
      />
    </div>
  );
};

// ─── RAG 详情 ───

const RagDetail = ({ metrics, errors }: { metrics: Record<string, unknown>; errors: Array<Record<string, unknown>> }) => {
  const qualityItems = [
    { key: 'faithfulness', label: 'Faithfulness', value: num(metrics.faithfulness) },
    { key: 'answer_relevancy', label: 'Answer Relevancy', value: num(metrics.answer_relevancy) },
    { key: 'context_precision', label: 'Context Precision', value: num(metrics.context_precision) },
  ];

  const nodeDurationRows = toList(metrics.node_duration).map((item, i) => ({
    key: `avg-${i}`,
    node: String(item.node ?? '?'),
    metric: '平均耗时',
    value: num(item.value),
  }));
  const nodeP95Rows = toList(metrics.node_p95).map((item, i) => ({
    key: `p95-${i}`,
    node: String(item.node ?? '?'),
    metric: 'p95',
    value: num(item.value),
  }));

  const intentRows = toList(metrics.requests_by_intent).map((item, i) => ({
    key: i,
    intent: String(item.intent ?? '?'),
    count: num(item.value),
  }));

  return (
    <>
      <Row gutter={[16, 16]}>
      <Col xs={24} md={12}>
        <Card size="small" title="请求与缓存">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="总请求数">{fmtNum(metrics.request_total, 0)}</Descriptions.Item>
            <Descriptions.Item label="缓存命中">{fmtNum(metrics.cache_hit, 0)}</Descriptions.Item>
            <Descriptions.Item label="缓存未命中">{fmtNum(metrics.cache_miss, 0)}</Descriptions.Item>
            <Descriptions.Item label="Rerank 过滤率">{fmtPct(metrics.rerank_filter_rate)}</Descriptions.Item>
            <Descriptions.Item label="Rerank 文档数">{fmtNum(metrics.rerank_docs, 0)}</Descriptions.Item>
            <Descriptions.Item label="Rerank 平均分">{fmtNum(metrics.rerank_scores_avg)}</Descriptions.Item>
            <Descriptions.Item label="Token 消耗">{fmtNum(metrics.tokens_total, 0)}</Descriptions.Item>
            <Descriptions.Item label="反馈 赞/踩">
              {fmtNum(metrics.feedback_upvote, 0)} / {fmtNum(metrics.feedback_downvote, 0)}
            </Descriptions.Item>
          </Descriptions>
          <div style={{ marginTop: 12 }}>
            <Text strong>缓存命中率: </Text>
            <Progress
              percent={Math.min((num(metrics.cache_hit_rate) ?? 0) * 100, 100)}
              status={num(metrics.cache_hit_rate) === 0 ? 'exception' : 'active'}
              strokeColor={num(metrics.cache_hit_rate) !== null && num(metrics.cache_hit_rate)! < 30 ? '#faad14' : undefined}
            />
          </div>
          {intentRows.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Text strong>请求意图分布</Text>
              <Table
                size="small"
                rowKey="key"
                pagination={false}
                dataSource={intentRows}
                columns={[
                  { title: '意图', dataIndex: 'intent' },
                  { title: '请求数', dataIndex: 'count', render: (v: number) => fmtNum(v, 0) },
                ]}
              />
            </div>
          )}
        </Card>
      </Col>
      <Col xs={24} md={12}>
        <Card size="small" title="RAG 质量指标">
          {qualityItems.map(({ key, label, value }) => (
            <div key={key} style={{ marginBottom: 12 }}>
              <Text strong>{label}: </Text>
              <Progress
                percent={Math.min((value ?? 0) * 100, 100)}
                strokeColor={value !== null && value! < 0.5 ? '#faad14' : undefined}
              />
            </div>
          ))}
        </Card>
      </Col>
    </Row>

    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} md={12}>
        <Card size="small" title="节点耗时 (ms)">
          <Table
            size="small"
            rowKey="key"
            pagination={false}
            dataSource={[...nodeDurationRows, ...nodeP95Rows]}
            columns={[
              { title: '节点', dataIndex: 'node' },
              { title: '指标', dataIndex: 'metric', width: 80 },
              {
                title: '耗时 (ms)',
                dataIndex: 'value',
                width: 120,
                render: (v: number | null) => (
                  <Text style={{ color: v !== null && v > 5000 ? '#ff4d4f' : undefined }}>
                    {fmtNum(v, 1)}
                  </Text>
                ),
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={24} md={12}>
        <Card size="small" title={`错误日志 (${errors.length})`}>
          {errors.length === 0 ? (
            <Text type="secondary">最近 1 小时无 ERROR 日志</Text>
          ) : (
            <Table
              size="small"
              rowKey={(_, i) => String(i)}
              pagination={false}
              dataSource={errors}
              columns={[
                { title: '时间', dataIndex: 'timestamp', width: 160, render: (v: string) => <Text type="secondary">{v}</Text> },
                { title: '容器', dataIndex: 'container', width: 110, render: (v: string) => <Tag>{v}</Tag> },
                { title: '消息', dataIndex: 'message', ellipsis: true },
              ]}
            />
          )}
        </Card>
      </Col>
    </Row>
    </>
  );
};

// ─── GPU 详情 ───

const GpuDetail = ({ metrics }: { metrics: Record<string, unknown> }) => {
  const memUsedArr = (metrics.gpu_mem_used as Array<Record<string, unknown>>) || [];
  const memTotalArr = (metrics.gpu_mem_total as Array<Record<string, unknown>>) || [];
  const tempArr = (metrics.gpu_temp as Array<Record<string, unknown>>) || [];
  const powerArr = (metrics.gpu_power as Array<Record<string, unknown>>) || [];

  const gpuRows = toList(metrics.gpu_util).map((item, i) => ({
    key: i,
    gpu: String(item.gpu ?? `GPU ${i}`),
    util: num(item.value),
    memUsed: num(memUsedArr[i]?.value),
    memTotal: num(memTotalArr[i]?.value),
    temp: num(tempArr[i]?.value),
    power: num(powerArr[i]?.value),
  }));

  return (
  <>
    <Row gutter={[16, 16]}>
      {[
        { label: 'CPU 使用率', value: num(metrics.cpu_usage_pct), danger: 90 },
        { label: '内存使用率', value: num(metrics.memory_usage_pct), danger: 90 },
        { label: '磁盘使用率', value: num(metrics.disk_usage_pct), danger: 90 },
      ].map(({ label, value, danger }) => (
        <Col xs={24} md={8} key={label}>
          <Card size="small" title={label}>
            <Progress
              type="dashboard"
              percent={Math.min(value ?? 0, 100)}
              status={value !== null && value! >= danger ? 'exception' : value !== null && value! >= 80 ? 'normal' : 'success'}
            />
          </Card>
        </Col>
      ))}
    </Row>

    <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
      <Col xs={24} md={12}>
        <Card size="small" title="主机资源">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="CPU 核数">{fmtNum(metrics.cpu_cores, 0)}</Descriptions.Item>
            <Descriptions.Item label="系统负载 (1m)">{fmtNum(metrics.load)}</Descriptions.Item>
            <Descriptions.Item label="内存总量">{fmtBytes(metrics.mem_total_bytes)}</Descriptions.Item>
            <Descriptions.Item label="磁盘总量">{fmtBytes(metrics.disk_total_bytes)}</Descriptions.Item>
          </Descriptions>
        </Card>
      </Col>
      <Col xs={24} md={12}>
        <Card size="small" title="I/O 速率">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="磁盘读取">{fmtSpeed(metrics.disk_io_read)}</Descriptions.Item>
            <Descriptions.Item label="磁盘写入">{fmtSpeed(metrics.disk_io_write)}</Descriptions.Item>
            <Descriptions.Item label="网络接收">{fmtSpeed(metrics.network_rx)}</Descriptions.Item>
            <Descriptions.Item label="网络发送">{fmtSpeed(metrics.network_tx)}</Descriptions.Item>
          </Descriptions>
        </Card>
      </Col>
    </Row>

    <Card size="small" title="GPU 详情" style={{ marginTop: 16 }}>
      {gpuRows.length === 0 ? (
        <Text type="secondary">无 GPU 数据（或 GPU 空闲无采样）</Text>
      ) : (
        <Table
          size="small"
          rowKey="key"
          pagination={false}
          dataSource={gpuRows}
          columns={[
            { title: 'GPU', dataIndex: 'gpu' },
            {
              title: '利用率',
              dataIndex: 'util',
              render: (v: number | null) => (
                <Progress percent={Math.min(v ?? 0, 100)} size="small"
                  status={v !== null && v! > 90 ? 'exception' : undefined} />
              ),
            },
            { title: '显存已用/总量', key: 'mem', render: (_, row) => `${fmtBytes(row.memUsed)} / ${fmtBytes(row.memTotal)}` },
            { title: '温度 (°C)', dataIndex: 'temp', render: (v: number | null) => <Text style={{ color: v !== null && v! > 85 ? '#ff4d4f' : undefined }}>{fmtNum(v, 0)}</Text> },
            { title: '功耗 (W)', dataIndex: 'power', render: (v: number | null) => fmtNum(v, 0) },
          ]}
        />
      )}
    </Card>
  </>
  );
};

// ─── vLLM 详情 ───

function VllmDetail({ metrics }: { metrics: Record<string, unknown> }) {
  return (
  <>
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12}>
        <Card size="small" title="引擎状态">
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="引擎状态">
              {num(metrics.engine_awake) === 1 ? <Tag color="green">活跃</Tag> : <Tag color="red">休眠/异常</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="运行中请求">{fmtNum(metrics.requests_running, 0)}</Descriptions.Item>
            <Descriptions.Item label="等待请求">{fmtNum(metrics.requests_waiting, 0)}</Descriptions.Item>
            <Descriptions.Item label="QPS (1m)">{fmtNum(metrics.qps_1m)}</Descriptions.Item>
            <Descriptions.Item label="QPS (5m)">{fmtNum(metrics.qps_5m)}</Descriptions.Item>
            <Descriptions.Item label="累计 Token">{fmtNum(metrics.tokens_total, 0)}</Descriptions.Item>
            <Descriptions.Item label="Token 速率 (t/s)">{fmtNum(metrics.tokens_per_sec)}</Descriptions.Item>
          </Descriptions>
        </Card>
      </Col>
      <Col xs={24} md={12}>
        <Card size="small" title="KV Cache 使用率">
          <Progress
            type="dashboard"
            percent={Math.min(num(metrics.kv_cache_usage_pct) ?? 0, 100)}
            status={(num(metrics.kv_cache_usage_pct) ?? 0) > 90 ? 'exception' : 'active'}
          />
        </Card>
      </Col>
    </Row>

    <Card size="small" title="TTFT 首 token 延迟 (秒)" style={{ marginTop: 16 }}>
      <Descriptions size="small" column={3}>
        <Descriptions.Item label="p50">{fmtNum(metrics.ttft_p50, 2)}</Descriptions.Item>
        <Descriptions.Item label="p95">{fmtNum(metrics.ttft_p95, 2)}</Descriptions.Item>
        <Descriptions.Item label="p99">{fmtNum(metrics.ttft_p99, 2)}</Descriptions.Item>
      </Descriptions>
      <Text type="secondary" style={{ fontSize: 12 }}>
        <Tooltip title="最近 5 分钟采样，无推理请求时显示为空">
          说明：无近期推理请求时 TTFT 无数据（-）
        </Tooltip>
      </Text>
    </Card>
  </>
  );
}

export default RagMonitor;
