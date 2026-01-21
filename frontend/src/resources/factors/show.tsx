import { Show } from "@refinedev/antd";
import { useShow } from "@refinedev/core";
import { Typography, Tag, Descriptions, Card, Row, Col, Divider } from "antd";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

const { Title, Text, Paragraph } = Typography;

// Category color mapping
const categoryColors: Record<string, string> = {
  momentum: "blue",
  mean_reversion: "green",
  volatility: "orange",
  volume: "purple",
  price_pattern: "cyan",
};

const categoryLabels: Record<string, string> = {
  momentum: "动量",
  mean_reversion: "均值回归",
  volatility: "波动率",
  volume: "成交量",
  price_pattern: "价格形态",
};

const holdingPeriodLabels: Record<string, string> = {
  intraday: "日内",
  short: "短期 (1-3天)",
  medium: "中期 (3-10天)",
  long: "长期 (10天+)",
};

const complexityLabels: Record<string, string> = {
  simple: "简单",
  medium: "中等",
  complex: "复杂",
};

export const FactorShow = () => {
  const { queryResult } = useShow({
    resource: "factors",
  });

  const record = queryResult?.data?.data;
  const isLoading = queryResult?.isLoading;

  return (
    <Show isLoading={isLoading} title={record?.name?.toUpperCase()}>
      <Row gutter={24}>
        <Col span={16}>
          {/* Basic Info */}
          <Card title="基本信息" size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="名称">
                <Text strong style={{ fontFamily: "monospace" }}>
                  {record?.name?.toUpperCase()}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                <Tag>{record?.source}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="类别">
                <Tag color={categoryColors[record?.category]}>
                  {categoryLabels[record?.category] || record?.category}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="信号类型">
                <Tag>{record?.signal_type}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="持仓期">
                {holdingPeriodLabels[record?.holding_period] || record?.holding_period}
              </Descriptions.Item>
              <Descriptions.Item label="复杂度">
                <Tag color={
                  record?.complexity === "simple" ? "green" :
                  record?.complexity === "medium" ? "gold" : "red"
                }>
                  {complexityLabels[record?.complexity] || record?.complexity}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="数据需求">
                {record?.data_requirement}
              </Descriptions.Item>
              <Descriptions.Item label="市场状态">
                {record?.market_regime}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* Description */}
          <Card title="描述" size="small" style={{ marginBottom: 16 }}>
            <Paragraph>{record?.description}</Paragraph>
          </Card>

          {/* Expression */}
          <Card title="DSL 公式" size="small" style={{ marginBottom: 16 }}>
            <div style={{
              background: "#1e1e1e",
              padding: 16,
              borderRadius: 4,
              overflow: "auto"
            }}>
              <Text code style={{ color: "#d4d4d4", whiteSpace: "pre-wrap", fontSize: 12 }}>
                {record?.expression}
              </Text>
            </div>
          </Card>

          {/* Code Template */}
          <Card title="Python 代码" size="small">
            {record?.code_template ? (
              <SyntaxHighlighter
                language="python"
                style={oneDark}
                customStyle={{
                  fontSize: 12,
                  borderRadius: 4,
                  margin: 0
                }}
              >
                {record.code_template}
              </SyntaxHighlighter>
            ) : (
              <Text type="secondary">无代码模板</Text>
            )}
          </Card>
        </Col>

        <Col span={8}>
          {/* Dependencies */}
          <Card title="依赖信息" size="small" style={{ marginBottom: 16 }}>
            <Title level={5}>操作符依赖</Title>
            <div style={{ marginBottom: 16 }}>
              {record?.operator_deps?.map((op: string) => (
                <Tag key={op} style={{ marginBottom: 4 }}>{op}</Tag>
              )) || <Text type="secondary">无</Text>}
            </div>

            <Title level={5}>数据依赖</Title>
            <div>
              {record?.data_deps?.map((d: string) => (
                <Tag key={d} color="blue" style={{ marginBottom: 4 }}>{d}</Tag>
              )) || <Text type="secondary">无</Text>}
            </div>
          </Card>

          {/* Usage Example */}
          <Card title="使用示例" size="small">
            <SyntaxHighlighter
              language="python"
              style={oneDark}
              customStyle={{ fontSize: 11, borderRadius: 4 }}
            >
{`# 在 Freqtrade 策略中使用
from freqsearch_agents.factors.operators import *

def populate_indicators(self, dataframe, metadata):
    # 计算因子
    dataframe['${record?.name}'] = ${record?.name}(dataframe)
    return dataframe

def populate_entry_trend(self, dataframe, metadata):
    # 使用因子作为入场信号
    dataframe.loc[
        dataframe['${record?.name}'] > 0,
        'enter_long'
    ] = 1
    return dataframe`}
            </SyntaxHighlighter>
          </Card>
        </Col>
      </Row>
    </Show>
  );
};
