import { useState, useRef, useEffect } from 'react';
import { Card, Input, Button, List, Spin, message, Typography, Space, Empty, Tooltip } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, ClearOutlined, ReloadOutlined } from '@ant-design/icons';
import { aiChatApi } from '../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const AIChat = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) {
      message.warning('请输入内容');
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const chatMessages = [...messages, userMessage].map(m => ({
        role: m.role,
        content: m.content,
      }));

      const response = await aiChatApi.chat(chatMessages);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      message.error('对话失败，请稍后重试');
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，我遇到了一些问题，请稍后再试。',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    message.success('对话已清空');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div style={{ height: 'calc(100vh - 144px)', display: 'flex', flexDirection: 'column' }}>
      <Card 
        title={
          <Space>
            <RobotOutlined style={{ color: '#1890ff' }} />
            <span>AI助手</span>
          </Space>
        }
        extra={
          <Space>
            <Tooltip title="清空对话">
              <Button 
                icon={<ClearOutlined />} 
                onClick={handleClear}
                disabled={messages.length === 0}
              >
                清空
              </Button>
            </Tooltip>
          </Space>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, overflow: 'auto', padding: 16 }}
      >
        {messages.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space direction="vertical" size="small">
                <Text>开始与 AI 助手对话</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  你可以问我任何问题，例如：
                </Text>
                <Space wrap>
                  <Text code>如何排查 CPU 使用率过高？</Text>
                  <Text code>MySQL 死锁怎么处理？</Text>
                  <Text code>解释一下微服务架构</Text>
                </Space>
              </Space>
            }
          />
        ) : (
          <div style={{ padding: '0 8px' }}>
            {messages.map((item) => (
              <div 
                key={item.id}
                style={{ 
                  marginBottom: 16, 
                  display: 'flex',
                  justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div style={{ maxWidth: '80%', display: 'flex', gap: 8 }}>
                  {item.role === 'assistant' && (
                    <div 
                      style={{ 
                        width: 32, 
                        height: 32, 
                        borderRadius: '50%', 
                        background: '#1890ff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <RobotOutlined style={{ color: '#fff' }} />
                    </div>
                  )}
                  <div>
                    <div
                      style={{
                        display: 'inline-block',
                        padding: '12px 16px',
                        borderRadius: 12,
                        background: item.role === 'user' ? '#1890ff' : '#f5f5f5',
                        color: item.role === 'user' ? '#fff' : 'inherit',
                        borderTopLeftRadius: item.role === 'assistant' ? 4 : 12,
                        borderTopRightRadius: item.role === 'user' ? 4 : 12,
                      }}
                    >
                      <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                        {item.content}
                      </Paragraph>
                    </div>
                    <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>
                      {formatTime(item.timestamp)}
                    </Text>
                  </div>
                  {item.role === 'user' && (
                    <div 
                      style={{ 
                        width: 32, 
                        height: 32, 
                        borderRadius: '50%', 
                        background: '#87d068',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <UserOutlined style={{ color: '#fff' }} />
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <div 
                  style={{ 
                    width: 32, 
                    height: 32, 
                    borderRadius: '50%', 
                    background: '#1890ff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <RobotOutlined style={{ color: '#fff' }} />
                </div>
                <div style={{ 
                  padding: '12px 16px', 
                  background: '#f5f5f5', 
                  borderRadius: 12,
                  borderTopLeftRadius: 4,
                }}>
                  <Spin size="small" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </Card>

      <Card style={{ marginTop: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            style={{ flex: 1 }}
            disabled={loading}
          />
          <Button 
            type="primary" 
            icon={<SendOutlined />} 
            onClick={handleSend}
            loading={loading}
            style={{ height: 'auto', minHeight: 32 }}
          >
            发送
          </Button>
        </Space.Compact>
        <Text type="secondary" style={{ fontSize: 11, marginTop: 8, display: 'block' }}>
          按 Enter 发送，Shift + Enter 换行
        </Text>
      </Card>
    </div>
  );
};

export default AIChat;
