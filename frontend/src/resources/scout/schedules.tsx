import React, { useState } from 'react';
import { useCustomMutation, useInvalidate } from '@refinedev/core';
import { List, useTable as useAntdTable, DateField } from '@refinedev/antd';
import { Table, Space, Tag, Button, Switch, Typography, Modal, message, Tooltip } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  StopOutlined,
} from '@ant-design/icons';
import type { ScoutSchedule, ScoutSource, CreateScoutSchedulePayload, UpdateScoutSchedulePayload } from '@providers/types';
import { ScheduleModal } from './ScheduleModal';

const { Text } = Typography;

/**
 * Source display labels
 */
const SOURCE_LABELS: Record<ScoutSource, string> = {
  stratninja: 'StratNinja',
  github: 'GitHub',
  freqai_gym: 'FreqAI Gym',
};

/**
 * Source tag colors
 */
const SOURCE_COLORS: Record<ScoutSource, string> = {
  stratninja: 'blue',
  github: 'purple',
  freqai_gym: 'green',
};

/**
 * Get human-readable description for a cron expression
 */
const getCronDescription = (cron: string): string => {
  // Map common cron patterns to readable descriptions
  const cronMap: Record<string, string> = {
    '0 * * * *': 'Every hour',
    '0 */2 * * *': 'Every 2 hours',
    '0 */6 * * *': 'Every 6 hours',
    '0 2 * * *': 'Daily at 2:00 AM',
    '0 8 * * *': 'Daily at 8:00 AM',
    '0 9 * * 1': 'Every Monday at 9:00 AM',
    '0 9 * * 1-5': 'Every weekday at 9:00 AM',
  };

  if (cronMap[cron]) {
    return cronMap[cron];
  }

  // Try to parse simple patterns
  const parts = cron.split(' ');
  if (parts.length === 5) {
    const [minute, hour, day, month, weekday] = parts;

    if (hour === '*' && minute === '0') {
      return 'Every hour';
    }
    if (hour.startsWith('*/') && minute === '0') {
      const interval = hour.split('/')[1];
      return `Every ${interval} hours`;
    }
    if (day === '*' && month === '*' && weekday === '*' && hour !== '*') {
      return `Daily at ${hour}:${minute.padStart(2, '0')}`;
    }
  }

  return cron; // Fallback to showing the cron expression itself
};

/**
 * ScoutScheduleList Component
 *
 * Displays and manages Scout scheduling configurations with:
 * - List of all schedules with key information
 * - Toggle enable/disable status inline
 * - Create, edit, and delete operations
 * - Human-readable cron descriptions
 * - Next/last run time displays
 */
