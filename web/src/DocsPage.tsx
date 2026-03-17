import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { GithubLogo, ArrowLeft, Terminal, Users, Student, GitBranch, Copy, CheckCircle, CaretRight } from '@phosphor-icons/react'

// ── Copy button — with label (for code blocks) ───────────────────────────────
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      className="copy-btn px-2 py-1 rounded text-xs flex items-center gap-1">
      {copied ? <CheckCircle size={11} weight="fill" /> : <Copy size={11} />}
      {copied ? 'copied' : 'copy'}
    </button>
  )
}

// ── Copy icon only — for command rows ────────────────────────────────────────
function CopyIcon({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
      title="Copy"
      className="shrink-0 transition-opacity opacity-40 hover:opacity-100"
      style={{ color: 'rgb(244,195,67)', background: 'none', border: 'none', padding: '2px', cursor: 'pointer' }}
    >
      {copied
        ? <CheckCircle size={14} weight="fill" />
        : <Copy size={14} />
      }
    </button>
  )
}

// ── Code block ───────────────────────────────────────────────────────────────
function Code({ children, copy }: { children: string; copy?: boolean }) {
  return (
    <div className="terminal my-4">
      <div className="terminal-bar justify-between">
        <div className="flex items-center gap-1.5">
          <div className="terminal-dot bg-[#FF5F57]" />
          <div className="terminal-dot bg-[#FEBC2E]" />
          <div className="terminal-dot bg-[#28C840]" />
        </div>
        {copy !== false && <CopyBtn text={children.trim()} />}
      </div>
      <pre className="p-4 font-mono text-xs text-cream-muted overflow-x-auto leading-relaxed">{children}</pre>
    </div>
  )
}

// ── Inline code ───────────────────────────────────────────────────────────────
function IC({ children }: { children: string }) {
  return <code className="font-mono text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(244,195,67,0.1)', color: 'rgb(244,195,67)' }}>{children}</code>
}

// ── Section ───────────────────────────────────────────────────────────────────
function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mb-16 scroll-mt-24">
      <h2 className="display-headline text-cream mb-6" style={{ fontSize: 'clamp(24px, 3vw, 36px)' }}>{title}</h2>
      <div className="space-y-4 text-cream-muted leading-relaxed">{children}</div>
    </section>
  )
}

// ── Callout ────────────────────────────────────────────────────────────────────
function Callout({ type, children }: { type: 'tip' | 'warn' | 'real'; children: React.ReactNode }) {
  const styles = {
    tip:  { bg: 'rgba(78,255,154,0.05)', border: 'rgba(78,255,154,0.2)', color: '#4EFF9A', label: 'Tip' },
    warn: { bg: 'rgba(255,200,50,0.05)', border: 'rgba(255,200,50,0.2)', color: '#F4C343', label: 'Note' },
    real: { bg: 'rgba(244,195,67,0.05)', border: 'rgba(244,195,67,0.2)', color: '#F4C343', label: 'Real example' },
  }
  const s = styles[type]
  return (
    <div className="rounded-xl p-4 my-4" style={{ background: s.bg, border: `1px solid ${s.border}` }}>
      <p className="text-xs font-mono mb-2" style={{ color: s.color }}>{s.label}</p>
      <div className="text-cream-muted text-sm">{children}</div>
    </div>
  )
}

// ── Sidebar nav ───────────────────────────────────────────────────────────────
const NAV = [
  { id: 'install',       label: 'Install' },
  { id: 'quickstart',    label: 'Quick start' },
  { id: 'who-is-it-for', label: 'Who is it for?' },
  { id: 'solo',          label: '→ Solo builder' },
  { id: 'team',          label: '→ Teams' },
  { id: 'student',       label: '→ Students' },
  { id: 'commands',      label: 'Commands' },
  { id: 'output',        label: 'Example output' },
  { id: 'tools',         label: 'AI tools' },
  { id: 'ci',            label: 'CI integration' },
  { id: 'faq',           label: 'FAQ' },
]

