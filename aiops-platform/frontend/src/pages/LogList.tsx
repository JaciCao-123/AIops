import { useEffect, useState, useCallback } from 'react';
import { Table, Card, Tag, Button, Select, Space, message, Modal, Typography } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

import { logsApi } from '../services/api';
import type { Log } from '../types';

const { Text } = Typography;

const LogList = () => {
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(false);
  const [levelFilter, setLevelFilter] = useState<string | undefined>();
  const [anomalyFilter, setAnomalyFilter] = useState<boolean | undefined>();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await logsApi.getLogs({
        level: levelFilter,
        is_anomaly: anomalyFilter,
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      });
      setLogs(data);
      setPagination(prev => ({ ...prev, total: data.length < pagination.pageSize ? prev.total : prev.total + data.length }));
    } catch (error) {
      message.error('获取日志失败');
    } finally {
      setLoading(false);
    }
  }, [levelFilter, anomalyFilter, pagination.current, pagination.pageSize]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleFeedback = async (logId: number, feedbackType: boolean) => {
    try {
      await logsApi.submitFeedback(logId, feedbackType);
      message.success('反馈已提交');
      fetchLogs();
    } catch (error) {
      message.error('提交失败');
    }
  };

  const showDetail = (log: Log) => {
    Modal.info({
      title: '日志详情',
      width: 800,
      content: (
        <div style={{ marginTop: 16 }}>
          <p><Text strong>时间：</Text>{dayjs(log.timestamp).format('YYYY-MM-DD HH:mm:ss')}</p>
          <p><Text strong>级别：</Text><Tag color={log.level === 'ERROR' ? 'red' : log.level === 'WARN' ? 'orange' : 'blue'}>{log.level}</Tag></p>
          <p><Text strong>来源：</Text>{log.source}</p>
          <p><Text strong>异常分数：</Text>{log.anomaly_score?.toFixed(3) || 'N/A'}</p>
          <p><Text strong>用户反馈：</Text>
            {log.user_feedback === null ? '未标注' : log.user_feedback ? '误报' : '确认异常'}
          </p>
          <p><Text strong>内容：</Text></p>
          <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, overflow: 'auto', maxHeight: 300 }}>
            {log.content}
          </pre>
        </div>
      ),
    });
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (level: string) => {
        const colorMap: Record<string, string> = { ERROR: 'red', WARN: 'orange', INFO: 'blue', DEBUG: 'gray' };
        return <Tag color={colorMap[level] || 'default'}>{level}</Tag>;
      },
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      className: 'log-content',
      render: (text: string, record: Log) => (
        <a onClick={() => showDetail(record)} style={{ color: record.is_anomaly ? '#cf1322' : undefined }}>
          {text}
        </a>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 80,
    },
    {
      title: '异常',
      dataIndex: 'is_anomaly',
      key: 'is_anomaly',
      width: 100,
      render: (isAnomaly: boolean, record: Log) => 
        isAnomaly ? (
          <Tag color="red" className="anomaly-tag">异常 ({record.anomaly_score?.toFixed(2)})</Tag>
        ) : (
          <Tag color="green">正常</Tag>
        ),
    },
    {
      title: '反馈',
      key: 'feedback',
      width: 150,
      render: (_: unknown, record: Log) => (
        <Space size="small">
          <Button
            size="small"
            type="text"
            icon={<CloseCircleOutlined style={{ color: record.user_feedback === true ? '#52c41a' : undefined }} />}
            onClick={() => handleFeedback(record.id, true)}
            title="标记为误报"
          />
          <Button
            size="small"
            type="text"
            icon={<CheckCircleOutlined style={{ color: record.user_feedback === false ? '#cf1322' : undefined }} />}
            onClick={() => handleFeedback(record.id, false)}
            title="确认异常"
          />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="日志级别"
            allowClear
            style={{ width: 120 }}
            value={levelFilter}
            onChange={setLevelFilter}
            options={[
              { value: 'ERROR', label: 'ERROR' },
              { value: 'WARN', label: 'WARN' },
              { value: 'INFO', label: 'INFO' },
              { value: 'DEBUG', label: 'DEBUG' },
            ]}
          />
          <Select
            placeholder="异常状态"
            allowClear
            style={{ width: 120 }}
            value={anomalyFilter}
            onChange={setAnomalyFilter}
            options={[
              { value: true, label: '异常' },
              { value: false, label: '正常' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchLogs}>刷新</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => setPagination(prev => ({ ...prev, current: page, pageSize })),
          }}
          size="small"
        />
      </Card>
    </div>
  );
};

export default LogList;
