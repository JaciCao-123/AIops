import { useState } from 'react';
import { Card, Input, Button, List, Tag, Spin, message, Typography, Space, Divider } from 'antd';
import { SendOutlined, QuestionCircleOutlined } from '@ant-design/icons';

import { knowledgeApi } from '../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface Message {
  id: number;
  type: 'user' | 'assistant';
  content: string;
  loading?: boolean;
  extra?: {
    intent?: {
      intent: string;
      entities: Record<string, string>;
      confidence: string;
    };
    knowledge?: string;
  };
}

const QA = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      type: 'assistant',
      content: '你好！我是AIOps智能问答助手。你可以问我关于运维的问题，例如：\n• 订单服务的依赖关系是什么？\n• 如何处理数据库连接池耗尽？\n• 最近有哪些故障案例？',
    },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) {
      message.warning('请输入问题');
      return;
    }

    const userMessage: Message = {
      id: Date.now(),
      type: 'user',
      content: input,
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const assistantMessage: Message = {
      id: Date.now() + 1,
      type: 'assistant',
      content: '',
      loading: true,
    };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const response = await knowledgeApi.chat(input);
      
      const updatedMessage: Message = {
        id: assistantMessage.id,
        type: 'assistant',
        content: (response as { answer?: string }).answer || '抱歉，我无法回答这个问题。',
        loading: false,
        extra: {
          intent: (response as { intent?: { intent: string; entities: Record<string, string>; confidence: string } }).intent,
          knowledge: (response as { knowledge?: { knowledge_report?: string } }).knowledge?.knowledge_report,
        },
      };
      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? updatedMessage : m));
    } catch (error) {
      const errorMessage: Message = {
        id: assistantMessage.id,
        type: 'assistant',
        content: '抱歉，查询过程中出现错误，请稍后重试。',
        loading: false,
      };
      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? errorMessage : m));
    } finally {
      setLoading(false);
    }
  };

  const getIntentColor = (intent: string) => {
    const colors: Record<string, string> = { 
      DIAGNOSE: 'blue', 
      QUERY_STATUS: 'green', 
      EXECUTE_FIX: 'orange', 
      GENERAL_QA: 'purple' 
    };
    return colors[intent] || 'default';
  };

  return (
    <div style={{ height: 'calc(100vh - 144px)', display: 'flex', flexDirection: 'column' }}>
      <Card 
        title={
          <span>
            <QuestionCircleOutlined style={{ marginRight: 8 }} />
            智能问答
          </span>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, overflow: 'auto', padding: 16 }}
      >
        <List
          dataSource={messages}
          renderItem={(item) => (
            <div style={{ 
              marginBottom: 16, 
              textAlign: item.type === 'user' ? 'right' : 'left' 
            }}>
              <div style={{
                display: 'inline-block',
                maxWidth: '80%',
                textAlign: 'left',
                padding: '12px 16px',
                borderRadius: 8,
                background: item.type === 'user' ? '#1890ff' : '#f5f5f5',
                color: item.type === 'user' ? '#fff' : 'inherit',
              }}>
                {item.loading ? (
                  <Spin size="small" />
                ) : (
                  <>
                    <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                      {item.content}
                    </Paragraph>
                    
                    {item.extra?.intent && (
                      <div style={{ marginTop: 12 }}>
                        <Divider style={{ margin: '8px 0' }} />
                        <Space size={4} wrap>
                          <Tag color={getIntentColor(item.extra.intent.intent)}>
                            {item.extra.intent.intent}
                          </Tag>
                          <Tag>置信度: {item.extra.intent.confidence}</Tag>
                          {item.extra.intent.entities.service && (
                            <Tag color="blue">服务: {item.extra.intent.entities.service}</Tag>
                          )}
                        </Space>
                      </div>
                    )}
                    
                    {item.extra?.knowledge && (
                      <div style={{ marginTop: 12 }}>
                        <Divider style={{ margin: '8px 0' }} />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          知识库参考：
                        </Text>
                        <Paragraph 
                          style={{ 
                            margin: 0, 
                            fontSize: 12, 
                            whiteSpace: 'pre-wrap',
                            color: item.type === 'user' ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.45)'
                          }}
                          ellipsis={{ rows: 3, expandable: true }}
                        >
                          {item.extra.knowledge}
                        </Paragraph>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        />
      </Card>

      <Card style={{ marginTop: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入你的运维问题..."
            autoSize={{ minRows: 1, maxRows: 3 }}
            style={{ flex: 1 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <Button 
            type="primary" 
            icon={<SendOutlined />} 
            onClick={handleSend}
            loading={loading}
            style={{ height: 'auto' }}
          >
            发送
          </Button>
        </Space.Compact>
      </Card>
    </div>
  );
};

export default QA;