function Sidebar({ active }: { active: string }) {
  return (
    <aside className="hidden lg:block w-56 shrink-0">
      <div className="sticky top-24 space-y-1">
        <p className="text-cream-dim font-mono text-xs tracking-widest uppercase mb-4">Docs</p>
        {NAV.map(item => (
          <a key={item.id} href={`#${item.id}`}
            className={`block text-sm py-1 px-2 rounded transition-colors ${
              active === item.id
                ? 'text-amber-saar'
                : item.label.startsWith('→')
                  ? 'text-cream-dim hover:text-cream-muted pl-4'
                  : 'text-cream-muted hover:text-cream'
            }`}>
            {item.label.replace('→ ', '')}
          </a>
        ))}
      </div>
    </aside>
  )
}

// ── Content sections ──────────────────────────────────────────────────────────
function InstallSection() {
  return (
    <Section id="install" title="Install">
      <p>No account. No API key. Your code never leaves your machine.</p>
      <Code copy>{`pip install saar`}</Code>
      <p>Or with pipx (recommended — avoids venv conflicts):</p>
      <Code copy>{`pipx install saar`}</Code>
      <p>Requires Python 3.10+. Works on macOS, Linux, and Windows.</p>
      <Callout type="tip">
        After installing, run <IC>saar --version</IC> to confirm it's working.
      </Callout>
    </Section>
  )
}

function QuickStartSection() {
  return (
    <Section id="quickstart" title="Quick start">
      <p>Navigate to any codebase and run:</p>
      <Code copy>{`cd your-project
saar extract .`}</Code>
      <p>saar will analyze your codebase, ask you 5 quick questions about your project, then write an <IC>AGENTS.md</IC> file in your project root.</p>
      <p>That file is automatically read by Claude Code, Cursor, claude.ai, GitHub Copilot, and Gemini CLI — before they answer your first question.</p>
      <Callout type="real">
        <p className="mb-2">Running on a real FastAPI + React project, saar finds:</p>
        <div className="font-mono text-xs space-y-1">
          <p><span style={{color:'rgb(244,195,67)'}}>Backend</span>     FastAPI  Python (47 files)</p>
          <p><span style={{color:'rgb(244,195,67)'}}>Frontend</span>    React  TypeScript  Vite  bun</p>
          <p><span style={{color:'rgb(244,195,67)'}}>Auth</span>        get_current_active_superuser</p>
          <p><span style={{color:'rgb(244,195,67)'}}>Logging</span>     structlog</p>
          <p><span style={{color:'rgb(244,195,67)'}}>Exceptions</span>  APIError, AuthError, LimitCheckError (+6)</p>
          <p><span style={{color:'rgb(244,195,67)'}}>Scale</span>       694 functions  276 files  96% typed</p>
        </div>
        <p className="mt-2 text-xs">You didn't write any of that. saar found it automatically.</p>
      </Callout>
      <p>Skip the interview questions (use cached answers):</p>
      <Code copy>{`saar extract . --no-interview`}</Code>
    </Section>
  )
}

function WhoIsItForSection() {
  return (
    <Section id="who-is-it-for" title="Who is it for?">
      <p>saar solves different problems for different people. Pick your scenario below.</p>
      <div className="grid sm:grid-cols-3 gap-4 my-6">
        {[
          { icon: Terminal, id: 'solo', label: 'Solo builder', desc: 'You switch between Cursor and Claude Code. Context resets every time.' },
          { icon: Users, id: 'team', label: 'Teams', desc: 'New devs onboard. AI suggests npm in your bun repo. You spend 20 min fixing it.' },
          { icon: Student, id: 'student', label: 'Students', desc: 'Building something new. Want AI to actually understand your project.' },
        ].map(({ icon: Icon, id, label, desc }) => (
          <a key={id} href={`#${id}`} className="feature-card rounded-xl p-5 block hover:no-underline group">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-4"
              style={{ background: 'rgba(244,195,67,0.1)', border: '1px solid rgba(244,195,67,0.2)' }}>
              <Icon size={16} weight="duotone" color="rgb(244,195,67)" />
            </div>
            <p className="text-cream text-sm font-medium mb-1">{label}</p>
            <p className="text-cream-dim text-xs leading-relaxed">{desc}</p>
          </a>
        ))}
      </div>
    </Section>
  )
}

