/**
 * TriggerScoutModal - Usage Examples
 *
 * This file demonstrates various ways to use the TriggerScoutModal component.
 * These examples are for reference only and can be adapted to your specific needs.
 */

import React, { useState } from 'react';
import { Button, Space, Card } from 'antd';
import { RocketOutlined } from '@ant-design/icons';
import { TriggerScoutModal } from './TriggerScoutModal';

/**
 * Example 1: Basic Usage
 * Simple button that opens the modal
 */
export const BasicExample: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <Button
        type="primary"
        icon={<RocketOutlined />}
        onClick={() => setModalOpen(true)}
      >
        Trigger Scout
      </Button>

      <TriggerScoutModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </>
  );
};

/**
 * Example 2: With Success Callback
 * Opens modal and performs additional actions on success
 */
export const WithSuccessCallback: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);

  const handleSuccess = () => {
    console.log('Scout triggered successfully!');
    // You can add additional logic here:
    // - Show custom notification
    // - Redirect to a specific page
    // - Trigger analytics event
    // - Refresh additional data
  };

  return (
    <>
      <Button
        type="primary"
        icon={<RocketOutlined />}
        onClick={() => setModalOpen(true)}
      >
        Trigger Scout
      </Button>

      <TriggerScoutModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={handleSuccess}
      />
    </>
  );
};

/**
 * Example 3: Integration with Strategy List Page
 * Add trigger button to existing strategy list toolbar
 */
export const StrategyListIntegration: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <Card
      title="Strategies"
      extra={
        <Space>
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => setModalOpen(true)}
          >
            Trigger Scout
          </Button>
          {/* Other action buttons can go here */}
        </Space>
      }
    >
      {/* Your strategy list content */}
      <div>Strategy list goes here...</div>

      <TriggerScoutModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </Card>
  );
};

/**
 * Example 4: Multiple Trigger Points
 * Use the same modal instance from different trigger points
 */
export const MultipleTriggerPoints: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Header button */}
        <Card title="Actions">
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => setModalOpen(true)}
          >
            Trigger Scout (Header)
          </Button>
        </Card>

        {/* Empty state button */}
        <Card>
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <p>No strategies found</p>
            <Button
              type="link"
              icon={<RocketOutlined />}
              onClick={() => setModalOpen(true)}
            >
              Fetch strategies from Scout
            </Button>
          </div>
        </Card>
      </Space>

      {/* Single modal instance shared by all triggers */}
      <TriggerScoutModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </>
  );
};

/**
 * Example 5: Programmatic Trigger
 * Open modal based on external conditions
 */
export const ProgrammaticTrigger: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);

  // Example: Auto-open modal on mount if needed
  React.useEffect(() => {
    const shouldAutoOpen = localStorage.getItem('autoOpenScout') === 'true';
    if (shouldAutoOpen) {
      setModalOpen(true);
      localStorage.removeItem('autoOpenScout');
    }
  }, []);

  return (
    <>
      <Space>
        <Button onClick={() => setModalOpen(true)}>
          Open Scout Modal
        </Button>
        <Button
          onClick={() => {
            localStorage.setItem('autoOpenScout', 'true');
            window.location.reload();
          }}
        >
          Test Auto-Open on Reload
        </Button>
      </Space>

      <TriggerScoutModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </>
  );
};
