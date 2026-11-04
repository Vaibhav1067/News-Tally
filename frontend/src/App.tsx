import { lazy, Suspense } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import Landing from './pages/Landing'

const Analyze = lazy(() => import('./pages/Analyze'))
const Explorer = lazy(() => import('./pages/Explorer'))
const Intelligence = lazy(() => import('./pages/Intelligence'))
const Methodology = lazy(() => import('./pages/Methodology'))

function NotFound() {
  return (
    <div className="mx-auto max-w-[1320px] px-5 py-24 md:px-8">
      <h1 className="text-[26px] font-bold">Page not found</h1>
      <p className="mt-2 text-muted">That address does not exist. <Link className="text-accent-ink underline" to="/">Return home</Link>.</p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="mx-auto max-w-[1320px] px-8"><Spinner label="Loading" /></div>}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Landing />} />
            <Route path="analyze" element={<Analyze />} />
            <Route path="explorer" element={<Explorer />} />
            <Route path="intelligence" element={<Intelligence />} />
            <Route path="methodology" element={<Methodology />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