function SoloSection() {
  return (
    <Section id="solo" title="Solo builder">
      <p><strong className="text-cream">The problem:</strong> You use Cursor for most of your work. When you open claude.ai or Claude Code for a specific task, it starts from zero — no idea about your stack, your patterns, your package manager.</p>
      <Callout type="real">
        <p className="font-mono text-xs mb-1">You: "Add the date-fns library to the frontend"</p>
        <p className="font-mono text-xs" style={{color:'#FF4E4E'}}>Claude: cd frontend && npm install date-fns</p>
        <p className="text-xs mt-1">Your project uses bun. The build breaks. You spend 15 minutes confused.</p>
      </Callout>
      <p><strong className="text-cream">The fix:</strong> Run saar once. Commit the AGENTS.md. Every tool you open — Cursor, Claude Code, claude.ai — reads it automatically.</p>
      <Code copy>{`cd your-project
saar extract .
git add AGENTS.md && git commit -m "add AI context"`}</Code>
      <p>Now when you switch tools, they all know:</p>
      <ul className="list-none space-y-1 text-sm ml-4">
        {['Your package manager (bun, not npm)', 'Your logging library (structlog, not logging)', 'Your auth pattern by exact name', 'Your custom exception classes'].map(item => (
          <li key={item} className="flex items-center gap-2">
            <span style={{color:'#4EFF9A'}} className="text-xs">+</span> {item}
          </li>
        ))}
      </ul>
      <Callout type="tip">
        If you use multiple AI tools, run <IC>saar extract . --format all</IC> to generate AGENTS.md, CLAUDE.md, and .cursorrules at once.
      </Callout>
    </Section>
  )
}

function TeamSection() {
  return (
    <Section id="team" title="Teams">
      <p><strong className="text-cream">The problem:</strong> Your team has conventions that AI doesn't know. Every new developer who joins and uses AI tooling gets wrong answers. Every session, someone's AI suggests the wrong package manager, imports the wrong exception class, or uses the wrong auth decorator.</p>
      <Callout type="real">
        <p className="text-xs mb-2">A new developer joins your team. They run Claude Code to add an endpoint. It:</p>
        <ul className="space-y-1 text-xs font-mono">
          <li style={{color:'#FF4E4E'}}>- Creates a new exception class instead of using LimitCheckError</li>
          <li style={{color:'#FF4E4E'}}>- Uses @login_required instead of Depends(get_current_active_user)</li>
          <li style={{color:'#FF4E4E'}}>- Writes npm run dev in the README</li>
        </ul>
        <p className="text-xs mt-2">They spend a day in code review getting it corrected.</p>
      </Callout>
      <p><strong className="text-cream">The fix:</strong> Commit AGENTS.md to the repo. Every developer who clones it gets AI that already knows your conventions on day one.</p>
      <Code copy>{`# One person runs this once
saar extract .
git add AGENTS.md && git commit -m "add AI context"
git push

# Every other developer gets it automatically on clone
git clone your-repo
# AGENTS.md is already there — Claude Code picks it up immediately`}</Code>
      <p>When your codebase changes — new package manager, new auth pattern, new exception classes — saar catches it:</p>
      <Code copy>{`saar diff .`}</Code>
      <Code>{`saar checking your-project...
  AGENTS.md last generated: 14 days ago

  Changed since last extract:
  ~ Package manager changed: npm -> bun
  + New exception class: RateLimitError

  Run saar extract . to update.`}</Code>
      <Callout type="tip">
        Add <IC>saar check .</IC> to your CI pipeline. It exits 1 if AGENTS.md is stale, so nobody accidentally pushes outdated context.
      </Callout>
    </Section>
  )
}

