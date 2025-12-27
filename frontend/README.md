# FreqSearch Frontend

Admin dashboard for the FreqSearch trading strategy optimization platform.

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite 5.x
- **Admin Framework**: Refine v4
- **UI Library**: Ant Design 5.x
- **Routing**: React Router v6
- **Charts**: Tremor React + Recharts
- **State Management**: Refine hooks + React Context
- **HTTP Client**: Axios
- **Real-time**: WebSocket (via Live Provider)

## Project Structure

```
frontend/
├── src/
│   ├── App.tsx                 # Main app with Refine setup
│   ├── main.tsx               # Entry point
│   ├── providers/             # Refine providers
│   │   ├── dataProvider.ts   # REST API integration
│   │   ├── liveProvider.ts   # WebSocket integration
│   │   └── types.ts          # API type definitions
│   ├── resources/            # Resource CRUD pages
│   │   ├── strategies/
│   │   ├── backtests/
│   │   ├── optimizations/
│   │   └── agents/
│   ├── pages/                # Non-resource pages
│   │   └── dashboard/        # Main dashboard
│   ├── components/           # Reusable components
│   │   ├── charts/
│   │   └── common/
│   ├── api/                  # API utilities
│   │   └── axios.ts          # Axios instance
│   └── types/                # TypeScript types
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── .env                      # Environment variables
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8080`

### Installation

```bash
# Install dependencies
npm install
```

### Configuration

Create or edit `.env` file:

```env
VITE_API_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/api/v1/ws/events
```

### Development

```bash
# Start dev server (http://localhost:3000)
npm run dev
```

### Build

```bash
# Type check and build for production
npm run build

# Preview production build
npm run preview
```

### Linting

```bash
npm run lint
```

## Features

### Dashboard
- Real-time queue statistics (pending/running/completed jobs)
- Active optimizations with live progress
- Agent status monitoring
- Performance charts (last 24h)

### Resources

#### Strategies
- List all strategies with performance metrics
- View strategy code and lineage
- Create new strategies (manual or from optimization)
- Delete strategies

#### Backtests
- List backtest jobs with status
- View detailed results and metrics
- Submit new backtest jobs
- Cancel running jobs

#### Optimizations
- List optimization runs
- View iterations and progress
- Create new optimization runs
- Control runs (pause/resume/cancel)

#### Agents
- View agent status and activity
- Monitor current tasks

### Real-time Updates

The app uses WebSocket connections for real-time updates:

- Optimization iteration progress
- Backtest job status changes
- Agent activity
- Queue statistics

## API Integration

### Data Provider

The data provider (`src/providers/dataProvider.ts`) implements Refine's DataProvider interface:

- `getList` - List resources with pagination/filters
- `getOne` - Get single resource
- `create` - Create new resource
- `update` - Update resource
- `delete` - Delete resource
- `custom` - Custom API calls

### Live Provider

The live provider (`src/providers/liveProvider.ts`) handles WebSocket events:

- Auto-reconnection with exponential backoff
- Ping/pong keep-alive
- Event routing to Refine resources
- Subscription management

### Type Safety

All API types are defined in `src/providers/types.ts` based on the backend protobuf definitions.

## Path Aliases

The following path aliases are configured:

- `@/*` → `src/*`
- `@components/*` → `src/components/*`
- `@pages/*` → `src/pages/*`
- `@resources/*` → `src/resources/*`
- `@providers/*` → `src/providers/*`
- `@api/*` → `src/api/*`

## Development Notes

### Component Guidelines

- Use functional components with hooks
- Implement TypeScript strict mode
- Follow Ant Design component patterns
- Use Refine hooks for data fetching
- Implement responsive design (mobile-first)

### Performance Considerations

- Use React.lazy() for code splitting
- Implement useCallback/useMemo where appropriate
- Virtualize long lists
- Optimize chart rendering

### Accessibility

- Use semantic HTML
- Add ARIA labels where needed
- Support keyboard navigation
- Maintain color contrast ratios

## Troubleshooting

### API Connection Issues

1. Ensure backend is running on `http://localhost:8080`
2. Check CORS configuration on backend
3. Verify `.env` file contains correct URLs

### WebSocket Issues

1. Check WebSocket endpoint is accessible
2. Verify firewall/proxy settings
3. Check browser console for connection errors

### Build Issues

1. Clear node_modules and reinstall: `rm -rf node_modules && npm install`
2. Clear Vite cache: `rm -rf node_modules/.vite`
3. Check TypeScript errors: `npm run build`

## Contributing

1. Follow the existing code style
2. Add TypeScript types for all new code
3. Test on multiple screen sizes
4. Ensure no ESLint warnings
5. Update documentation as needed
