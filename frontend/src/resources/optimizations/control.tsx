import { useState } from 'react';
import { useCustomMutation, useInvalidate } from '@refinedev/core';
import { Button, Modal, Space, Tooltip, message } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { OptimizationStatus, OptimizationAction, ControlOptimizationPayload } from '@providers/types';

interface OptimizationControlPanelProps {
  optimizationId: string;
  currentStatus: OptimizationStatus;
  size?: 'small' | 'middle' | 'large';
  showLabels?: boolean;
  onSuccess?: () => void;
}

export const OptimizationControlPanel: React.FC<OptimizationControlPanelProps> = ({
  optimizationId,
  currentStatus,
  size = 'middle',
  showLabels = false,
  onSuccess,
}) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [pendingAction, setPendingAction] = useState<OptimizationAction | null>(null);
  const invalidate = useInvalidate();

  const { mutate: controlOptimization, isLoading } = useCustomMutation();

  const handleControl = (action: OptimizationAction) => {
    setPendingAction(action);
    setModalVisible(true);
  };

  const confirmAction = () => {
    if (!pendingAction) return;

    const payload: ControlOptimizationPayload = {
      action: pendingAction,
    };

    controlOptimization(
      {
        url: `optimizations/${optimizationId}/control`,
        method: 'post',
        values: payload,
      },
      {
        onSuccess: () => {
          const actionText = pendingAction.replace('OPTIMIZATION_ACTION_', '').toLowerCase();
          message.success(`Optimization ${actionText}d successfully`);
          setModalVisible(false);
          setPendingAction(null);
          invalidate({
            resource: 'optimizations',
            invalidates: ['list', 'detail'],
            id: optimizationId,
          });
          if (onSuccess) onSuccess();
        },
        onError: (error: any) => {
          message.error(`Failed to control optimization: ${error.message}`);
        },
      }
    );
  };

  const getActionText = (action: OptimizationAction): string => {
    switch (action) {
      case 'OPTIMIZATION_ACTION_PAUSE':
        return 'pause';
      case 'OPTIMIZATION_ACTION_RESUME':
        return 'resume';
      case 'OPTIMIZATION_ACTION_CANCEL':
        return 'cancel';
      default:
        return 'perform action on';
    }
  };

  const canPause = currentStatus === 'OPTIMIZATION_STATUS_RUNNING';
  const canResume = currentStatus === 'OPTIMIZATION_STATUS_PAUSED';
  const canCancel =
    currentStatus === 'OPTIMIZATION_STATUS_RUNNING' ||
    currentStatus === 'OPTIMIZATION_STATUS_PAUSED' ||
    currentStatus === 'OPTIMIZATION_STATUS_PENDING';

  return (
    <>
      <Space size="small">
        {canPause && (
          <Tooltip title="Pause optimization">
            <Button
              type={showLabels ? 'default' : 'text'}
              icon={<PauseCircleOutlined />}
              size={size}
              onClick={() => handleControl('OPTIMIZATION_ACTION_PAUSE')}
              loading={isLoading}
            >
              {showLabels && 'Pause'}
            </Button>
          </Tooltip>
        )}
        {canResume && (
          <Tooltip title="Resume optimization">
            <Button
              type={showLabels ? 'primary' : 'text'}
              icon={<PlayCircleOutlined />}
              size={size}
              onClick={() => handleControl('OPTIMIZATION_ACTION_RESUME')}
              loading={isLoading}
            >
              {showLabels && 'Resume'}
            </Button>
          </Tooltip>
        )}
        {canCancel && (
          <Tooltip title="Cancel optimization">
            <Button
              type={showLabels ? 'default' : 'text'}
              danger
              icon={<CloseCircleOutlined />}
              size={size}
              onClick={() => handleControl('OPTIMIZATION_ACTION_CANCEL')}
              loading={isLoading}
            >
              {showLabels && 'Cancel'}
            </Button>
          </Tooltip>
        )}
      </Space>

      <Modal
        title="Confirm Action"
        open={modalVisible}
        onOk={confirmAction}
        onCancel={() => {
          setModalVisible(false);
          setPendingAction(null);
        }}
        confirmLoading={isLoading}
        okText="Confirm"
        cancelText="Cancel"
      >
        <p>
          Are you sure you want to <strong>{pendingAction && getActionText(pendingAction)}</strong> this
          optimization run?
        </p>
        {pendingAction === 'OPTIMIZATION_ACTION_CANCEL' && (
          <p style={{ color: '#ff4d4f' }}>
            This action cannot be undone. All progress will be stopped and the optimization will be marked as
            cancelled.
          </p>
        )}
      </Modal>
    </>
  );
};