function StudentSection() {
  return (
    <Section id="student" title="Students">
      <p><strong className="text-cream">The problem:</strong> You're building a project for class or a hackathon. You're switching between claude.ai, Cursor, and maybe GitHub Copilot. Every tool gives different answers because none of them know what you've built.</p>
      <p><strong className="text-cream">The fix:</strong> Run saar after setting up your project. It takes 10 seconds.</p>
      <Code copy>{`pip install saar
cd my-project
saar extract .`}</Code>
      <p>Then when you paste questions into claude.ai:</p>
      <ol className="list-decimal list-inside space-y-2 text-sm ml-2">
        <li>Open your <IC>AGENTS.md</IC> file</li>
        <li>Paste its contents at the start of your claude.ai conversation</li>
        <li>Ask your question — Claude now knows your stack</li>
      </ol>
      <Callout type="real">
        <p className="text-xs mb-1">Without AGENTS.md → claude.ai gives generic Next.js answers</p>
        <p className="text-xs">With AGENTS.md → claude.ai knows you use Vite, not Next.js. Bun, not npm. Tailwind, not CSS modules.</p>
      </Callout>
      <Callout type="tip">
        Building something new? Run <IC>saar extract . --no-interview</IC> first to skip the questions, then add corrections as you go with <IC>saar add "rule here"</IC>.
      </Callout>
    </Section>
  )
}

function CommandsSection() {
  const cmds = [
    { cmd: 'saar extract .', desc: 'Analyze codebase and generate AGENTS.md (default)', tag: 'main' },
    { cmd: 'saar extract . --no-interview', desc: 'Skip questions, use cached answers', tag: '' },
    { cmd: 'saar extract . --format all', desc: 'Generate AGENTS.md + CLAUDE.md + .cursorrules', tag: '' },
    { cmd: 'saar extract . --format claude', desc: 'Generate CLAUDE.md only (for Claude Code users)', tag: '' },
    { cmd: 'saar extract . --verbose', desc: 'Remove 100-line cap, show full output', tag: '' },
    { cmd: 'saar extract . --include packages/api', desc: 'Monorepo: only analyze a subdirectory', tag: '' },
    { cmd: 'saar diff .', desc: 'Detect what changed since last extract', tag: 'maintain' },
    { cmd: 'saar add "rule"', desc: 'Add a correction without re-running analysis', tag: '' },
    { cmd: 'saar add --off-limits "billing/"', desc: 'Mark a file/dir as off-limits for AI', tag: '' },
    { cmd: 'saar add --domain "Workspace = tenant"', desc: 'Add domain vocabulary term', tag: '' },
    { cmd: 'saar add --verify "pytest tests/ -v"', desc: 'Set the verification workflow', tag: '' },
    { cmd: 'saar lint .', desc: 'Check AGENTS.md for quality issues (SA001-SA005)', tag: 'quality' },
    { cmd: 'saar stats .', desc: 'Score your AGENTS.md quality (0-100)', tag: '' },
    { cmd: 'saar check .', desc: 'CI check: exits 1 if AGENTS.md stale or incomplete', tag: '' },
  ]
  let lastTag = ''
  return (
    <Section id="commands" title="All commands">
      <div className="space-y-1">
        {cmds.map(({ cmd, desc, tag }) => {
          const showTag = tag && tag !== lastTag
          if (tag) lastTag = tag
          return (
            <div key={cmd}>
              {showTag && (
                <p className="text-amber-saar font-mono text-xs tracking-widest uppercase mt-6 mb-2">{tag}</p>
              )}
              <div className="feature-card rounded-lg p-3 flex items-center gap-3 group">
                <IC>{cmd}</IC>
                <span className="text-cream-dim text-xs flex-1">{desc}</span>
                <CopyIcon text={cmd} />
              </div>
            </div>
          )
        })}
      </div>
    </Section>
  )
}

