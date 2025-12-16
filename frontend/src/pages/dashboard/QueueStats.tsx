import { Card, Metric, Text, Flex, BadgeDelta } from '@tremor/react';
import { QueueStats as QueueStatsType } from '../../types/api';

interface QueueStatsProps {
  stats: QueueStatsType | undefined;
  loading?: boolean;
}

/**
 * QueueStats Component
 * Displays backtest queue statistics in 4 color-coded cards
 * Uses Tremor Card and Metric components for consistent dashboard UI
 */
export const QueueStats: React.FC<QueueStatsProps> = ({ stats, loading }) => {
  if (loading || !stats) {
    return (
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr',
        gap: 16
      }}>
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <Flex alignItems="start">
              <div style={{ height: 16, width: 96, borderRadius: 4, backgroundColor: '#e8e8e8' }} />
            </Flex>
            <Flex style={{ marginTop: 16 }}>
              <div style={{ height: 32, width: 64, borderRadius: 4, backgroundColor: '#e8e8e8' }} />
            </Flex>
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    {
      title: 'Pending Jobs',
      value: stats.pending,
      color: 'blue' as const,
      deltaType: 'unchanged' as const,
    },
    {
      title: 'Running Jobs',
      value: stats.running,
      color: 'yellow' as const,
      deltaType: 'moderateIncrease' as const,
    },
    {
      title: 'Completed',
      value: stats.completed,
      color: 'emerald' as const,
      deltaType: 'increase' as const,
    },
    {
      title: 'Failed',
      value: stats.failed,
      color: 'red' as const,
      deltaType: stats.failed > 0 ? ('decrease' as const) : ('unchanged' as const),
    },
  ];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 16
    }}>
      {cards.map((card) => (
        <Card
          key={card.title}
          decoration="top"
          decorationColor={card.color}
        >
          <Flex alignItems="start">
            <div>
              <Text>{card.title}</Text>
              <Metric style={{ marginTop: 8 }}>{card.value}</Metric>
            </div>
            {card.value > 0 && (
              <BadgeDelta deltaType={card.deltaType} size="xs" />
            )}
          </Flex>
        </Card>
      ))}
    </div>
  );
};
