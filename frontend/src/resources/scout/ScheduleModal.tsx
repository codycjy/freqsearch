import React, { useEffect } from 'react';
import { Modal, Form, Input, Select, InputNumber, Switch, Space, Alert, Typography } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';
import type { ScoutSchedule, ScoutSource, CreateScoutSchedulePayload, UpdateScoutSchedulePayload } from '@providers/types';

const { Text } = Typography;

interface ScheduleModalProps {
  visible: boolean;
  mode: 'create' | 'edit';
  schedule?: ScoutSchedule;
  loading?: boolean;
  onSubmit: (values: CreateScoutSchedulePayload | UpdateScoutSchedulePayload) => void;
  onCancel: () => void;
}

/**
 * Common cron expression presets with human-readable descriptions
 */
const CRON_PRESETS = [
  { label: 'Every hour', value: '0 * * * *', description: 'Runs at the start of every hour' },
  { label: 'Every 2 hours', value: '0 */2 * * *', description: 'Runs every 2 hours' },
  { label: 'Every 6 hours', value: '0 */6 * * *', description: 'Runs every 6 hours' },
  { label: 'Daily at 2:00 AM', value: '0 2 * * *', description: 'Runs once per day at 2:00 AM' },
  { label: 'Daily at 8:00 AM', value: '0 8 * * *', description: 'Runs once per day at 8:00 AM' },
  { label: 'Every Monday at 9:00 AM', value: '0 9 * * 1', description: 'Runs every Monday at 9:00 AM' },
  { label: 'Every weekday at 9:00 AM', value: '0 9 * * 1-5', description: 'Runs Monday-Friday at 9:00 AM' },
  { label: 'Custom', value: 'custom', description: 'Enter your own cron expression' },
];

/**
 * Data source options
 */
const SOURCE_OPTIONS: Array<{ label: string; value: ScoutSource; description: string }> = [
  {
    label: 'StratNinja',
    value: 'stratninja',
    description: 'Import strategies from StratNinja marketplace'
  },
  {
    label: 'GitHub',
    value: 'github',
    description: 'Search and import strategies from GitHub repositories'
  },
  {
    label: 'FreqAI Gym',
    value: 'freqai_gym',
    description: 'Import strategies from FreqAI Gym collection'
  },
];

/**
 * Get human-readable description for a cron expression
 */
const getCronDescription = (cron: string): string => {
  const preset = CRON_PRESETS.find(p => p.value === cron);
  if (preset) {
    return preset.description;
  }

  // Simple cron pattern descriptions
  const parts = cron.split(' ');
  if (parts.length === 5) {
    const [minute, hour, day, month, weekday] = parts;

    if (hour === '*' && minute === '0') {
      return 'Runs at the start of every hour';
    }
    if (hour.startsWith('*/') && minute === '0') {
      const interval = hour.split('/')[1];
      return `Runs every ${interval} hours`;
    }
    if (day === '*' && month === '*' && weekday === '*' && hour !== '*') {
      return `Runs daily at ${hour}:${minute.padStart(2, '0')}`;
    }
  }

  return 'Custom schedule';
};

/**
 * ScheduleModal Component
 *
 * Modal for creating or editing Scout schedule configurations
 * Supports:
 * - Cron expression presets and custom input
 * - Data source selection
 * - Max strategies limit
 * - Enable/disable toggle
 */
