import React, { useState, useEffect } from 'react';
import { Edit, useForm, useSelect } from '@refinedev/antd';
import { Form, Input, Select, Alert } from 'antd';
import { useCustom } from '@refinedev/core';
import type { Strategy, CreateStrategyPayload } from '@providers/types';

const { TextArea } = Input;

/**
 * StrategyEdit Component
 *
 * Form to edit an existing strategy:
 * - Pre-populated with current strategy data
 * - Same fields as create (name, description, code, parent)
 * - Shows warning if strategy has existing backtests
 * - Code validation before submit
 *
 * Uses Refine's useForm hook with Ant Design Form
 */
export const StrategyEdit: React.FC = () => {
  const { formProps, saveButtonProps, queryResult } = useForm<Strategy, any, CreateStrategyPayload>({
    resource: 'strategies',
    redirect: 'show',
  });

  const [codeError, setCodeError] = useState<string | null>(null);
  const strategy = queryResult?.data?.data;

  // Check if strategy has backtests
  const { data: backtestsData } = useCustom({
    url: `backtests`,
    method: 'get',
    config: {
      query: {
        strategy_id: strategy?.id,
        limit: 1,
      },
    },
    queryOptions: {
      enabled: !!strategy?.id,
    },
  });

  const hasBacktests = backtestsData?.data?.data?.length > 0;

  // Load parent strategies for dropdown
  const { selectProps: parentSelectProps } = useSelect<Strategy>({
    resource: 'strategies',
    optionLabel: 'name',
    optionValue: 'id',
    defaultValue: strategy?.parent_id,
  });

  // Validate Python code syntax (basic validation)
  const validateCode = (code: string): boolean => {
    if (!code || code.trim().length === 0) {
      setCodeError('Code is required');
      return false;
    }

    // Basic Python syntax checks
    if (!code.includes('class') || !code.includes('IStrategy')) {
      setCodeError('Code must define a class that inherits from IStrategy');
      return false;
    }

    if (!code.includes('def populate_indicators')) {
      setCodeError('Code must implement populate_indicators method');
      return false;
    }

    if (!code.includes('def populate_entry_trend')) {
      setCodeError('Code must implement populate_entry_trend method');
      return false;
    }

    if (!code.includes('def populate_exit_trend')) {
      setCodeError('Code must implement populate_exit_trend method');
      return false;
    }

    setCodeError(null);
    return true;
  };

  const handleCodeChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const code = e.target.value;
    if (code && code.length > 50) {
      validateCode(code);
    }
  };

  // Set initial form values
  useEffect(() => {
    if (strategy) {
      formProps.form?.setFieldsValue({
        name: strategy.name,
        description: strategy.description,
        code: strategy.code,
        parent_id: strategy.parent_id,
      });
    }
  }, [strategy, formProps.form]);

  return (
    <Edit
      saveButtonProps={{
        ...saveButtonProps,
        onClick: () => {
          const code = formProps?.form?.getFieldValue('code');
          if (validateCode(code)) {
            saveButtonProps.onClick?.();
          }
        },
      }}
    >
      {hasBacktests && (
        <Alert
          message="Warning: This strategy has existing backtests"
          description="Editing this strategy will not affect historical backtest results, but new backtests will use the updated code. Consider creating a new strategy version instead."
          type="warning"
          showIcon
          closable
          style={{ marginBottom: 24 }}
        />
      )}

      <Form
        {...formProps}
        layout="vertical"
        onFinish={(values) => {
          if (validateCode(values.code)) {
            formProps.onFinish?.({
              name: values.name,
              description: values.description || '',
              code: values.code,
              parent_id: values.parent_id,
            });
          }
        }}
      >
        <Form.Item
          label="Strategy Name"
          name="name"
          rules={[
            {
              required: true,
              message: 'Please enter a strategy name',
            },
            {
              min: 3,
              message: 'Name must be at least 3 characters',
            },
          ]}
        >
          <Input placeholder="e.g., EMACrossStrategy" />
        </Form.Item>

        <Form.Item
          label="Description"
          name="description"
          rules={[
            {
              required: true,
              message: 'Please enter a description',
            },
          ]}
        >
          <TextArea
            rows={3}
            placeholder="Describe what this strategy does and its key features"
          />
        </Form.Item>

        <Form.Item
          label="Parent Strategy (Optional)"
          name="parent_id"
          help="Select a parent strategy if this is derived from another strategy"
        >
          <Select
            {...parentSelectProps}
            placeholder="Select parent strategy"
            allowClear
            showSearch
            filterOption={(input, option) => {
              const label = option?.label;
              if (typeof label === 'string') {
                return label.toLowerCase().includes(input.toLowerCase());
              }
              return false;
            }}
          />
        </Form.Item>

        <Form.Item
          label="Strategy Code"
          name="code"
          rules={[
            {
              required: true,
              message: 'Please enter the strategy code',
            },
          ]}
        >
          <TextArea
            rows={20}
            placeholder="Paste your FreqTrade strategy code here..."
            style={{
              fontFamily: 'monospace',
              fontSize: 13,
            }}
            onChange={handleCodeChange}
          />
        </Form.Item>

        {codeError && (
          <Alert
            message="Code Validation Error"
            description={codeError}
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Alert
          message="Strategy Code Requirements"
          description={
            <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
              <li>Must define a class that inherits from IStrategy</li>
              <li>Must implement populate_indicators method</li>
              <li>Must implement populate_entry_trend method</li>
              <li>Must implement populate_exit_trend method</li>
              <li>Follow FreqTrade strategy development guidelines</li>
            </ul>
          }
          type="info"
          style={{ marginBottom: 16 }}
        />
      </Form>
    </Edit>
  );
};
