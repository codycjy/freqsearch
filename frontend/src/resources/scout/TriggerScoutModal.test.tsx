/**
 * TriggerScoutModal - Unit Tests
 *
 * Basic test structure for the TriggerScoutModal component.
 * These tests ensure the component renders correctly and handles user interactions.
 *
 * Note: Update these tests according to your testing setup and requirements.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TriggerScoutModal } from './TriggerScoutModal';

// Mock Refine hooks
jest.mock('@refinedev/core', () => ({
  useCustomMutation: () => ({
    mutate: jest.fn(),
    isLoading: false,
  }),
  useInvalidate: () => jest.fn(),
}));

// Mock Ant Design message
jest.mock('antd', () => {
  const actual = jest.requireActual('antd');
  return {
    ...actual,
    message: {
      success: jest.fn(),
      error: jest.fn(),
    },
  };
});

describe('TriggerScoutModal', () => {
  const mockOnClose = jest.fn();
  const mockOnSuccess = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  /**
   * Test: Component renders when open
   */
  it('renders modal when open is true', () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Trigger Scout Agent')).toBeInTheDocument();
    expect(screen.getByText('Manual Scout Trigger')).toBeInTheDocument();
  });

  /**
   * Test: Component does not render when closed
   */
  it('does not render modal when open is false', () => {
    render(
      <TriggerScoutModal
        open={false}
        onClose={mockOnClose}
      />
    );

    expect(screen.queryByText('Trigger Scout Agent')).not.toBeInTheDocument();
  });

  /**
   * Test: Form fields are present
   */
  it('displays form fields for source and max_strategies', () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByLabelText('Data Source')).toBeInTheDocument();
    expect(screen.getByLabelText('Max Strategies')).toBeInTheDocument();
  });

  /**
   * Test: Data source options are available
   */
  it('displays all data source options', async () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    // Open the select dropdown
    const selectElement = screen.getByLabelText('Data Source');
    fireEvent.mouseDown(selectElement);

    await waitFor(() => {
      expect(screen.getByText('StratNinja')).toBeInTheDocument();
      expect(screen.getByText('GitHub')).toBeInTheDocument();
      expect(screen.getByText('FreqAI Gym')).toBeInTheDocument();
    });
  });

  /**
   * Test: Default max_strategies value
   */
  it('has default value of 100 for max_strategies', () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    const maxStrategiesInput = screen.getByLabelText('Max Strategies');
    expect(maxStrategiesInput).toHaveValue(100);
  });

  /**
   * Test: Cancel button calls onClose
   */
  it('calls onClose when cancel button is clicked', () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  /**
   * Test: Form validation - source is required
   */
  it('shows validation error when source is not selected', async () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    const submitButton = screen.getByText('Trigger Scout');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Please select a data source')).toBeInTheDocument();
    });
  });

  /**
   * Test: Form validation - max_strategies range
   */
  it('validates max_strategies is within range', async () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    const maxStrategiesInput = screen.getByLabelText('Max Strategies');

    // Test below minimum
    fireEvent.change(maxStrategiesInput, { target: { value: 0 } });
    const submitButton = screen.getByText('Trigger Scout');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Must be between 1 and 500')).toBeInTheDocument();
    });

    // Test above maximum
    fireEvent.change(maxStrategiesInput, { target: { value: 501 } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Must be between 1 and 500')).toBeInTheDocument();
    });
  });

  /**
   * Test: Accessibility - form has proper labels
   */
  it('has accessible form labels', () => {
    render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    expect(screen.getByLabelText('Data Source')).toBeInTheDocument();
    expect(screen.getByLabelText('Max Strategies')).toBeInTheDocument();
  });

  /**
   * Test: Modal has proper ARIA attributes
   */
  it('has proper ARIA attributes for accessibility', () => {
    const { container } = render(
      <TriggerScoutModal
        open={true}
        onClose={mockOnClose}
      />
    );

    const modal = container.querySelector('[role="dialog"]');
    expect(modal).toBeInTheDocument();
  });
});

/**
 * Integration Test Example
 *
 * This test demonstrates how to test the full flow with API calls
 */
describe('TriggerScoutModal - Integration', () => {
  it('submits form and calls API with correct payload', async () => {
    const mockMutate = jest.fn((config, callbacks) => {
      // Simulate successful API call
      if (callbacks?.onSuccess) {
        callbacks.onSuccess();
      }
    });

    jest.spyOn(require('@refinedev/core'), 'useCustomMutation').mockReturnValue({
      mutate: mockMutate,
      isLoading: false,
    });

    const mockOnSuccess = jest.fn();

    render(
      <TriggerScoutModal
        open={true}
        onClose={jest.fn()}
        onSuccess={mockOnSuccess}
      />
    );

    // Select data source
    const sourceSelect = screen.getByLabelText('Data Source');
    fireEvent.mouseDown(sourceSelect);
    await waitFor(() => {
      fireEvent.click(screen.getByText('StratNinja'));
    });

    // Set max strategies
    const maxStrategiesInput = screen.getByLabelText('Max Strategies');
    fireEvent.change(maxStrategiesInput, { target: { value: 150 } });

    // Submit form
    const submitButton = screen.getByText('Trigger Scout');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          url: '/api/v1/agents/scout/trigger',
          method: 'post',
          values: {
            source: 'stratninja',
            max_strategies: 150,
          },
        }),
        expect.any(Object)
      );
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });
});