export const ScheduleModal: React.FC<ScheduleModalProps> = ({
  visible,
  mode,
  schedule,
  loading = false,
  onSubmit,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const [showCustomCron, setShowCustomCron] = React.useState(false);
  const [selectedSource, setSelectedSource] = React.useState<ScoutSource>('stratninja');

  // Initialize form when schedule changes (for edit mode)
  useEffect(() => {
    if (visible && schedule && mode === 'edit') {
      const preset = CRON_PRESETS.find(p => p.value === schedule.cron_expression);
      if (preset && preset.value !== 'custom') {
        setShowCustomCron(false);
      } else {
        setShowCustomCron(true);
      }
      setSelectedSource(schedule.source);

      form.setFieldsValue({
        name: schedule.name,
        cron_preset: preset ? preset.value : 'custom',
        cron_expression: schedule.cron_expression,
        source: schedule.source,
        max_strategies: schedule.max_strategies,
        enabled: schedule.enabled,
      });
    } else if (visible && mode === 'create') {
      // Reset to defaults for create mode
      form.resetFields();
      setShowCustomCron(false);
      setSelectedSource('stratninja');
    }
  }, [visible, schedule, mode, form]);

  const handleCronPresetChange = (value: string) => {
    if (value === 'custom') {
      setShowCustomCron(true);
      form.setFieldValue('cron_expression', '');
    } else {
      setShowCustomCron(false);
      form.setFieldValue('cron_expression', value);
    }
  };

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      const payload: CreateScoutSchedulePayload | UpdateScoutSchedulePayload = {
        name: values.name,
        cron_expression: values.cron_expression,
        source: values.source,
        max_strategies: values.max_strategies || 100,
        enabled: values.enabled !== undefined ? values.enabled : true,
      };

      onSubmit(payload);
    });
  };

  const handleCancel = () => {
    form.resetFields();
    onCancel();
  };

  const currentCronExpression = Form.useWatch('cron_expression', form);

  return (
    <Modal
      title={mode === 'create' ? 'Create Scout Schedule' : 'Edit Scout Schedule'}
      open={visible}
      onOk={handleSubmit}
      onCancel={handleCancel}
      confirmLoading={loading}
      okText={mode === 'create' ? 'Create' : 'Update'}
      cancelText="Cancel"
      width={600}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          max_strategies: 100,
          enabled: true,
          cron_preset: '0 * * * *',
          cron_expression: '0 * * * *',
          source: 'stratninja',
        }}
      >
        {/* Info Alert */}
        <Alert
          message={mode === 'create' ? 'Create New Schedule' : 'Update Schedule'}
          description="Configure when and how the Scout agent should search for new trading strategies."
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />

        {/* Schedule Name */}
        <Form.Item
          name="name"
          label="Schedule Name"
          rules={[
            { required: true, message: 'Please enter a schedule name' },
            { min: 3, message: 'Name must be at least 3 characters' },
            { max: 100, message: 'Name must not exceed 100 characters' },
          ]}
          extra="A descriptive name for this schedule"
        >
          <Input placeholder="e.g., Hourly StratNinja Scout" />
        </Form.Item>

        {/* Cron Preset Selection */}
        <Form.Item
          name="cron_preset"
          label="Schedule Frequency"
          extra={
            <Space direction="vertical" size={0}>
              <Text type="secondary">
                <ClockCircleOutlined /> {currentCronExpression ? getCronDescription(currentCronExpression) : 'Select a frequency'}
              </Text>
            </Space>
          }
        >
          <Select
            placeholder="Select frequency"
            onChange={handleCronPresetChange}
            options={CRON_PRESETS.map(preset => ({
              label: preset.label,
              value: preset.value,
            }))}
          />
        </Form.Item>

        {/* Custom Cron Expression */}
        {showCustomCron && (
          <Form.Item
            name="cron_expression"
            label="Custom Cron Expression"
            rules={[
              { required: true, message: 'Please enter a cron expression' },
              {
                pattern: /^(\*|([0-5]?\d)) (\*|([01]?\d|2[0-3])) (\*|([01]?\d|2\d|3[01])) (\*|([1-9]|1[0-2])) (\*|([0-6]))$/,
                message: 'Invalid cron expression format (minute hour day month weekday)',
              },
            ]}
            extra="Format: minute hour day month weekday (e.g., 0 */2 * * * for every 2 hours)"
          >
            <Input placeholder="0 * * * *" />
          </Form.Item>
        )}

        {/* Hidden field to store actual cron expression */}
        {!showCustomCron && (
          <Form.Item name="cron_expression" hidden>
            <Input />
          </Form.Item>
        )}

        {/* Data Source */}
        <Form.Item
          name="source"
          label="Data Source"
          rules={[{ required: true, message: 'Please select a data source' }]}
          extra={SOURCE_OPTIONS.find(s => s.value === selectedSource)?.description}
        >
          <Select
            placeholder="Select data source"
            onChange={(value) => setSelectedSource(value as ScoutSource)}
            options={SOURCE_OPTIONS.map(source => ({
              label: source.label,
              value: source.value,
            }))}
          />
        </Form.Item>

        {/* Max Strategies */}
        <Form.Item
          name="max_strategies"
          label="Max Strategies"
          rules={[
            { required: true, message: 'Please enter max strategies' },
            { type: 'number', min: 1, message: 'Must be at least 1' },
            { type: 'number', max: 1000, message: 'Must not exceed 1000' },
          ]}
          extra="Maximum number of strategies to fetch per run"
        >
          <InputNumber
            style={{ width: '100%' }}
            min={1}
            max={1000}
            placeholder="100"
          />
        </Form.Item>

        {/* Enabled Toggle */}
        <Form.Item
          name="enabled"
          label="Enabled"
          valuePropName="checked"
          extra="Enable or disable this schedule"
        >
          <Switch checkedChildren="Enabled" unCheckedChildren="Disabled" />
        </Form.Item>
      </Form>
    </Modal>
  );
};
