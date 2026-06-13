import { useState, useRef, useEffect, useCallback } from 'react';
import { Card, Input, Button, List, Spin, message, Typography, Space, Empty, Tooltip, Modal, InputRef } from 'antd';
import { 
  SendOutlined, RobotOutlined, UserOutlined, ClearOutlined, 
  PlusOutlined, DeleteOutlined, EditOutlined, MessageOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { aiChatApi, ChatSession } from '../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

const AIChat = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<InputRef>(null);
  const streamingMessageIdRef = useRef<string | null>(null);

  const scrollToBottom = useCallback(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const data = await aiChatApi.getSessions();
      setSessions(data);
    } catch (error) {
      console.error('加载会话列表失败:', error);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const loadSessionMessages = async (sessionId: string) => {
    try {
      const sessionDetail = await aiChatApi.getSession(sessionId);
      const loadedMessages: Message[] = sessionDetail.messages.map((m, index) => ({
        id: `${sessionId}-${index}`,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: new Date(),
      }));
      setMessages(loadedMessages);
    } catch (error) {
      console.error('加载会话消息失败:', error);
      message.error('加载会话消息失败');
    }
  };

  const handleSelectSession = async (session: ChatSession) => {
    setCurrentSession(session);
    await loadSessionMessages(session.session_id);
    inputRef.current?.focus();
  };

  const handleNewSession = async () => {
    setCurrentSession(null);
    setMessages([]);
    inputRef.current?.focus();
  };

  const handleDeleteSession = (session: ChatSession) => {
    Modal.confirm({
      title: '删除会话',
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除会话 "${session.title}" 吗？`,
      okText: '删除',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await aiChatApi.deleteSession(session.session_id);
          message.success('会话已删除');
          if (currentSession?.session_id === session.session_id) {
            setCurrentSession(null);
            setMessages([]);
          }
          loadSessions();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };

  const handleEditTitle = (session: ChatSession) => {
    setEditingTitle(session.session_id);
    setNewTitle(session.title);
  };

  const handleSaveTitle = async (sessionId: string) => {
    if (!newTitle.trim()) {
      message.warning('标题不能为空');
      return;
    }
    try {
      await aiChatApi.updateSessionTitle(sessionId, newTitle.trim());
      message.success('标题已更新');
      setEditingTitle(null);
      loadSessions();
      if (currentSession?.session_id === sessionId) {
        setCurrentSession({ ...currentSession, title: newTitle.trim() });
      }
    } catch (error) {
      message.error('更新失败');
    }
  };

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

    const assistantMessageId = (Date.now() + 1).toString();
    streamingMessageIdRef.current = assistantMessageId;

    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages(prev => [...prev, assistantMessage]);

    try {
      await aiChatApi.chatStream(
        currentSession?.session_id || null,
        input,
        {
          onSession: (sessionId) => {
            if (!currentSession) {
              const newSession: ChatSession = {
                session_id: sessionId,
                title: input.slice(0, 30) + (input.length > 30 ? '...' : ''),
                message_count: 0,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              };
              setCurrentSession(newSession);
              loadSessions();
            }
          },
          onContent: (content) => {
            setMessages(prev => 
              prev.map(m => 
                m.id === assistantMessageId 
                  ? { ...m, content: m.content + content }
                  : m
              )
            );
            scrollToBottom();
          },
          onDone: (_sessionId, messageCount) => {
            setMessages(prev => 
              prev.map(m => 
                m.id === assistantMessageId 
                  ? { ...m, isStreaming: false }
                  : m
              )
            );
            if (currentSession) {
              setCurrentSession({
                ...currentSession,
                message_count: messageCount,
              });
            }
            loadSessions();
          },
          onError: (error) => {
            message.error(`对话失败: ${error}`);
            setMessages(prev => prev.filter(m => m.id !== assistantMessageId));
          },
        }
      );
    } catch (error) {
      message.error('对话失败，请稍后重试');
      setMessages(prev => prev.filter(m => m.id !== assistantMessageId));
    } finally {
      setLoading(false);
      streamingMessageIdRef.current = null;
    }
  };

  const handleClearCurrentSession = () => {
    if (!currentSession) {
      setMessages([]);
      return;
    }
    Modal.confirm({
      title: '清空对话',
      icon: <ExclamationCircleOutlined />,
      content: '确定要清空当前会话的所有消息吗？',
      okText: '清空',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await aiChatApi.clearSessionMessages(currentSession.session_id);
          setMessages([]);
          message.success('对话已清空');
        } catch (error) {
          message.error('清空失败');
        }
      },
    });
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

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return '昨天';
    } else if (days < 7) {
      return `${days}天前`;
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', gap: 16 }}>
      {/* 会话列表 */}
      <Card
        style={{ width: 260, height: '100%', display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, overflow: 'hidden', padding: 0 }}
        title={
          <Space>
            <MessageOutlined />
            <span>会话列表</span>
          </Space>
        }
        extra={
          <Tooltip title="新建会话">
            <Button 
              type="text" 
              icon={<PlusOutlined />} 
              onClick={handleNewSession}
              size="small"
            />
          </Tooltip>
        }
      >
        <div style={{ height: '100%', overflow: 'auto' }}>
          <Spin spinning={sessionsLoading}>
            {sessions.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无会话"
                style={{ marginTop: 40 }}
              />
            ) : (
              <List
                dataSource={sessions}
                renderItem={(session) => (
                  <List.Item
                    onClick={() => handleSelectSession(session)}
                    style={{
                      padding: '12px 16px',
                      cursor: 'pointer',
                      background: currentSession?.session_id === session.session_id ? '#e6f7ff' : 'transparent',
                      borderLeft: currentSession?.session_id === session.session_id ? '3px solid #1890ff' : '3px solid transparent',
                    }}
                    actions={[
                      <Tooltip title="编辑标题" key="edit">
                        <Button
                          type="text"
                          size="small"
                          icon={<EditOutlined />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditTitle(session);
                          }}
                        />
                      </Tooltip>,
                      <Tooltip title="删除" key="delete">
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteSession(session);
                          }}
                        />
                      </Tooltip>,
                    ]}
                  >
                    <List.Item.Meta
                      title={
                        editingTitle === session.session_id ? (
                          <Input
                            size="small"
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                            onPressEnter={() => handleSaveTitle(session.session_id)}
                            onBlur={() => setEditingTitle(null)}
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <Text ellipsis style={{ maxWidth: 120 }}>
                            {session.title}
                          </Text>
                        )
                      }
                      description={
                        <Space size={4}>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {formatDate(session.updated_at)}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            · {session.message_count} 条消息
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Spin>
        </div>
      </Card>

      {/* 对话区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
        <Card 
          title={
            <Space>
              <RobotOutlined style={{ color: '#1890ff' }} />
              <span>{currentSession?.title || 'AI助手'}</span>
              {currentSession && (
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 'normal' }}>
                  (ID: {currentSession.session_id})
                </Text>
              )}
            </Space>
          }
          extra={
            <Space>
              <Tooltip title="清空当前对话">
                <Button 
                  icon={<ClearOutlined />} 
                  onClick={handleClearCurrentSession}
                  disabled={messages.length === 0}
                >
                  清空
                </Button>
              </Tooltip>
            </Space>
          }
          style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column' }}
          bodyStyle={{ flex: 1, overflow: 'hidden', padding: 0, display: 'flex', flexDirection: 'column' }}
        >
          <div 
            ref={messagesContainerRef}
            style={{ 
              flex: 1,
              overflow: 'auto',
              padding: 16,
              minHeight: 0,
            }}
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
                            {item.isStreaming && (
                              <span 
                                style={{ 
                                  display: 'inline-block',
                                  width: 8,
                                  height: 16,
                                  background: '#1890ff',
                                  marginLeft: 2,
                                  animation: 'blink 1s infinite',
                                } as React.CSSProperties}
                              />
                            )}
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
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </Card>

        <Card style={{ marginTop: 16 }}>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={currentSession ? "继续对话..." : "开始新对话..."}
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
            按 Enter 发送，Shift + Enter 换行 · 
            {currentSession ? ` 当前会话: ${currentSession.title}` : ' 新会话'}
          </Text>
        </Card>
      </div>

      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  );
};

export default AIChat;
