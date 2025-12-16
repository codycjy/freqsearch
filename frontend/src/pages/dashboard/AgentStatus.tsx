import { Card, Title, Flex, Badge } from '@tremor/react';
import { Agent, AgentStatus as AgentStatusType, AgentType } from '../../types/api';

interface AgentStatusProps {
  agents?: Agent[];
  loading?: boolean;
}

/**
 * AgentStatus Component
 * Displays the status of each agent type (Orchestrator, Engineer, Analyst, Scout)
 * Status indicators: Active (green), Idle (yellow), Offline (gray)
 */
export const AgentStatus: React.FC<AgentStatusProps> = ({ agents, loading }) => {
  // Default agents if none provided
  const defaultAgents: Agent[] = [
    { type: 'orchestrator', status: 'offline' },
    { type: 'engineer', status: 'offline' },
    { type: 'analyst', status: 'offline' },
    { type: 'scout', status: 'offline' },
  ];

  const displayAgents = agents || defaultAgents;

  const getStatusColor = (status: AgentStatusType): 'emerald' | 'yellow' | 'gray' => {
    switch (status) {
      case 'active':
        return 'emerald';
      case 'idle':
        return 'yellow';
      case 'offline':
      default:
        return 'gray';
    }
  };

  const formatAgentName = (type: AgentType): string => {
    return type.charAt(0).toUpperCase() + type.slice(1);
  };

  const formatLastSeen = (lastSeen?: string): string => {
    if (!lastSeen) return '';
    const date = new Date(lastSeen);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  if (loading) {
    return (
      <Card>
        <Title>Agent Status</Title>
        <div style={{ marginTop: 16 }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: i > 1 ? 12 : 0
            }}>
              <div style={{ height: 16, width: 96, borderRadius: 4, backgroundColor: '#e8e8e8' }} />
              <div style={{ height: 24, width: 64, borderRadius: 4, backgroundColor: '#e8e8e8' }} />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Title>Agent Status</Title>
      <div style={{ marginTop: 16 }}>
        {displayAgents.map((agent, index) => (
          <Flex
            key={agent.type}
            alignItems="center"
            style={{
              marginTop: index > 0 ? 12 : 0,
              marginLeft: -8,
              marginRight: -8,
              paddingLeft: 8,
              paddingRight: 8,
              paddingTop: 4,
              paddingBottom: 4,
              borderRadius: 4,
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
              e.currentTarget.style.backgroundColor = '#fafafa';
            }}
            onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontWeight: 500, color: '#262626' }}>
                  {formatAgentName(agent.type)}
                </span>
                {agent.current_task && (
                  <span style={{
                    fontSize: 12,
                    color: '#8c8c8c',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    maxWidth: 150
                  }}>
                    {agent.current_task}
                  </span>
                )}
              </div>
              {agent.last_seen && agent.status !== 'offline' && (
                <span style={{ fontSize: 12, color: '#8c8c8c' }}>
                  {formatLastSeen(agent.last_seen)}
                </span>
              )}
            </div>
            <Badge color={getStatusColor(agent.status)} size="sm">
              {agent.status}
            </Badge>
          </Flex>
        ))}
      </div>
    </Card>
  );
};
