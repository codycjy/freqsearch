import { Refine } from '@refinedev/core';
import { RefineKbar, RefineKbarProvider } from '@refinedev/kbar';
import routerBindings, {
  DocumentTitleHandler,
  NavigateToResource,
  UnsavedChangesNotifier,
} from '@refinedev/react-router-v6';
import { App as AntdApp, ConfigProvider } from 'antd';
import { BrowserRouter, Outlet, Route, Routes } from 'react-router-dom';
import { ThemedLayoutV2, useNotificationProvider } from '@refinedev/antd';
import {
  DashboardOutlined,
  LineChartOutlined,
  ExperimentOutlined,
  RocketOutlined,
  RobotOutlined,
} from '@ant-design/icons';

import '@refinedev/antd/dist/reset.css';

import { dataProvider, liveProvider } from '@providers';
import { DashboardPage } from '@pages/dashboard';
import { StrategyList, StrategyShow, StrategyCreate, StrategyEdit } from '@resources/strategies';
import { BacktestList, BacktestShow, BacktestCreate } from '@resources/backtests';
import { OptimizationList, OptimizationShow, OptimizationCreate } from '@resources/optimizations';
import { AgentList, AgentShow } from '@resources/agents';

function App() {
  return (
    <BrowserRouter>
      <RefineKbarProvider>
        <ConfigProvider
          theme={{
            token: {
              colorPrimary: '#1890ff',
            },
          }}
        >
          <AntdApp>
            <Refine
              dataProvider={dataProvider}
              liveProvider={liveProvider}
              notificationProvider={useNotificationProvider}
              routerProvider={routerBindings}
              resources={[
                {
                  name: 'dashboard',
                  list: '/',
                  meta: {
                    label: 'Dashboard',
                    icon: <DashboardOutlined />,
                  },
                },
                {
                  name: 'strategies',
                  list: '/strategies',
                  create: '/strategies/create',
                  edit: '/strategies/edit/:id',
                  show: '/strategies/show/:id',
                  meta: {
                    label: 'Strategies',
                    icon: <LineChartOutlined />,
                    canDelete: true,
                  },
                },
                {
                  name: 'backtests',
                  list: '/backtests',
                  create: '/backtests/create',
                  show: '/backtests/show/:id',
                  meta: {
                    label: 'Backtests',
                    icon: <ExperimentOutlined />,
                  },
                },
                {
                  name: 'optimizations',
                  list: '/optimizations',
                  create: '/optimizations/create',
                  show: '/optimizations/show/:id',
                  meta: {
                    label: 'Optimizations',
                    icon: <RocketOutlined />,
                  },
                },
                {
                  name: 'agents',
                  list: '/agents',
                  show: '/agents/show/:id',
                  meta: {
                    label: 'Agents',
                    icon: <RobotOutlined />,
                  },
                },
              ]}
              options={{
                syncWithLocation: true,
                warnWhenUnsavedChanges: true,
                projectId: 'freqsearch',
                liveMode: 'auto',
              }}
            >
              <Routes>
                <Route
                  element={
                    <ThemedLayoutV2>
                      <Outlet />
                    </ThemedLayoutV2>
                  }
                >
                  <Route index element={<DashboardPage />} />

                  {/* Strategies */}
                  <Route path="/strategies">
                    <Route index element={<StrategyList />} />
                    <Route path="create" element={<StrategyCreate />} />
                    <Route path="edit/:id" element={<StrategyEdit />} />
                    <Route path="show/:id" element={<StrategyShow />} />
                  </Route>

                  {/* Backtests */}
                  <Route path="/backtests">
                    <Route index element={<BacktestList />} />
                    <Route path="create" element={<BacktestCreate />} />
                    <Route path="show/:id" element={<BacktestShow />} />
                  </Route>

                  {/* Optimizations */}
                  <Route path="/optimizations">
                    <Route index element={<OptimizationList />} />
                    <Route path="create" element={<OptimizationCreate />} />
                    <Route path="show/:id" element={<OptimizationShow />} />
                  </Route>

                  {/* Agents */}
                  <Route path="/agents">
                    <Route index element={<AgentList />} />
                    <Route path="show/:id" element={<AgentShow />} />
                  </Route>

                  <Route path="*" element={<NavigateToResource />} />
                </Route>
              </Routes>

              <RefineKbar />
              <UnsavedChangesNotifier />
              <DocumentTitleHandler />
            </Refine>
          </AntdApp>
        </ConfigProvider>
      </RefineKbarProvider>
    </BrowserRouter>
  );
}

export default App;
