import { useState, useEffect } from 'react';
import { Card, Input, Button, Tag, Steps, Spin, message, Typography, Collapse, Descriptions, Space } from 'antd';
import { SendOutlined } from '@ant-design/icons';

import { agentApi } from '../services/api';
import type { AgentTask } from '../types';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

const Diagnose = () => {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentTask, setCurrentTask] = useState<AgentTask | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (polling && currentTask && currentTask.status === 'processing') {
      interval = setInterval(async () => {
        try {
          const task = await agentApi.getTaskStatus(currentTask.task_id);
          setCurrentTask(task);
          if (task.status !== 'processing') {
            setPolling(false);
          }
        } catch (error) {
          message.error('获取任务状态失败');
          setPolling(false);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [polling, currentTask]);

  const handleSubmit = async () => {
    if (!input.trim()) {
      message.warning('请输入故障描述');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/multi-agent/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: input }),
      });

      if (!response.ok) {
        throw new Error('请求失败');
      }

      const data = await response.json();
      
      const stages = data.stages || {};
      const intentParsing = stages.intent_parsing || {};
      const skillMatching = stages.skill_matching || {};
      const obsAnalysis = stages.observability_analysis || {};
      const knowledgeQuery = stages.knowledge_query || {};
      const dynamicExec = stages.dynamic_execution || {};

      const diagnosisPlan = obsAnalysis.diagnosis_plan || null;
      const commandEntries = dynamicExec.command_entries || [];
      const emailApproval = dynamicExec.email_approval || null;

      const dynamicStatus = dynamicExec.status || 'processing';
      let taskStatus: 'completed' | 'processing' | 'needs_confirmation' = 'processing';
      if (dynamicStatus === 'completed') {
        taskStatus = 'completed';
      } else if (dynamicStatus === 'needs_confirmation' || dynamicStatus === 'waiting_approval' 
                 || data.final_decision?.decision === 'NEEDS_CONFIRMATION') {
        taskStatus = 'needs_confirmation';
      }
      
      setCurrentTask({
        task_id: 'multi-agent-' + Date.now(),
        user_input: input,
        status: taskStatus,
        intent_data: intentParsing,
        analysis_report: {
          analysis_report: obsAnalysis.analysis_report || data.raw_response || '',
          diagnosis_plan: diagnosisPlan,
        },
        knowledge_context: {
          knowledge_report: knowledgeQuery.knowledge_report || '',
          service: knowledgeQuery.service || '',
        },
        decision: data.final_decision || null,
        action_result: data.execution_result || null,
        created_at: data.start_time,
        updated_at: data.end_time,
        warning_cleared: data.warning_cleared || false,
        server_status_check: data.stages?.server_status_check || null,
        mode: data.mode,
        iterations: dynamicExec.iterations,
        diagnosis_plan: diagnosisPlan,
        execution_outputs: commandEntries,
        skill_matching: {
          matched_skills: skillMatching.matched_skills || [],
          skill_summary: skillMatching.skill_summary || '',
          skills_preview: skillMatching.skills_preview || '',
        },
        email_approval: emailApproval,
        raw_response: data.raw_response,
        saved_to: data.saved_to,
      });
      
      message.success('诊断完成');
    } catch (error) {
      message.error('诊断失败');
    } finally {
      setLoading(false);
    }
  };

  const getCurrentStep = () => {
    if (!currentTask) return -1;
    if (currentTask.status === 'pending') return 0;
    if (currentTask.status === 'needs_confirmation') {
      if (currentTask.email_approval?.email_sent) return 3;
      return 0;
    }
    if (currentTask.status === 'completed') return 4;
    if (currentTask.status === 'failed') return -1;
    return 0;
  };

  const getRiskColor = (risk: string) => {
    const colors: Record<string, string> = { HIGH: 'red', MEDIUM: 'orange', LOW: 'green' };
    return colors[risk] || 'default';
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
    <div>
      <Card title="故障诊断" style={{ marginBottom: 16 }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="描述故障现象，例如：订单服务最近响应很慢，经常超时"
            autoSize={{ minRows: 2, maxRows: 4 }}
            style={{ flex: 1 }}
          />
          <Button 
            type="primary" 
            icon={<SendOutlined />} 
            onClick={handleSubmit}
            loading={loading}
            style={{ height: 'auto' }}
          >
            诊断
          </Button>
        </Space.Compact>
      </Card>

      {currentTask && (
        <Card style={{ marginBottom: 16 }}>
          <Steps
            current={getCurrentStep()}
            status={currentTask.status === 'failed' ? 'error' : 'process'}
            items={[
              { title: '意图识别', description: 'NER + Intent Parsing' },
              { title: 'Skill 匹配', description: 'Skill Manager' },
              { title: '故障诊断', description: 'ReAct Agent (LangGraph)' },
              { title: '人工审批', description: 'Human-in-the-Loop' },
              { title: '结果汇总', description: 'Finalize' },
            ]}
          />
        </Card>
      )}

      {currentTask && currentTask.status === 'completed' && (
        <>
          {currentTask.warning_cleared && (
            <Card style={{ marginBottom: 16, backgroundColor: '#f6ffed', borderColor: '#b7eb8f' }}>
              <div style={{ textAlign: 'center', padding: 20 }}>
                <Title level={3} style={{ color: '#52c41a', marginBottom: 16 }}>✅ 警告已解除</Title>
                <Paragraph style={{ fontSize: 16 }}>
                  {currentTask.decision?.action_plan || '服务器状态检查完成，未发现异常'}
                </Paragraph>
              </div>
            </Card>
          )}
          
          <Collapse defaultActiveKey={['1', '2', '3', '4', '5', '6', '7', '8']}>
            <Panel header="意图识别结果" key="1">
              {currentTask.intent_data && (
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="意图">
                    <Tag color={getIntentColor(currentTask.intent_data.intent)}>
                      {currentTask.intent_data.intent}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="置信度">
                    <Tag color={currentTask.intent_data.confidence === 'HIGH' ? 'green' : 'orange'}>
                      {currentTask.intent_data.confidence}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="服务">{currentTask.intent_data.entities.service}</Descriptions.Item>
                  <Descriptions.Item label="症状">{currentTask.intent_data.entities.symptom}</Descriptions.Item>
                  <Descriptions.Item label="标准化查询">{currentTask.intent_data.normalized_query}</Descriptions.Item>
                </Descriptions>
              )}
            </Panel>

            {currentTask.skill_matching && (
              <Panel header="Skill 匹配结果" key="8">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="匹配到的技能">
                    {currentTask.skill_matching.matched_skills.map((s: string) => (
                      <Tag key={s} color="blue" style={{ marginBottom: 4 }}>{s}</Tag>
                    ))}
                  </Descriptions.Item>
                  <Descriptions.Item label="匹配摘要">{currentTask.skill_matching.skill_summary}</Descriptions.Item>
                </Descriptions>
                {currentTask.skill_matching.skills_preview && (
                  <Paragraph style={{ marginTop: 12, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, backgroundColor: '#f5f5f5', padding: 12, borderRadius: 4, maxHeight: 200, overflow: 'auto' }}>
                    {currentTask.skill_matching.skills_preview}
                  </Paragraph>
                )}
              </Panel>
            )}

            {currentTask.ansible_playbook && (
              <Panel header="生成的 Ansible Playbook" key="6">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="目标主机">{currentTask.ansible_playbook.target_host}</Descriptions.Item>
                  <Descriptions.Item label="症状">{currentTask.ansible_playbook.symptoms?.join(', ')}</Descriptions.Item>
                  <Descriptions.Item label="检查指标">{currentTask.ansible_playbook.metrics?.join(', ')}</Descriptions.Item>
                </Descriptions>
              </Panel>
            )}

            {currentTask.server_status_check && (
              <Panel header="服务器状态检查结果" key="7">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="检查状态">
                    <Tag color={currentTask.server_status_check.success ? 'green' : 'red'}>
                      {currentTask.server_status_check.success ? '成功' : '失败'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="警告状态">
                    <Tag color={currentTask.server_status_check.warning_cleared ? 'green' : 'orange'}>
                      {currentTask.server_status_check.warning_cleared ? '已解除' : '存在异常'}
                    </Tag>
                  </Descriptions.Item>
                  {currentTask.server_status_check.memory_usage !== undefined && (
                    <Descriptions.Item label="内存使用率">
                      <Tag color={currentTask.server_status_check.memory_usage > 80 ? 'red' : currentTask.server_status_check.memory_usage > 60 ? 'orange' : 'green'}>
                        {currentTask.server_status_check.memory_usage}%
                      </Tag>
                    </Descriptions.Item>
                  )}
                  {currentTask.server_status_check.cpu_usage !== undefined && (
                    <Descriptions.Item label="CPU 负载">{currentTask.server_status_check.cpu_usage}</Descriptions.Item>
                  )}
                  {currentTask.server_status_check.disk_usage !== undefined && (
                    <Descriptions.Item label="磁盘使用率">{currentTask.server_status_check.disk_usage}%</Descriptions.Item>
                  )}
                  {currentTask.server_status_check.shm_usage !== undefined && (
                    <Descriptions.Item label="/dev/shm 使用率">
                      <Tag color={currentTask.server_status_check.shm_usage >= 100 ? 'red' : currentTask.server_status_check.shm_usage >= 90 ? 'orange' : 'green'}>
                        {currentTask.server_status_check.shm_usage}%
                      </Tag>
                    </Descriptions.Item>
                  )}
                </Descriptions>
                {currentTask.server_status_check.anomalies && currentTask.server_status_check.anomalies.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <Text strong>发现的异常：</Text>
                    <ul>
                      {currentTask.server_status_check.anomalies.map((anomaly, index) => (
                        <li key={index} style={{ color: '#ff4d4f' }}>{anomaly}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </Panel>
            )}

            {currentTask.mode === 'dynamic' && currentTask.diagnosis_plan && (
              <Panel header={`诊断计划 (${currentTask.iterations} 次迭代)`} key="8">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="计划名称">{currentTask.diagnosis_plan.plan_name}</Descriptions.Item>
                  <Descriptions.Item label="检查类型">
                    <Tag color="blue">{currentTask.diagnosis_plan.check_type}</Tag>
                  </Descriptions.Item>
                </Descriptions>
                <div style={{ marginTop: 16 }}>
                  <Text strong>选择原因：</Text>
                  <Paragraph style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
                    {currentTask.diagnosis_plan.reasoning}
                  </Paragraph>
                </div>
                <div style={{ marginTop: 16 }}>
                  <Text strong>执行命令：</Text>
                  <ul style={{ marginTop: 8 }}>
                    {currentTask.diagnosis_plan.commands.map((cmd, index) => (
                      <li key={index}>
                        <Tag color="geekblue">{cmd}</Tag>
                      </li>
                    ))}
                  </ul>
                </div>
              </Panel>
            )}

            {currentTask.execution_outputs && currentTask.execution_outputs.length > 0 && (
              <Panel header="诊断命令执行结果" key="9">
                {currentTask.execution_outputs.map((exec, index) => (
                  <Card key={index} size="small" style={{ marginBottom: 16 }} title={
                    <Space>
                      <Tag color={exec.success ? 'green' : 'red'}>
                        {exec.success ? '成功' : '失败'}
                      </Tag>
                      <Text code>{exec.command}</Text>
                    </Space>
                  }>
                    <Paragraph style={{ 
                      whiteSpace: 'pre-wrap', 
                      fontFamily: 'monospace',
                      backgroundColor: '#f5f5f5',
                      padding: 12,
                      borderRadius: 4,
                      maxHeight: 300,
                      overflow: 'auto'
                    }}>
                      {exec.output || '无输出'}
                    </Paragraph>
                  </Card>
                ))}
              </Panel>
            )}

            {currentTask.saved_outputs && currentTask.saved_outputs.length > 0 && (
              <Panel header="保存的中间文件" key="10">
                <div>
                  {currentTask.saved_outputs.map((item: any, index: number) => (
                    <div key={index} style={{ padding: '8px 0', borderBottom: index < currentTask.saved_outputs!.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                      <Space>
                        <Tag color="green">已保存</Tag>
                        <Text code>{item.saved_to}</Text>
                        {item.command && <Text type="secondary">({item.command})</Text>}
                      </Space>
                    </div>
                  ))}
                </div>
              </Panel>
            )}

            <Panel header="观测分析报告" key="2">
              {currentTask.analysis_report && (
                <div>
                  {currentTask.analysis_report.diagnosis_plan && (
                    <>
                      <Descriptions column={2} size="small" title="诊断计划">
                        <Descriptions.Item label="计划名称">
                          <Tag color="blue">{currentTask.analysis_report.diagnosis_plan.plan_name}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="检查类型">
                          <Tag>{currentTask.analysis_report.diagnosis_plan.check_type}</Tag>
                        </Descriptions.Item>
                      </Descriptions>
                      <Paragraph style={{ marginTop: 12, whiteSpace: 'pre-wrap' }}>
                        <Text strong>诊断逻辑：</Text>
                        {currentTask.analysis_report.diagnosis_plan.reasoning}
                      </Paragraph>
                    </>
                  )}
                  <Paragraph style={{ marginTop: 12, whiteSpace: 'pre-wrap' }}>
                    {currentTask.analysis_report.analysis_report}
                  </Paragraph>
                </div>
              )}
            </Panel>

            <Panel header="知识库检索" key="3">
              {currentTask.knowledge_context && (
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                  {currentTask.knowledge_context.knowledge_report}
                </Paragraph>
              )}
            </Panel>

            <Panel header="决策结果" key="4">
              {currentTask.decision && (
                <div>
                  {currentTask.decision.is_final ? (
                    <>
                      <Descriptions column={2} size="small">
                        <Descriptions.Item label="问题类型">
                          <Tag color="blue">{currentTask.decision.problem_type}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="风险等级">
                          <Tag color={getRiskColor(currentTask.decision.risk_level)}>
                            {currentTask.decision.risk_level}
                          </Tag>
                        </Descriptions.Item>
                      </Descriptions>
                      <Paragraph style={{ marginTop: 16 }}>
                        <Text strong>根本原因：</Text>{currentTask.decision.root_cause}
                      </Paragraph>
                      <Paragraph>
                        <Text strong>影响范围：</Text>{currentTask.decision.impact}
                      </Paragraph>
                      <Paragraph>
                        <Text strong>建议操作：</Text>{currentTask.decision.recommendation}
                      </Paragraph>
                    </>
                  ) : (
                    <>
                      <Descriptions column={2} size="small">
                        <Descriptions.Item label="根因">{currentTask.decision.root_cause_summary}</Descriptions.Item>
                        <Descriptions.Item label="决策">
                          <Tag color={currentTask.decision.decision === 'EXECUTE_FIX' ? 'orange' : 'blue'}>
                            {currentTask.decision.decision}
                          </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="风险等级">
                          <Tag color={getRiskColor(currentTask.decision.risk_level)}>
                            {currentTask.decision.risk_level}
                          </Tag>
                        </Descriptions.Item>
                      </Descriptions>
                      <Paragraph style={{ marginTop: 16, whiteSpace: 'pre-wrap' }}>
                        <Text strong>执行计划：</Text>{'\n'}{currentTask.decision.action_plan}
                      </Paragraph>
                      <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                        <Text strong>推理过程：</Text>{'\n'}{currentTask.decision.reasoning}
                      </Paragraph>
                    </>
                  )}
                </div>
              )}
            </Panel>

            {currentTask.action_result && (
              <Panel header="执行指令" key="5">
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="工具">{currentTask.action_result.tool_name}</Descriptions.Item>
                  <Descriptions.Item label="模板">{currentTask.action_result.template_name}</Descriptions.Item>
                  <Descriptions.Item label="风险评估">
                    <Tag color={getRiskColor(currentTask.action_result.risk_assessment)}>
                      {currentTask.action_result.risk_assessment}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="需要审批">
                    <Tag color={currentTask.action_result.requires_approval ? 'red' : 'green'}>
                      {currentTask.action_result.requires_approval ? '是' : '否'}
                    </Tag>
                  </Descriptions.Item>
                </Descriptions>
                <Paragraph style={{ marginTop: 16 }}>
                  <Text strong>执行说明：</Text>{currentTask.action_result.execution_note}
                </Paragraph>
              </Panel>
            )}
          </Collapse>
        </>
      )}

      {currentTask && currentTask.status === 'needs_confirmation' && (
        <Card style={{ marginBottom: 16, backgroundColor: '#fffbe6', borderColor: '#ffe58f' }}>
          {currentTask.email_approval?.email_sent ? (
            <div style={{ padding: 20, textAlign: 'center' }}>
              <Title level={4} style={{ color: '#d48806', marginBottom: 16 }}>✉️ 审批邮件已发送</Title>
              <Descriptions column={1} size="small" style={{ textAlign: 'left' }}>
                <Descriptions.Item label="收件人">{currentTask.email_approval.to_email}</Descriptions.Item>
                <Descriptions.Item label="审批 ID">
                  <Tag color="blue">{currentTask.email_approval.approval_id}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="操作内容">{currentTask.email_approval.operation}</Descriptions.Item>
                <Descriptions.Item label="风险等级">
                  <Tag color="orange">{currentTask.email_approval.risk}</Tag>
                </Descriptions.Item>
              </Descriptions>
              <Paragraph style={{ marginTop: 16, color: '#666' }}>
                请检查邮箱并回复邮件进行确认。回复含 <Tag>APPROVE</Tag> 或 <Tag>批准</Tag> 即批准执行。
              </Paragraph>
              <Paragraph style={{ marginTop: 8, color: '#999', fontSize: 12 }}>
                审批通过后，系统将自动执行已批准的命令并更新诊断结果。当前状态：{currentTask.email_approval.status}
              </Paragraph>
            </div>
          ) : currentTask.decision?.confirmation_request ? (
            <div style={{ padding: 20 }}>
              <Title level={4} style={{ color: '#d48806', marginBottom: 16 }}>⚠️ 需要用户确认</Title>
              <Paragraph style={{ fontSize: 16, marginBottom: 16 }}>
                <Text strong>操作：</Text>{currentTask.decision.confirmation_request.operation}
              </Paragraph>
              <Paragraph style={{ marginBottom: 8 }}>
                <Text strong>风险：</Text>
                <Tag color="orange">{currentTask.decision.confirmation_request.risk}</Tag>
              </Paragraph>
              <Paragraph style={{ marginBottom: 8 }}>
                <Text strong>影响：</Text>{currentTask.decision.confirmation_request.impact}
              </Paragraph>
              <Paragraph style={{ marginTop: 16, color: '#666' }}>
                {currentTask.decision.confirmation_request.message}
              </Paragraph>
            </div>
          ) : (
            <div style={{ padding: 20, textAlign: 'center' }}>
              <Spin size="default" />
              <Paragraph style={{ marginTop: 16 }}>等待处理中...</Paragraph>
            </div>
          )}
        </Card>
      )}

      {currentTask && currentTask.status === 'processing' && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <Paragraph style={{ marginTop: 16 }}>正在分析中，请稍候...</Paragraph>
        </Card>
      )}

    </div>
  );
};

export default Diagnose;
