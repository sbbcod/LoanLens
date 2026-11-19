import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { Layout } from './components/Layout'
import './index.css'
import { ApplicationsPage } from './pages/ApplicationsPage'

// The review page (PDF reader) and metrics page (charts) are the heavy ones;
// load them only when opened, so the first page is quick.
const lazyPage = (load: () => Promise<{ Component: React.ComponentType }>) => ({ lazy: load })

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false } },
})

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <ApplicationsPage /> },
      {
        path: '/applications/:id',
        ...lazyPage(() => import('./pages/ReviewPage').then((m) => ({ Component: m.ReviewPage }))),
      },
      {
        path: '/metrics',
        ...lazyPage(() => import('./pages/MetricsPage').then((m) => ({ Component: m.MetricsPage }))),
      },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
