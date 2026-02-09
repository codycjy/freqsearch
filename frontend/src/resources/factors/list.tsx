import { List, useTable, FilterDropdown, getDefaultSortOrder, ShowButton } from "@refinedev/antd";
import { Table, Tag, Input, Select, Card, Statistic, Row, Col, Typography, Tooltip } from "antd";
import { useCustom } from "@refinedev/core";
import { SearchOutlined, ExperimentOutlined } from "@ant-design/icons";

const { Text, Paragraph } = Typography;

// Category color mapping
const categoryColors: Record<string, string> = {
  momentum: "blue",
  mean_reversion: "green",
  volatility: "orange",
  volume: "purple",
  price_pattern: "cyan",
};

// Holding period labels
const holdingPeriodLabels: Record<string, string> = {
  intraday: "日内",
  short: "短期 (1-3天)",
  medium: "中期 (3-10天)",
  long: "长期 (10天+)",
};

// Complexity labels
const complexityLabels: Record<string, string> = {
  simple: "简单",
  medium: "中等",
  complex: "复杂",
};

export const FactorList = () => {
  const { tableProps, sorters } = useTable({
    resource: "factors",
    syncWithLocation: true,
    pagination: {
      pageSize: 20,
    },
    sorters: {
      initial: [{ field: "name", order: "asc" }],
    },
  });

  // Get category stats
  const { data: statsData } = useCustom({
    url: "/factors/categories",
    method: "get",
  });

  const stats = (statsData as any)?.data?.stats || {};
  const totalFactors = Object.values(stats).reduce((a: number, b: any) => a + b, 0);

  return (
    <List title="因子库 (WorldQuant 101)">
      {/* Stats Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="总因子数"
              value={totalFactors}
              prefix={<ExperimentOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="动量"
              value={stats.momentum || 0}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="均值回归"
              value={stats.mean_reversion || 0}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="成交量"
              value={stats.volume || 0}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="波动率"
              value={stats.volatility || 0}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="价格形态"
              value={stats.price_pattern || 0}
              valueStyle={{ color: '#13c2c2' }}
            />
          </Card>
        </Col>
      </Row>

      <Table
        {...tableProps}
        rowKey="id"
        size="small"
        scroll={{ x: 1200 }}
      >
        <Table.Column
          dataIndex="name"
          title="名称"
          width={120}
          sorter
          defaultSortOrder={getDefaultSortOrder("name", sorters)}
          filterDropdown={(props) => (
            <FilterDropdown {...props}>
              <Input placeholder="搜索名称" />
            </FilterDropdown>
          )}
          filterIcon={<SearchOutlined />}
          render={(value) => (
            <Text strong style={{ fontFamily: "monospace" }}>
              {value?.toUpperCase()}
            </Text>
          )}
        />

        <Table.Column
          dataIndex="category"
          title="类别"
          width={120}
          filterDropdown={(props) => (
            <FilterDropdown {...props}>
              <Select
                style={{ width: 150 }}
                placeholder="选择类别"
                options={[
                  { label: "动量", value: "momentum" },
                  { label: "均值回归", value: "mean_reversion" },
                  { label: "成交量", value: "volume" },
                  { label: "波动率", value: "volatility" },
                  { label: "价格形态", value: "price_pattern" },
                ]}
              />
            </FilterDropdown>
          )}
          render={(value) => (
            <Tag color={categoryColors[value] || "default"}>
              {value === "momentum" && "动量"}
              {value === "mean_reversion" && "均值回归"}
              {value === "volume" && "成交量"}
              {value === "volatility" && "波动率"}
              {value === "price_pattern" && "价格形态"}
            </Tag>
          )}
        />

        <Table.Column
          dataIndex="description"
          title="描述"
          ellipsis={{ showTitle: false }}
          render={(value) => (
            <Tooltip title={value} placement="topLeft">
              <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, fontSize: 12 }}>
                {value}
              </Paragraph>
            </Tooltip>
          )}
        />

        <Table.Column
          dataIndex="holding_period"
          title="持仓期"
          width={120}
          filterDropdown={(props) => (
            <FilterDropdown {...props}>
              <Select
                style={{ width: 150 }}
                placeholder="选择持仓期"
                options={[
                  { label: "日内", value: "intraday" },
                  { label: "短期", value: "short" },
                  { label: "中期", value: "medium" },
                  { label: "长期", value: "long" },
                ]}
              />
            </FilterDropdown>
          )}
          render={(value) => (
            <Tag>{holdingPeriodLabels[value] || value}</Tag>
          )}
        />

        <Table.Column
          dataIndex="complexity"
          title="复杂度"
          width={90}
          render={(value) => {
            const colors: Record<string, string> = {
              simple: "green",
              medium: "gold",
              complex: "red",
            };
            return (
              <Tag color={colors[value] || "default"}>
                {complexityLabels[value] || value}
              </Tag>
            );
          }}
        />

        <Table.Column
          dataIndex="data_requirement"
          title="数据需求"
          width={100}
          render={(value) => {
            const labels: Record<string, string> = {
              price_only: "仅价格",
              volume: "价量",
              vwap: "VWAP",
              industry: "行业",
            };
            return <Text type="secondary">{labels[value] || value}</Text>;
          }}
        />

        <Table.Column
          dataIndex="expression"
          title="公式"
          width={200}
          ellipsis={{ showTitle: false }}
          render={(value) => (
            <Tooltip title={value} placement="topLeft">
              <Text
                code
                style={{
                  fontSize: 10,
                  maxWidth: 200,
                  display: "inline-block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap"
                }}
              >
                {value?.substring(0, 50)}...
              </Text>
            </Tooltip>
          )}
        />

        <Table.Column
          title="操作"
          dataIndex="actions"
          width={80}
          fixed="right"
          render={(_, record: any) => (
            <ShowButton
              hideText
              size="small"
              recordItemId={record.id}
            />
          )}
        />
      </Table>
    </List>
  );
};
