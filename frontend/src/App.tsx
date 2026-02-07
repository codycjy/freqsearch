import { Refine } from '@refinedev/core';
import { RefineKbar, RefineKbarProvider } from '@refinedev/kbar';
import routerBindings, {
  DocumentTitleHandler,
  NavigateToResource,
  UnsavedChangesNotifier,
} from '@refinedev/react-router-v6';
import { App as AntdApp, ConfigProvider, Spin } from 'antd';
import { BrowserRouter, Outlet, Route, Routes } from 'react-router-dom';
import { ThemedLayoutV2, useNotificationProvider } from '@refinedev/antd';
import {
  DashboardOutlined,
  LineChartOutlined,
  ExperimentOutlined,
  RocketOutlined,
  RobotOutlined,
  SearchOutlined,
  ClockCircleOutlined,
  FunctionOutlined,
} from '@ant-design/icons';
import { lazy, Suspense } from 'react';

import '@refinedev/antd/dist/reset.css';

import { dataProvider, liveProvider } from '@providers';

// Lazy load route components for code splitting
const DashboardPage = lazy(() => import('@pages/dashboard').then(m => ({ default: m.DashboardPage })));
const StrategyList = lazy(() => import('@resources/strategies').then(m => ({ default: m.StrategyList })));
const StrategyShow = lazy(() => import('@resources/strategies').then(m => ({ default: m.StrategyShow })));
const StrategyCreate = lazy(() => import('@resources/strategies').then(m => ({ default: m.StrategyCreate })));
const StrategyEdit = lazy(() => import('@resources/strategies').then(m => ({ default: m.StrategyEdit })));
const BacktestList = lazy(() => import('@resources/backtests').then(m => ({ default: m.BacktestList })));
const BacktestShow = lazy(() => import('@resources/backtests').then(m => ({ default: m.BacktestShow })));
const BacktestCreate = lazy(() => import('@resources/backtests').then(m => ({ default: m.BacktestCreate })));
const OptimizationList = lazy(() => import('@resources/optimizations').then(m => ({ default: m.OptimizationList })));
const OptimizationShow = lazy(() => import('@resources/optimizations').then(m => ({ default: m.OptimizationShow })));
const OptimizationCreate = lazy(() => import('@resources/optimizations').then(m => ({ default: m.OptimizationCreate })));
const AgentList = lazy(() => import('@resources/agents').then(m => ({ default: m.AgentList })));
const AgentShow = lazy(() => import('@resources/agents').then(m => ({ default: m.AgentShow })));
const ScoutList = lazy(() => import('@resources/scout').then(m => ({ default: m.ScoutList })));
const ScoutShow = lazy(() => import('@resources/scout').then(m => ({ default: m.ScoutShow })));
const ScoutScheduleList = lazy(() => import('@resources/scout').then(m => ({ default: m.ScoutScheduleList })));
const FactorList = lazy(() => import('@resources/factors').then(m => ({ default: m.FactorList })));
const FactorShow = lazy(() => import('@resources/factors').then(m => ({ default: m.FactorShow })));

// Loading fallback component
const PageLoader = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <Spin size="large" tip="Loading..." />
  </div>
);

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
                {
                  name: 'factors',
                  list: '/factors',
                  show: '/factors/show/:id',
                  meta: {
                    label: 'Factors',
                    icon: <FunctionOutlined />,
                  },
                },
                {
                  name: 'scout',
                  meta: {
                    label: 'Scout',
                    icon: <SearchOutlined />,
                  },
                },
                {
                  name: 'scout-runs',
                  list: '/scout/runs',
                  show: '/scout/runs/:id',
                  meta: {
                    label: 'Runs',
                    icon: <RocketOutlined />,
                    parent: 'scout',
                  },
                },
                {
                  name: 'scout-schedules',
                  list: '/scout/schedules',
                  meta: {
                    label: 'Schedules',
                    icon: <ClockCircleOutlined />,
                    parent: 'scout',
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
                      <Suspense fallback={<PageLoader />}>
                        <Outlet />
                      </Suspense>
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

                  {/* Factors */}
                  <Route path="/factors">
                    <Route index element={<FactorList />} />
                    <Route path="show/:id" element={<FactorShow />} />
                  </Route>

                  {/* Scout */}
                  <Route path="/scout">
                    <Route path="runs">
                      <Route index element={<ScoutList />} />
                      <Route path=":id" element={<ScoutShow />} />
                    </Route>
                    <Route path="schedules" element={<ScoutScheduleList />} />
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
