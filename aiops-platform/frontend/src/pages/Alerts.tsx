import { useEffect, useState } from 'react';
import { Card, Table, Tag, Statistic, Row, Col, Badge, Timeline, message, Select, Space, Button, Modal, Descriptions, List } from 'antd';
import { AlertOutlined, CheckCircleOutlined, ExclamationCircleOutlined, InfoCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';

import { alertsApi } from '../services/api';
import type { Alert, ClusteredAlerts, AlertStats, AlertCluster } from '../types';

const Alerts = () => {
  const [loading, setLoading] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [clusteredAlerts, setClusteredAlerts] = useState<ClusteredAlerts | null>(null);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<AlertCluster | null>(null);
  const [lookback, setLookback] = useState('1h');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [alertsData, clusteredData, statsData] = await Promise.all([
        alertsApi.getAlerts({ limit: 100 }),
        alertsApi.getClusteredAlerts(lookback),
        alertsApi.getAlertStats(lookback),
      ]);
      setAlerts(alertsData);
      setClusteredAlerts(clusteredData);
      setStats(statsData);
    } catch (error) {
      message.error('获取告警数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [lookback]);

  const getSeverityColor = (severity: string) => {
    const colors: Record<string, string> = {
      critical: 'red',
      warning: 'orange',
      info: 'blue',
    };
    return colors[severity] || 'default';
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'warning':
        return <AlertOutlined style={{ color: '#faad14' }} />;
      default:
        return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
    }
  };

  const columns = [
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Badge
          status={status === 'firing' ? 'error' : 'success'}
          text={status === 'firing' ? '告警中' : '已恢复'}
        />
      ),
    },
    {
      title: '严重级别',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (severity: string) => (
        <Tag color={getSeverityColor(severity)} icon={getSeverityIcon(severity)}>
          {severity.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: '告警名称',
      dataIndex: ['labels', 'alertname'],
      key: 'alertname',
      width: 200,
    },
    {
      title: '服务',
      dataIndex: ['labels', 'service'],
      key: 'service',
      width: 150,
      render: (service: string) => service || '-',
    },
    {
      title: '实例',
      dataIndex: ['labels', 'instance'],
      key: 'instance',
      width: 150,
    },
    {
      title: '描述',
      dataIndex: ['annotations', 'summary'],
      key: 'summary',
      ellipsis: true,
      render: (summary: string, record: Alert) => summary || record.annotations?.description || '-',
    },
    {
      title: '开始时间',
      dataIndex: 'startsAt',
      key: 'startsAt',
      width: 180,
      render: (time: string) => dayjs(time).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '聚类',
      dataIndex: 'cluster_id',
      key: 'cluster_id',
      width: 80,
      render: (clusterId: number) => clusterId ? <Tag color="purple">#{clusterId}</Tag> : '-',
    },
  ];

  const getSeverityChartOption = () => ({
    title: { text: '告警级别分布', left: 'center' },
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data: stats
        ? Object.entries(stats.by_severity).map(([name, value]) => ({
            name: name.toUpperCase(),
            value,
            itemStyle: { color: getSeverityColor(name) },
          }))
        : [],
    }],
  });

  const getServiceChartOption = () => ({
    title: { text: '服务告警 Top 10', left: 'center' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: stats ? Object.keys(stats.by_service).slice(0, 10) : [], axisLabel: { rotate: 45 } },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: stats ? Object.values(stats.by_service).slice(0, 10) : [],
      itemStyle: { color: '#1890ff' },
    }],
  });

  const getTrendChartOption = () => ({
    title: { text: '告警趋势', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: stats?.trend.map(t => dayjs(t.time).format('HH:mm')) || [],
    },
    yAxis: { type: 'value' },
    series: [{
      data: stats?.trend.map(t => t.count) || [],
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.3 },
    }],
  });

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col span={4}>
            <Statistic
              title="总告警数"
              value={stats?.total || 0}
              prefix={<AlertOutlined />}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="告警中"
              value={stats?.firing || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="已恢复"
              value={stats?.resolved || 0}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="聚类数"
              value={clusteredAlerts?.cluster_count || 0}
              suffix={`/ ${clusteredAlerts?.total_alerts || 0} 条`}
            />
          </Col>
          <Col span={8} style={{ textAlign: 'right' }}>
            <Space>
              <Select value={lookback} onChange={setLookback} style={{ width: 120 }}>
                <Select.Option value="15m">最近 15 分钟</Select.Option>
                <Select.Option value="1h">最近 1 小时</Select.Option>
                <Select.Option value="6h">最近 6 小时</Select.Option>
                <Select.Option value="24h">最近 24 小时</Select.Option>
              </Select>
              <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card>
            <ReactECharts option={getSeverityChartOption()} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <ReactECharts option={getServiceChartOption()} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <ReactECharts option={getTrendChartOption()} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>

      {clusteredAlerts && clusteredAlerts.clusters.length > 0 && (
        <Card title="告警聚类" style={{ marginTop: 16 }}>
          <Timeline>
            {clusteredAlerts.clusters.map((cluster) => (
              <Timeline.Item
                key={cluster.cluster_id}
                color={cluster.severity === 'critical' ? 'red' : cluster.severity === 'warning' ? 'orange' : 'blue'}
                dot={<Badge count={cluster.count} style={{ backgroundColor: getSeverityColor(cluster.severity) }} />}
              >
                <Card
                  size="small"
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedCluster(cluster)}
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Space>
                      <Tag color={getSeverityColor(cluster.severity)}>{cluster.severity.toUpperCase()}</Tag>
                      <span style={{ fontWeight: 'bold' }}>聚类 #{cluster.cluster_id}</span>
                      <span style={{ color: '#666' }}>{cluster.count} 条告警</span>
                    </Space>
                    <div style={{ color: '#666' }}>{cluster.pattern}</div>
                    <Space>
                      <span>服务: {cluster.services.join(', ')}</span>
                      <span>|</span>
                      <span>首次: {dayjs(cluster.first_occurrence).format('HH:mm:ss')}</span>
                      <span>|</span>
                      <span>最近: {dayjs(cluster.last_occurrence).format('HH:mm:ss')}</span>
                    </Space>
                  </Space>
                </Card>
              </Timeline.Item>
            ))}
          </Timeline>
        </Card>
      )}

      <Card title="告警列表" style={{ marginTop: 16 }}>
        <Table
          columns={columns}
          dataSource={alerts}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      </Card>

      <Modal
        title={`聚类 #${selectedCluster?.cluster_id} 详情`}
        open={!!selectedCluster}
        onCancel={() => setSelectedCluster(null)}
        footer={null}
        width={800}
      >
        {selectedCluster && (
          <div>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="模式">{selectedCluster.pattern}</Descriptions.Item>
              <Descriptions.Item label="告警数">{selectedCluster.count}</Descriptions.Item>
              <Descriptions.Item label="严重级别">
                <Tag color={getSeverityColor(selectedCluster.severity)}>{selectedCluster.severity.toUpperCase()}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="服务">{selectedCluster.services.join(', ')}</Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 16 }}>
              <strong>示例告警：</strong>
              <List
                size="small"
                dataSource={selectedCluster.sample_alerts.slice(0, 5)}
                renderItem={(alert) => (
                  <List.Item>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Space>
                        <Tag color={getSeverityColor(alert.severity)}>{alert.severity}</Tag>
                        <Tag>{alert.labels?.alertname}</Tag>
                        <span>{alert.labels?.instance}</span>
                      </Space>
                      <div style={{ color: '#666' }}>{alert.annotations?.summary || alert.annotations?.description}</div>
                    </Space>
                  </List.Item>
                )}
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Alerts;
