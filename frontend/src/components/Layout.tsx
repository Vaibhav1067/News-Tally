import { NavLink, Link, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Menu, X } from 'lucide-react'

const API_DOCS = `${import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'}/docs`

export function Mark({ className = 'size-6' }: { className?: string }) {
  // Four tally strokes; the fifth stroke is a tick. Master file: brand/news-tally-mark.svg
  return (
    <svg viewBox="16 40 232 176" className={className} aria-hidden>
      <g fill="#111111"><rect x="62" y="52" width="20" height="152" /><rect x="104" y="52" width="20" height="152" /><rect x="146" y="52" width="20" height="152" /><rect x="188" y="52" width="20" height="152" /></g>
      <path d="M22 150 L70 192 L234 78" fill="none" stroke="#d42b2b" strokeWidth="22" />
    </svg>
  )
}

const LINKS = [
  { to: '/analyze', label: 'Check a claim' },
  { to: '/explorer', label: 'Fact-checks' },
  { to: '/map', label: 'India map' },
  { to: '/intelligence', label: 'Dataset' },
  { to: '/methodology', label: 'Methodology' },
]

export function Layout() {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => { setOpen(false); window.scrollTo(0, 0) }, [loc.pathname])

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:bg-surface focus:px-3 focus:py-2">Skip to content</a>
      <header className="sticky top-0 z-40 border-b border-border bg-ground">
        <div className="mx-auto flex h-12 max-w-[1160px] items-center gap-8 px-5 md:px-8">
          <Link to="/" className="flex items-center gap-2" aria-label="News Tally home">
            <Mark className="h-[22px] w-[29px]" />
            <span className="font-serif text-[19px] leading-none font-semibold tracking-[-0.01em]">News Tally</span>
          </Link>
          <nav aria-label="Primary" className="hidden h-full items-center gap-6 md:flex">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to}
                className={({ isActive }) => `sel-line flex h-full items-center text-[14px] font-medium transition-colors ${isActive ? 'text-ink' : 'text-muted hover:text-ink'}`}
                data-active={loc.pathname.startsWith(l.to)}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <a href={API_DOCS} target="_blank" rel="noreferrer" className="hidden text-[14px] font-medium text-muted hover:text-ink sm:block">API</a>
            <button className="grid size-9 place-items-center rounded-ctl text-ink md:hidden" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
          </div>
        </div>
        {open && (
          <nav aria-label="Mobile" className="border-t border-border bg-ground px-5 pb-3 md:hidden">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} className={({ isActive }) => `block py-3 text-[15px] ${isActive ? 'font-semibold text-ink' : 'text-muted'}`}>{l.label}</NavLink>
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
    <footer className="mt-20 border-t border-border bg-surface">
      <div className="mx-auto grid max-w-[1160px] gap-8 px-5 py-10 text-[13px] md:grid-cols-[1.2fr_1fr_1fr] md:px-8">
        <div>
          <div className="flex items-center gap-2"><Mark className="h-5 w-[26px]" /><span className="font-serif text-[17px] font-semibold">News Tally</span></div>
          <p className="mt-3 max-w-sm text-muted">A lookup tool. It shows published fact-checks and model signals for a claim; it does not decide what is true.</p>
        </div>
        <div>
          <h3 className="font-semibold">Fact-check data</h3>
          <p className="mt-2 text-muted">Headlines, claims and one-sentence conclusions from <a className="text-ink underline underline-offset-2" href="https://factly.in" target="_blank" rel="noreferrer">Factly</a> and <a className="text-ink underline underline-offset-2" href="https://www.altnews.in" target="_blank" rel="noreferrer">Alt News</a>, collected from their public WordPress APIs. Every record links to the original article.</p>
        </div>
        <div>
          <h3 className="font-semibold">Project</h3>
          <ul className="mt-2 space-y-1 text-muted">
            <li><Link className="hover:text-ink" to="/methodology">Methodology and limitations</Link></li>
            <li><Link className="hover:text-ink" to="/intelligence">Dataset statistics</Link></li>
            <li><a className="hover:text-ink" href={API_DOCS} target="_blank" rel="noreferrer">API documentation</a></li>
          </ul>
        </div>
      </div>
      <p className="mx-auto max-w-[1160px] px-5 pb-8 text-[12px] text-muted md:px-8">
        Photograph: <a className="underline" href="https://commons.wikimedia.org/w/index.php?curid=31360367" target="_blank" rel="noreferrer">“Street Newspaper Reading - Manicktala - Kolkata”</a> by Biswarup Ganguly, CC BY 3.0, via Wikimedia Commons.
      </p>
    </footer>
  )
}