function OutputSection() {
  const output = `# AGENTS.md -- saar

Generated by saar (getsaar.com).

773 functions, 137 classes, 15% async, 87% type-hinted.
Languages: python (48 files), typescript (4 files)

## Frontend
Stack: React + TypeScript + Vite
Package manager: bun -- always use bun install, never npm/yarn

## Coding Conventions
- Functions: snake_case
- Classes: PascalCase
- Files: snake_case

## Auth
- Protected routes: Depends(get_current_active_user)
- Public routes: no decorator

## Logging
- Use structlog -- never bare print() or import logging

## Exception Classes
APIError, AuthenticationError, LimitCheckError,
TokenExpiredError, RateLimitError (+3 more)

## Tribal Knowledge
- billing/ is frozen until Q3 -- never modify
- "Workspace" means tenant, not a directory
- Run: pytest tests/ -v before any commit`

  return (
    <Section id="output" title="Example output">
      <p>This is what a real AGENTS.md looks like. Short. Precise. No filler.</p>
      <Code copy={false}>{output}</Code>
      <p>saar keeps it under 100 lines by default. ETH Zurich research showed that longer context files actually hurt AI performance. The 100-line cap is intentional.</p>
      <p>Want the full output? Run <IC>saar extract . --verbose</IC>.</p>
    </Section>
  )
}

function ToolsSection() {
  const tools = [
    { name: 'Claude Code', file: 'CLAUDE.md or AGENTS.md', cmd: 'saar extract . --format claude', auto: true },
    { name: 'Cursor', file: '.cursorrules', cmd: 'saar extract . --format cursorrules', auto: true },
    { name: 'claude.ai', file: 'Paste AGENTS.md contents into chat', cmd: 'saar extract .', auto: false },
    { name: 'GitHub Copilot', file: '.github/copilot-instructions.md', cmd: 'saar extract . --format copilot', auto: true },
    { name: 'Gemini CLI', file: 'AGENTS.md', cmd: 'saar extract .', auto: true },
    { name: 'Windsurf', file: '.windsurfrules', cmd: 'saar extract . --format all', auto: true },
  ]
  return (
    <Section id="tools" title="AI tools">
      <p>saar generates context files for every major AI coding tool. Use <IC>--format all</IC> to generate everything at once.</p>
      <div className="space-y-2 my-4">
        {tools.map(t => (
          <div key={t.name} className="feature-card rounded-lg p-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="sm:w-32 shrink-0">
              <p className="text-cream text-sm font-medium">{t.name}</p>
            </div>
            <div className="flex-1">
              <p className="text-cream-dim text-xs font-mono">{t.file}</p>
            </div>
            <div>
              {t.auto
                ? <span className="text-xs px-2 py-0.5 rounded font-mono" style={{background:'rgba(78,255,154,0.1)',color:'#4EFF9A'}}>auto-detected</span>
                : <span className="text-xs px-2 py-0.5 rounded font-mono" style={{background:'rgba(244,195,67,0.1)',color:'#F4C343'}}>paste manually</span>
              }
            </div>
          </div>
        ))}
      </div>
      <Callout type="tip">
        Running <IC>saar extract .</IC> auto-detects which tools you use (based on existing config files in your repo) and generates the right formats automatically.
      </Callout>
    </Section>
  )
}

function CISection() {
  return (
    <Section id="ci" title="CI integration">
      <p>Keep AGENTS.md fresh automatically. Add <IC>saar check</IC> to your CI pipeline.</p>
      <Code copy>{`# .github/workflows/ci.yml
- name: Check AGENTS.md is up to date
  run: |
    pip install saar
    saar check .`}</Code>
      <p><IC>saar check</IC> exits <IC>0</IC> if AGENTS.md is fresh and complete. Exits <IC>1</IC> with a specific message if it's stale or missing sections. This prevents outdated context from silently hurting your AI's answers.</p>
      <Callout type="warn">
        saar check only works if you've run <IC>saar extract .</IC> at least once first — it needs the snapshot to compare against.
      </Callout>
    </Section>
  )
}

