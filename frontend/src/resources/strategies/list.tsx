import React from 'react';
import {
  List,
  useTable,
  EditButton,
  ShowButton,
  DeleteButton,
} from '@refinedev/antd';
import { Table, Space, Typography, Tag, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { Strategy } from '@providers/types';

const { Text } = Typography;

/**
 * Extended strategy type with best_result from API
 */
interface StrategyWithBestResult extends Strategy {
  best_result?: {
    sharpe_ratio: number;
    profit_pct: number;
    max_drawdown_pct: number;
    total_trades: number;
    win_rate: number;
    backtest_count: number;
  };
}

/**
 * StrategyList Component
 *
 * Lists all strategies with performance metrics
 * - Filterable by name, min sharpe ratio, min profit
 * - Sortable by all metric columns
 * - Actions: View, Edit, Delete
 *
 * Uses Refine's useTable hook with Ant Design Table
 */
export const StrategyList: React.FC = () => {
  const { tableProps, searchFormProps } = useTable<StrategyWithBestResult>({
    resource: 'strategies',
    syncWithLocation: true,
    onSearch: (values: any) => {
      const filters: Array<{
        field: string;
        operator: 'contains' | 'gte';
        value: any;
      }> = [];

      if (values.name) {
        filters.push({
          field: 'name',
          operator: 'contains',
          value: values.name,
        });
      }

      if (values.min_sharpe) {
        filters.push({
          field: 'min_sharpe',
          operator: 'gte',
          value: values.min_sharpe,
        });
      }

      if (values.min_profit_pct) {
        filters.push({
          field: 'min_profit_pct',
          operator: 'gte',
          value: values.min_profit_pct,
        });
      }

      return filters;
    },
  });

  return (
    <List>
      <div style={{ marginBottom: 16, display: 'flex', gap: 16 }}>
        <Input
          placeholder="Search by name"
          prefix={<SearchOutlined />}
          style={{ width: 300 }}
          onChange={(e) => {
            const value = e.target.value;
            searchFormProps?.form?.setFieldsValue({ name: value });
            searchFormProps?.form?.submit();
          }}
        />
      </div>

      <Table {...tableProps} rowKey="id">
        <Table.Column
          dataIndex="name"
          title="Name"
          sorter
          render={(_, record: StrategyWithBestResult) => (
            <div>
              <Text strong>{record.name}</Text>
              {record.parent_id && (
                <div>
                  <Tag color="blue" style={{ fontSize: '11px', marginTop: 4 }}>
                    Gen {record.generation}
                  </Tag>
                </div>
              )}
            </div>
          )}
        />

        <Table.Column
          dataIndex="description"
          title="Description"
          ellipsis
          render={(value) => (
            <Text ellipsis style={{ maxWidth: 300 }}>
              {value || '-'}
            </Text>
          )}
        />

        <Table.Column
          dataIndex={['best_result', 'sharpe_ratio']}
          title="Sharpe Ratio"
          sorter
          align="right"
          render={(value) => (
            <Text
              style={{
                color: value > 0 ? '#52c41a' : value < 0 ? '#f5222d' : undefined,
                fontWeight: 500,
              }}
            >
              {value ? value.toFixed(2) : '-'}
            </Text>
          )}
        />

        <Table.Column
          dataIndex={['best_result', 'profit_pct']}
          title="Profit %"
          sorter
          align="right"
          render={(value) => (
            <Text
              style={{
                color: value > 0 ? '#52c41a' : value < 0 ? '#f5222d' : undefined,
                fontWeight: 500,
              }}
            >
              {value ? `${value.toFixed(2)}%` : '-'}
            </Text>
          )}
        />

        <Table.Column
          dataIndex={['best_result', 'win_rate']}
          title="Win Rate"
          sorter
          align="right"
          render={(value) => (
            <Text>{value ? `${(value * 100).toFixed(1)}%` : '-'}</Text>
          )}
        />

        <Table.Column
          dataIndex={['best_result', 'total_trades']}
          title="Trades"
          sorter
          align="right"
          render={(value) => <Text>{value || '-'}</Text>}
        />

        <Table.Column
          dataIndex={['best_result', 'backtest_count']}
          title="Backtests"
          align="right"
          render={(value) => <Tag color="blue">{value || 0}</Tag>}
        />

        <Table.Column
          dataIndex="created_at"
          title="Created"
          sorter
          render={(value) => (
            <Text type="secondary">
              {new Date(value).toLocaleDateString()}
            </Text>
          )}
        />

        <Table.Column
          title="Actions"
          dataIndex="actions"
          render={(_, record: StrategyWithBestResult) => (
            <Space>
              <ShowButton
                hideText
                size="small"
                recordItemId={record.id}
              />
              <EditButton
                hideText
                size="small"
                recordItemId={record.id}
              />
              <DeleteButton
                hideText
                size="small"
                recordItemId={record.id}
              />
            </Space>
          )}
        />
      </Table>
    </List>
  );
};