export const ScoutScheduleList: React.FC = () => {
  const [modalVisible, setModalVisible] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [selectedSchedule, setSelectedSchedule] = useState<ScoutSchedule | undefined>();

  const invalidate = useInvalidate();

  const { tableProps } = useAntdTable<ScoutSchedule>({
    resource: 'scout-schedules',
    syncWithLocation: true,
  });

  // Create schedule mutation
  const { mutate: createSchedule, isLoading: isCreating } = useCustomMutation<ScoutSchedule>();

  // Update schedule mutation
  const { mutate: updateSchedule, isLoading: isUpdating } = useCustomMutation<ScoutSchedule>();

  // Delete schedule mutation
  const { mutate: deleteSchedule, isLoading: isDeleting } = useCustomMutation();

  // Toggle schedule enabled status
  const { mutate: toggleSchedule, isLoading: isToggling } = useCustomMutation();

  // Handle create button click
  const handleCreate = () => {
    setModalMode('create');
    setSelectedSchedule(undefined);
    setModalVisible(true);
  };

  // Handle edit button click
  const handleEdit = (schedule: ScoutSchedule) => {
    setModalMode('edit');
    setSelectedSchedule(schedule);
    setModalVisible(true);
  };

  // Handle delete button click
  const handleDelete = (schedule: ScoutSchedule) => {
    Modal.confirm({
      title: 'Delete Schedule',
      content: `Are you sure you want to delete the schedule "${schedule.name}"? This action cannot be undone.`,
      okText: 'Delete',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: () => {
        deleteSchedule(
          {
            url: `/agents/scout/schedules/${schedule.id}`,
            method: 'delete',
            values: {},
          },
          {
            onSuccess: () => {
              message.success('Schedule deleted successfully');
              invalidate({
                resource: 'scout-schedules',
                invalidates: ['list'],
              });
            },
            onError: (error: any) => {
              message.error(`Failed to delete schedule: ${error.message}`);
            },
          }
        );
      },
    });
  };

  // Handle toggle enabled status
  const handleToggle = (schedule: ScoutSchedule, checked: boolean) => {
    toggleSchedule(
      {
        url: `/agents/scout/schedules/${schedule.id}/toggle`,
        method: 'post',
        values: { enabled: checked },
      },
      {
        onSuccess: () => {
          message.success(`Schedule ${checked ? 'enabled' : 'disabled'} successfully`);
          invalidate({
            resource: 'scout-schedules',
            invalidates: ['list'],
          });
        },
        onError: (error: any) => {
          message.error(`Failed to toggle schedule: ${error.message}`);
        },
      }
    );
  };

  // Handle modal submit
  const handleModalSubmit = (values: CreateScoutSchedulePayload | UpdateScoutSchedulePayload) => {
    if (modalMode === 'create') {
      createSchedule(
        {
          url: '/agents/scout/schedules',
          method: 'post',
          values,
        },
        {
          onSuccess: () => {
            message.success('Schedule created successfully');
            setModalVisible(false);
            invalidate({
              resource: 'scout-schedules',
              invalidates: ['list'],
            });
          },
          onError: (error: any) => {
            message.error(`Failed to create schedule: ${error.message}`);
          },
        }
      );
    } else if (modalMode === 'edit' && selectedSchedule) {
      updateSchedule(
        {
          url: `/agents/scout/schedules/${selectedSchedule.id}`,
          method: 'put',
          values,
        },
        {
          onSuccess: () => {
            message.success('Schedule updated successfully');
            setModalVisible(false);
            invalidate({
              resource: 'scout-schedules',
              invalidates: ['list'],
            });
          },
          onError: (error: any) => {
            message.error(`Failed to update schedule: ${error.message}`);
          },
        }
      );
    }
  };

  return (
    <>
      <List
        headerButtons={({ defaultButtons }) => (
          <>
            {defaultButtons}
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              Create Schedule
            </Button>
          </>
        )}
      >
        <Table<ScoutSchedule>
          {...tableProps}
          rowKey="id"
          pagination={{
            ...tableProps.pagination,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} schedules`,
          }}
        >
          {/* Name Column */}
          <Table.Column
            dataIndex="name"
            title="Name"
            width={200}
            render={(value: string) => <Text strong>{value}</Text>}
            sorter
          />

          {/* Cron Expression Column */}
          <Table.Column
            dataIndex="cron_expression"
            title="Schedule"
            width={200}
            render={(value: string) => (
              <Space direction="vertical" size={0}>
                <Tooltip title={`Cron: ${value}`}>
                  <Text>
                    <ClockCircleOutlined /> {getCronDescription(value)}
                  </Text>
                </Tooltip>
                <Text type="secondary" code style={{ fontSize: 11 }}>
                  {value}
                </Text>
              </Space>
            )}
          />

          {/* Source Column */}
          <Table.Column
            dataIndex="source"
            title="Source"
            width={120}
            render={(value: ScoutSource) => (
              <Tag color={SOURCE_COLORS[value]}>
                {SOURCE_LABELS[value]}
              </Tag>
            )}
            filters={[
              { text: 'StratNinja', value: 'stratninja' },
              { text: 'GitHub', value: 'github' },
              { text: 'FreqAI Gym', value: 'freqai_gym' },
            ]}
          />

          {/* Max Strategies Column */}
          <Table.Column
            dataIndex="max_strategies"
            title="Max Strategies"
            width={130}
            align="center"
            render={(value: number) => <Tag color="blue">{value}</Tag>}
            sorter
          />

          {/* Enabled Status Column */}
          <Table.Column
            dataIndex="enabled"
            title="Enabled"
            width={100}
            align="center"
            render={(value: boolean, record: ScoutSchedule) => (
              <Tooltip title={value ? 'Click to disable' : 'Click to enable'}>
                <Switch
                  checked={value}
                  checkedChildren={<CheckCircleOutlined />}
                  unCheckedChildren={<StopOutlined />}
                  onChange={(checked) => handleToggle(record, checked)}
                  loading={isToggling}
                />
              </Tooltip>
            )}
            filters={[
              { text: 'Enabled', value: true },
              { text: 'Disabled', value: false },
            ]}
          />

          {/* Last Run Column */}
          <Table.Column
            dataIndex="last_run_at"
            title="Last Run"
            width={160}
            render={(value?: string) =>
              value ? (
                <DateField value={value} format="YYYY-MM-DD HH:mm:ss" />
              ) : (
                <Text type="secondary">Never</Text>
              )
            }
            sorter
          />

          {/* Next Run Column */}
          <Table.Column
            dataIndex="next_run_at"
            title="Next Run"
            width={160}
            render={(value?: string) =>
              value ? (
                <DateField value={value} format="YYYY-MM-DD HH:mm:ss" />
              ) : (
                <Text type="secondary">-</Text>
              )
            }
            sorter
          />

          {/* Actions Column */}
          <Table.Column
            title="Actions"
            fixed="right"
            width={150}
            render={(_, record: ScoutSchedule) => (
              <Space size="small">
                <Tooltip title="Edit schedule">
                  <Button
                    type="link"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => handleEdit(record)}
                  >
                    Edit
                  </Button>
                </Tooltip>
                <Tooltip title="Delete schedule">
                  <Button
                    type="link"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleDelete(record)}
                    loading={isDeleting}
                  >
                    Delete
                  </Button>
                </Tooltip>
              </Space>
            )}
          />
        </Table>
      </List>

      {/* Create/Edit Modal */}
      <ScheduleModal
        visible={modalVisible}
        mode={modalMode}
        schedule={selectedSchedule}
        loading={isCreating || isUpdating}
        onSubmit={handleModalSubmit}
        onCancel={() => setModalVisible(false)}
      />
    </>
  );
};