function FAQSection() {
  const faqs = [
    {
      q: 'No code files found — what do I do?',
      a: `saar analyzes .py, .js, .jsx, .ts, .tsx, and .sql files. If your project uses a different language, saar won't find anything yet. Check what files are actually in your directory.`,
    },
    {
      q: 'Does saar send my code anywhere?',
      a: 'No. saar runs entirely locally. It reads files from disk and writes AGENTS.md. No network calls, no account, no telemetry.',
    },
    {
      q: 'What if the AI still gives wrong answers after saar?',
      a: 'Use saar add to add corrections. Run: saar add "Never use X, always use Y". Each correction is saved and included next time you regenerate.',
    },
    {
      q: 'My AGENTS.md shows the wrong package manager. Why?',
      a: 'saar detects package manager from lockfiles. If you switched from npm to bun but still have package-lock.json around, saar might get confused. Delete the old lockfile or run saar add "Package manager is bun, not npm".',
    },
    {
      q: 'How often should I re-run saar extract?',
      a: 'When your stack changes significantly — new package manager, new auth pattern, new major library. For smaller changes, use saar add to add corrections without full re-analysis. Run saar diff to see if anything important changed.',
    },
    {
      q: 'Can I edit AGENTS.md manually?',
      a: 'Yes. saar uses SAAR:AUTO-START / SAAR:AUTO-END markers. Content inside those markers is managed by saar. Content outside them is never touched — add your own notes above or below the markers.',
    },
  ]
  return (
    <Section id="faq" title="FAQ">
      <div className="space-y-6">
        {faqs.map(({ q, a }) => (
          <div key={q}>
            <p className="text-cream font-medium mb-2 flex items-start gap-2">
              <CaretRight size={14} weight="bold" className="mt-1 shrink-0 text-amber-saar" />
              {q}
            </p>
            <p className="text-cream-muted text-sm ml-5 leading-relaxed">{a}</p>
          </div>
        ))}
      </div>
    </Section>
  )
}

// ── Main DocsPage ─────────────────────────────────────────────────────────────
export default function DocsPage() {
  const [active, setActive] = useState('install')

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(e => { if (e.isIntersecting) setActive(e.target.id) })
      },
      { rootMargin: '-20% 0px -70% 0px' }
    )
    NAV.forEach(({ id }) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })
    return () => observer.disconnect()
  }, [])

  return (
    <div className="grid-bg min-h-screen" style={{ background: 'rgb(8 12 20)' }}>
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b border-white/5"
        style={{ background: 'rgba(8,12,20,0.95)' }}>
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="text-cream-muted hover:text-cream transition-colors flex items-center gap-1.5 text-sm">
              <ArrowLeft size={14} weight="bold" />
              saar
            </Link>
            <span className="text-cream-dim text-xs">/</span>
            <span className="font-serif italic text-amber-saar">docs</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="https://github.com/OpenCodeIntel/saar" target="_blank" rel="noopener noreferrer"
              className="text-cream-muted hover:text-cream text-sm transition-colors flex items-center gap-2">
              <GithubLogo size={15} weight="fill" />
              GitHub
            </a>
          </div>
        </div>
      </nav>

      {/* Layout */}
      <div className="max-w-6xl mx-auto px-6 pt-28 pb-24">
        <div className="flex gap-12">
          <Sidebar active={active} />

          {/* Main content */}
          <main className="flex-1 min-w-0">
            {/* Header */}
            <div className="mb-16">
              <p className="text-cream-dim font-mono text-xs tracking-widest uppercase mb-4">Documentation</p>
              <h1 className="display-headline text-cream mb-4" style={{ fontSize: 'clamp(36px, 5vw, 56px)' }}>
                saar docs
              </h1>
              <p className="text-cream-muted text-lg max-w-xl">
                Everything you need to get your AI coding assistant to actually understand your codebase.
              </p>
            </div>

            <InstallSection />
            <QuickStartSection />
            <WhoIsItForSection />
            <SoloSection />
            <TeamSection />
            <StudentSection />
            <CommandsSection />
            <OutputSection />
            <ToolsSection />
            <CISection />
            <FAQSection />

            {/* Footer CTA */}
            <div className="feature-card rounded-2xl p-8 text-center mt-8">
              <h3 className="display-headline text-cream mb-3" style={{ fontSize: '28px' }}>
                Still stuck?
              </h3>
              <p className="text-cream-muted text-sm mb-6">Open an issue on GitHub. We respond fast.</p>
              <a href="https://github.com/OpenCodeIntel/saar/issues" target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm px-5 py-2.5 rounded-full font-medium transition-colors"
                style={{ background: 'rgb(244,195,67)', color: 'rgb(8,12,20)' }}>
                <GithubLogo size={15} weight="fill" />
                Open an issue
              </a>
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
