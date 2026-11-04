import { NavLink, Link, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'

export function Mark({ className = 'size-6' }: { className?: string }) {
  // Tally marks struck through: counting the evidence.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <g fill="#4a8ad6"><rect x="7" y="7" width="3" height="18" rx="1" /><rect x="12.5" y="7" width="3" height="18" rx="1" /><rect x="18" y="7" width="3" height="18" rx="1" /><rect x="23.5" y="7" width="3" height="18" rx="1" /></g>
      <rect x="3" y="14.5" width="27" height="3" rx="1" fill="#f4f4f2" transform="rotate(-22 16 16)" />
    </svg>
  )
}

const LINKS = [
  { to: '/analyze', label: 'Analyze' },
  { to: '/explorer', label: 'Fact-checks' },
  { to: '/intelligence', label: 'Dataset' },
  { to: '/methodology', label: 'Methodology' },
]

export function Layout() {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => { setOpen(false); window.scrollTo(0, 0) }, [loc.pathname])

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:bg-raised focus:px-3 focus:py-2">Skip to content</a>
      <header className="sticky top-0 z-40 bg-ground">
        <div className="mx-auto flex h-14 max-w-[1320px] items-center gap-8 px-5 md:px-8">
          <Link to="/" className="flex items-center gap-2.5" aria-label="NEWS TALLY home">
            <Mark />
            <span className="text-[15px] font-bold tracking-[-0.01em]">NEWS TALLY</span>
          </Link>
          <nav aria-label="Primary" className="hidden h-full items-center gap-6 md:flex">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to}
                className={({ isActive }) => `sel-line flex h-full items-center text-[13px] transition-colors ${isActive ? 'text-ink' : 'text-muted hover:text-ink'}`}
                data-active={loc.pathname.startsWith(l.to)}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <Link to="/analyze" className="hidden h-[34px] items-center rounded-full bg-ink px-4 text-[13px] font-semibold text-ground transition hover:bg-white active:scale-[0.98] sm:inline-flex">
              Analyze a claim
            </Link>
            <button className="grid size-9 place-items-center rounded-full text-muted hover:text-ink md:hidden" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
          </div>
        </div>
        {open && (
          <nav aria-label="Mobile" className="bg-ground px-5 pb-4 md:hidden">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} className={({ isActive }) => `block py-3 text-[15px] ${isActive ? 'text-ink' : 'text-muted'}`}>{l.label}</NavLink>
            ))}
          </nav>
        )}
      </header>
      <main id="main" className="flex-1"><Outlet /></main>
      <Footer />
    </div>
  )
}

function Footer() {
  return (
    <footer className="mt-24 bg-surface">
      <div className="mx-auto grid max-w-[1320px] gap-8 px-5 py-10 md:grid-cols-[1.2fr_1fr_1fr] md:px-8">
        <div>
          <div className="flex items-center gap-2.5"><Mark className="size-5" /><span className="font-bold">NEWS TALLY</span></div>
          <p className="mt-3 max-w-sm text-[13px] text-muted">Understand the claim. Examine the evidence. An information-assistance tool — it surfaces published fact-checks and model signals, and does not decide what is true.</p>
        </div>
        <div className="text-[13px]">
          <h3 className="font-semibold">Fact-check data</h3>
          <p className="mt-2 text-muted">Headlines, claims and one-sentence conclusions from <a className="text-ink underline underline-offset-2" href="https://factly.in" target="_blank" rel="noreferrer">Factly</a> and <a className="text-ink underline underline-offset-2" href="https://www.altnews.in" target="_blank" rel="noreferrer">Alt News</a>, collected from their public WordPress APIs. Every record links to the original article.</p>
        </div>
        <div className="text-[13px]">
          <h3 className="font-semibold">Project</h3>
          <ul className="mt-2 space-y-1 text-muted">
            <li><Link className="hover:text-ink" to="/methodology">Methodology and limitations</Link></li>
            <li><Link className="hover:text-ink" to="/intelligence">Dataset statistics</Link></li>
            <li><a className="hover:text-ink" href="/api/docs" onClick={(e) => { e.preventDefault(); window.open(`${import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'}/docs`, '_blank') }}>API documentation</a></li>
          </ul>
        </div>
      </div>
      <p className="mx-auto max-w-[1320px] px-5 pb-8 text-[13px] text-muted md:px-8">
        Photographs via Wikimedia Commons: <a className="underline" href="https://commons.wikimedia.org/w/index.php?curid=31360367" target="_blank" rel="noreferrer">“Street Newspaper Reading - Manicktala - Kolkata”</a> by Biswarup Ganguly, CC BY 3.0;{' '}
        <a className="underline" href="https://commons.wikimedia.org/w/index.php?curid=88731857" target="_blank" rel="noreferrer">“Safe Newspaper Vendor”</a> by Vaikunda Raja, CC BY-SA 4.0;{' '}
        <a className="underline" href="https://commons.wikimedia.org/w/index.php?curid=37047186" target="_blank" rel="noreferrer">“Assam tribune picture”</a> by Vikramjit Kakati, CC BY-SA 4.0.
      </p>
    </footer>
  )
}
