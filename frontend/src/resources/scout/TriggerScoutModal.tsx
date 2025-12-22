import React from 'react';
import { useCustomMutation, useInvalidate } from '@refinedev/core';
import { Modal, Form, Select, InputNumber, Alert, message } from 'antd';
import { RocketOutlined } from '@ant-design/icons';

/**
 * TriggerScoutModal Component Props
 */
interface TriggerScoutModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

/**
 * Payload for triggering Scout agent
 */
interface TriggerScoutPayload {
  source: string;
  max_strategies?: number;
  trigger_type?: string;
  triggered_by?: string;
}

/**
 * Available data sources for Scout
 */
const DATA_SOURCES = [
  { label: 'StratNinja', value: 'stratninja' },
  { label: 'GitHub', value: 'github' },
  { label: 'FreqAI Gym', value: 'freqai_gym' },
];

/**
 * TriggerScoutModal Component
 *
 * Modal dialog for manually triggering Scout agent to fetch strategies from external sources.
 *
 * Features:
 * - Source selection (stratninja, github, freqai_gym)
 * - Optional max_strategies limit (1-500, default 100)
 * - Form validation
 * - Success/error notifications
 * - Auto-refresh on success
 *
 * Usage:
 * ```tsx
 * <TriggerScoutModal
 *   open={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   onSuccess={() => {
 *     // Optional: Additional actions after success
 *   }}
 * />
 * ```
 */
export const TriggerScoutModal: React.FC<TriggerScoutModalProps> = ({
  open,
  onClose,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const invalidate = useInvalidate();

  const { mutate: triggerScout, isLoading } = useCustomMutation<TriggerScoutPayload>();

  /**
   * Handle form submission
   */
  const handleSubmit = (values: TriggerScoutPayload) => {
    const payload: TriggerScoutPayload = {
      source: values.source,
      trigger_type: 'manual',
      triggered_by: 'user',
    };

    // Only include max_strategies if provided
    if (values.max_strategies !== undefined && values.max_strategies !== null) {
      payload.max_strategies = values.max_strategies;
    }

    triggerScout(
      {
        url: '/agents/scout/trigger',
        method: 'post',
        values: payload,
      },
      {
        onSuccess: () => {
          message.success(`Scout agent triggered successfully for source: ${values.source}`);
          form.resetFields();
          onClose();

          // Invalidate relevant resources to refresh lists
          invalidate({
            resource: 'strategies',
            invalidates: ['list'],
          });

          if (onSuccess) {
            onSuccess();
          }
        },
        onError: (error: any) => {
          const errorMessage = error?.message || 'Failed to trigger Scout agent';
          message.error(errorMessage);
        },
      }
    );
  };

  /**
   * Handle modal close
   */
  const handleCancel = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title={
        <span>
          <RocketOutlined style={{ marginRight: 8 }} />
          Trigger Scout Agent
        </span>
      }
      open={open}
      onOk={() => form.submit()}
      onCancel={handleCancel}
      confirmLoading={isLoading}
      okText="Trigger Scout"
      cancelText="Cancel"
      width={500}
      destroyOnClose
    >
      <Alert
        message="Manual Scout Trigger"
        description="Trigger the Scout agent to fetch and import new strategies from external sources. The agent will run asynchronously."
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          max_strategies: 100,
        }}
      >
        <Form.Item
          name="source"
          label="Data Source"
          rules={[
            {
              required: true,
              message: 'Please select a data source',
            },
          ]}
          extra="Choose the external source to fetch strategies from"
        >
          <Select
            placeholder="Select a data source"
            options={DATA_SOURCES}
            size="large"
          />
        </Form.Item>

        <Form.Item
          name="max_strategies"
          label="Max Strategies"
          rules={[
            {
              type: 'number',
              min: 1,
              max: 500,
              message: 'Must be between 1 and 500',
            },
          ]}
          extra="Maximum number of strategies to fetch (1-500)"
        >
          <InputNumber
            placeholder="100"
            style={{ width: '100%' }}
            min={1}
            max={500}
            size="large"
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};
