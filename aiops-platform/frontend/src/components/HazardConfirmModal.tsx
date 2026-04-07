import { useState } from 'react';
import { Modal, Input, Typography, Space, Alert } from 'antd';
import { ExclamationCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface HazardConfirmModalProps {
  open: boolean;
  title?: string;
  operationName: string;
  description?: string;
  requireInput?: boolean;
  inputPlaceholder?: string;
  expectedInput?: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

const HazardConfirmModal: React.FC<HazardConfirmModalProps> = ({
  open,
  title = '高危操作确认',
  operationName,
  description,
  requireInput = false,
  inputPlaceholder = '请输入确认信息',
  expectedInput,
  onConfirm,
  onCancel,
  loading = false,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [error, setError] = useState('');

  const handleConfirm = () => {
    if (requireInput && expectedInput) {
      if (inputValue !== expectedInput) {
        setError('输入内容不正确');
        return;
      }
    }
    onConfirm();
    setInputValue('');
    setError('');
  };

  const handleCancel = () => {
    setInputValue('');
    setError('');
    onCancel();
  };

  return (
    <Modal
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#faad14' }} />
          <span>{title}</span>
        </Space>
      }
      open={open}
      onOk={handleConfirm}
      onCancel={handleCancel}
      okText="确认执行"
      cancelText="取消"
      okButtonProps={{ 
        danger: true, 
        loading,
        disabled: requireInput && !inputValue
      }}
      width={480}
    >
      <Alert
        message="警告：此操作具有高风险"
        description={
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>
              您正在尝试执行 <Text strong type="danger">{operationName}</Text>
            </Text>
            {description && <Text type="secondary">{description}</Text>}
            <Text type="danger">该操作不可逆，请确认后继续</Text>
          </Space>
        }
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
      />
      
      {requireInput && (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>请输入 <Text code>{expectedInput}</Text> 以确认操作：</Text>
          <Input
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setError('');
            }}
            placeholder={inputPlaceholder}
            status={error ? 'error' : undefined}
          />
          {error && <Text type="danger">{error}</Text>}
        </Space>
      )}
    </Modal>
  );
};

export default HazardConfirmModal;
