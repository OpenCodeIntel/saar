import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Copy, CheckCircle, GithubLogo, ArrowRight,
  X, Check, ArrowsLeftRight,
  Terminal, Stack, ShieldCheck, FileText, Code, Lightning
} from '@phosphor-icons/react'

// ── Scroll reveal hook ──────────────────────────────────────────────────────
function useReveal() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) el.classList.add('visible') },
      { threshold: 0.15 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return ref
}

// ── Copy button ─────────────────────────────────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy} className="copy-btn px-3 py-1.5 rounded-md font-mono text-xs flex items-center gap-1.5">
      {copied ? <CheckCircle size={12} weight="fill" /> : <Copy size={12} />}
      {copied ? 'copied' : 'copy'}
    </button>
  )
}

// ── Nav ──────────────────────────────────────────────────────────────────────
function Nav() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', fn)
    return () => window.removeEventListener('scroll', fn)
  }, [])
  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${scrolled ? 'backdrop-blur-md border-b border-white/5' : ''}`}
      style={scrolled ? { background: 'rgba(8,12,20,0.92)' } : {}}>
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <span className="font-serif italic text-xl text-amber-saar tracking-tight">saar</span>
        <div className="flex items-center gap-6">
          <a href="https://github.com/OpenCodeIntel/saar" target="_blank" rel="noopener noreferrer"
            className="text-cream-muted hover:text-cream text-sm transition-colors flex items-center gap-2">
            <GithubLogo size={15} weight="fill" />
            GitHub
          </a>
          <a href="#install"
            className="bg-amber-saar text-navy-900 text-sm font-medium px-4 py-1.5 rounded-full hover:bg-amber-400 transition-colors">
            Install
          </a>
        </div>
      </div>
    </nav>
  )
}

// ── Hero ────────────────────────────────────────────────────────────────────
function Hero() {
  const [typed, setTyped] = useState('')
  const [showOutput, setShowOutput] = useState(false)
  const cmd = 'saar extract .'

  useEffect(() => {
    let i = 0
    const delay = setTimeout(() => {
      const t = setInterval(() => {
        setTyped(cmd.slice(0, i + 1))
        i++
        if (i >= cmd.length) {
          clearInterval(t)
          setTimeout(() => setShowOutput(true), 400)
        }
      }, 60)
      return () => clearInterval(t)
    }, 800)
    return () => clearTimeout(delay)
  }, [])

  return (
    <section className="min-h-screen grid-bg flex flex-col items-center justify-center px-6 pt-24 pb-16 relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full blur-3xl pointer-events-none" style={{ background: 'rgba(244,195,67,0.05)' }} />

      <div className="max-w-4xl mx-auto text-center relative z-10">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 mb-10"
          style={{ border: '1px solid rgba(244,195,67,0.2)', background: 'rgba(244,195,67,0.07)' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-amber-saar animate-pulse" />
          <span className="text-amber-saar text-xs font-mono tracking-widest uppercase">Open Source · PyPI</span>
        </div>

        {/* The headline — this is the unforgettable moment */}
        <h1 className="display-headline text-cream mb-6"
          style={{ fontSize: 'clamp(52px, 9vw, 112px)' }}>
          Your AI is<br />
          <span className="text-amber-saar">guessing.</span>
        </h1>

        <p className="text-cream-muted text-lg md:text-xl max-w-xl mx-auto mb-12 leading-relaxed font-light">
          Every coding assistant gives you generic answers.<br />
          <span className="text-cream">saar tells it what your codebase actually needs.</span>
        </p>

        {/* Terminal demo */}
        <div className="terminal max-w-lg mx-auto mb-10 text-left">
          <div className="terminal-bar">
            <div className="terminal-dot bg-[#FF5F57]" />
            <div className="terminal-dot bg-[#FEBC2E]" />
            <div className="terminal-dot bg-[#28C840]" />
            <span className="ml-2 text-cream-dim text-xs font-mono">terminal</span>
          </div>
          <div className="p-5 font-mono text-sm space-y-2">
            <p className="text-cream-muted">
              <span className="text-amber-saar">$</span>{' '}
              <span className="text-cream">{typed}</span>
              {typed.length < cmd.length && <span className="cursor" />}
            </p>
            {showOutput && (
              <div className="space-y-1.5 animate-fade-up">
                <p className="text-cream-dim">Analyzing <span className="text-cream">694 functions</span>...</p>
                <p className="text-cream-dim">Detected: <span className="text-amber-saar">bun</span>, <span className="text-amber-saar">structlog</span>, <span className="text-amber-saar">JwtAuthGuard</span></p>
                <p className="text-cream-dim">Writing <span className="text-cream">AGENTS.md</span>...</p>
                <p className="font-medium flex items-center gap-1.5" style={{ color: '#4EFF9A' }}>
                  <Check size={13} weight="bold" />
                  Done. Your AI knows your project.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Install */}
        <div id="install" className="flex items-center justify-center gap-3 flex-wrap">
          <div className="terminal flex items-center gap-3 px-5 py-3">
            <span className="text-cream-muted font-mono text-sm">pip install saar</span>
            <CopyButton text="pip install saar" />
          </div>
          <a href="https://github.com/OpenCodeIntel/saar" target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 text-cream-muted text-sm hover:text-cream transition-colors">
            View on GitHub <ArrowRight size={14} weight="bold" />
          </a>
        </div>

        {/* Supported by */}
        <p className="text-cream-dim text-xs font-mono mt-8 tracking-wider uppercase">
          Works with Claude Code · Cursor · claude.ai · GitHub Copilot
        </p>
      </div>
    </section>
  )
}

// ── The Proof — draggable split screen ──────────────────────────────────────
function TheProof() {
  const [splitPos, setSplitPos] = useState(50)
  const isDragging = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const ref = useReveal()

  const getX = useCallback((clientX: number) => {
    if (!containerRef.current) return 50
    const rect = containerRef.current.getBoundingClientRect()
    return Math.max(5, Math.min(95, ((clientX - rect.left) / rect.width) * 100))
  }, [])

  const onMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging.current) return
    setSplitPos(getX(e.clientX))
  }, [getX])

  const onMouseUp = useCallback(() => { isDragging.current = false }, [])

  const onTouchMove = useCallback((e: TouchEvent) => {
    if (!isDragging.current || !e.touches[0]) return
    e.preventDefault()
    setSplitPos(getX(e.touches[0].clientX))
  }, [getX])

  const onTouchEnd = useCallback(() => { isDragging.current = false }, [])

  useEffect(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    window.addEventListener('touchmove', onTouchMove, { passive: false })
    window.addEventListener('touchend', onTouchEnd)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      window.removeEventListener('touchmove', onTouchMove)
      window.removeEventListener('touchend', onTouchEnd)
    }
  }, [onMouseMove, onMouseUp, onTouchMove, onTouchEnd])

  const startDrag = () => { isDragging.current = true }

  return (
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div ref={ref} className="reveal text-center mb-12">
          <div className="section-divider" />
          <p className="text-cream-muted font-mono text-xs tracking-widest uppercase mb-3">The proof</p>
          <h2 className="display-headline text-cream mb-4" style={{ fontSize: 'clamp(36px, 5vw, 60px)' }}>
            You've seen this before.
          </h2>
          <p className="text-cream-muted max-w-md mx-auto">
            Drag the handle. Watch the difference between an AI that's guessing and one that knows.
          </p>
        </div>

        {/* Draggable split — uses width+overflow, not clipPath, so content stays contained */}
        <div
          ref={containerRef}
          className="relative rounded-xl overflow-hidden border border-white/5 select-none"
          style={{ height: '400px', cursor: 'col-resize' }}
          onMouseDown={startDrag}
          onTouchStart={startDrag}
        >
          {/* LEFT panel — wrong answer */}
          <div
            className="absolute top-0 left-0 bottom-0 overflow-hidden"
            style={{ width: `${splitPos}%` }}
          >
            <div className="h-full w-full flex flex-col">
              <div className="bg-[#1A0A0A] px-4 py-2 border-b border-red-900/30 flex items-center justify-between shrink-0">
                <span style={{ color: 'rgba(255,78,78,0.7)' }} className="text-xs font-mono">Without saar</span>
                <span style={{ color: 'rgba(255,78,78,0.5)' }} className="text-xs whitespace-nowrap">AI is guessing</span>
              </div>
              <div className="flex-1 p-5 font-mono text-sm space-y-3 overflow-hidden" style={{ background: '#0D0404' }}>
                <p className="text-xs" style={{ color: 'rgb(158,154,146)' }}>You asked: "Add the date-fns library"</p>
                <div className="rounded-lg p-4 space-y-2" style={{ background: '#1A0808', border: '1px solid rgba(180,0,0,0.2)' }}>
                  <p className="text-xs" style={{ color: 'rgb(90,87,80)' }}>Searched for lockfiles... found package.json</p>
                  <p style={{ color: 'rgb(232,227,217)' }}>Uses <span className="line-through" style={{ color: '#FF4E4E' }}>npm</span>:</p>
                  <div className="px-3 py-2 rounded font-mono text-xs whitespace-nowrap" style={{ color: '#FF7777', background: '#200000' }}>
                    npm install date-fns
                  </div>
                  <p className="text-xs flex items-center gap-1" style={{ color: 'rgb(90,87,80)' }}>
                    <X size={11} weight="bold" color="#FF4E4E" />
                    Project uses bun. Build will fail.
                  </p>
                </div>
                <p className="text-xs italic" style={{ color: 'rgba(255,78,78,0.5)' }}>Claude missed bun.lock entirely</p>
              </div>
            </div>
          </div>

          {/* RIGHT panel — correct answer */}
          <div
            className="absolute top-0 right-0 bottom-0 overflow-hidden"
            style={{ left: `${splitPos}%` }}
          >
            <div className="h-full w-full flex flex-col">
              <div className="bg-[#071A0F] px-4 py-2 border-b border-green-900/30 flex items-center justify-between shrink-0">
                <span style={{ color: 'rgba(78,255,154,0.7)' }} className="text-xs font-mono">With saar</span>
                <span style={{ color: 'rgba(78,255,154,0.5)' }} className="text-xs whitespace-nowrap">AI knows your codebase</span>
              </div>
              <div className="flex-1 p-5 font-mono text-sm space-y-3 overflow-hidden" style={{ background: '#040D06' }}>
                <p className="text-xs" style={{ color: 'rgb(158,154,146)' }}>You asked: "Add the date-fns library"</p>
                <div className="rounded-lg p-4 space-y-2" style={{ background: '#071508', border: '1px solid rgba(0,160,60,0.2)' }}>
                  <p className="text-xs" style={{ color: 'rgb(90,87,80)' }}>AGENTS.md: package manager is bun</p>
                  <p style={{ color: 'rgb(232,227,217)' }}>Uses <span style={{ color: '#4EFF9A' }}>bun</span>:</p>
                  <div className="px-3 py-2 rounded font-mono text-xs whitespace-nowrap" style={{ color: '#4EFF9A', background: '#001200' }}>
                    bun add date-fns
                  </div>
                  <p className="text-xs flex items-center gap-1" style={{ color: 'rgb(90,87,80)' }}>
                    <Check size={11} weight="bold" color="#4EFF9A" />
                    Correct. Build succeeds.
                  </p>
                </div>
                <p className="text-xs italic" style={{ color: 'rgba(78,255,154,0.5)' }}>Zero file exploration needed</p>
              </div>
            </div>
          </div>

          {/* Drag handle */}
          <div
            className="absolute top-0 bottom-0 z-20 flex items-center justify-center"
            style={{ left: `${splitPos}%`, transform: 'translateX(-50%)', width: '2px', background: 'rgba(244,195,67,0.7)' }}
          >
            <div className="w-9 h-9 rounded-full flex items-center justify-center shadow-lg"
              style={{ background: '#080C14', border: '2px solid #F4C343' }}>
              <ArrowsLeftRight size={14} weight="bold" color="#F4C343" />
            </div>
          </div>
        </div>

        <p className="text-center text-cream-dim text-sm mt-4 font-mono flex items-center justify-center gap-2">
          <ArrowsLeftRight size={14} weight="bold" />
          drag to compare
        </p>
      </div>
    </section>
  )
}

// ── How it works ────────────────────────────────────────────────────────────
function StepCard({ step, title, code, desc }: { step: string; title: string; code: string; desc: string }) {
  const r = useReveal()
  return (
    <div ref={r} className="reveal feature-card rounded-xl p-6">
      <span className="font-mono text-xs" style={{ color: 'rgba(244,195,67,0.4)' }}>{step}</span>
      <h3 className="text-cream font-medium mt-3 mb-3">{title}</h3>
      <div className="terminal mb-4">
        <div className="p-3 font-mono text-xs text-cream-muted">
          <span className="text-amber-saar">$</span> {code}
        </div>
      </div>
      <p className="text-cream-muted text-sm leading-relaxed">{desc}</p>
    </div>
  )
}

function HowItWorks() {
  const ref = useReveal()
  const steps = [
    {
      step: '01',
      title: 'Run saar',
      code: 'saar extract ./my-repo',
      desc: 'Static analysis across your full codebase. 694 functions. Finds what your tools actually use.',
    },
    {
      step: '02',
      title: 'Answer 5 questions',
      code: 'What does your app do in one sentence?',
      desc: 'Guided interview captures tribal knowledge that no static analysis can find. Off-limits files, domain terms, team gotchas.',
    },
    {
      step: '03',
      title: 'Drop in AGENTS.md',
      code: 'git add AGENTS.md && git commit -m "add context"',
      desc: 'Every AI tool reads it automatically. Claude Code, Cursor, claude.ai, Copilot. One file. All tools.',
    },
  ]
  return (
    <section className="py-24 px-6" style={{ background: 'rgba(4,7,15,0.5)' }}>
      <div className="max-w-5xl mx-auto">
        <div ref={ref} className="reveal text-center mb-12">
          <div className="section-divider" />
          <p className="text-cream-muted font-mono text-xs tracking-widest uppercase mb-3">The process</p>
          <h2 className="display-headline text-cream" style={{ fontSize: 'clamp(36px, 5vw, 60px)' }}>
            Ten seconds.<br />One command.
          </h2>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          {steps.map((s) => <StepCard key={s.step} {...s} />)}
        </div>
      </div>
    </section>
  )
}

// ── What it captures ────────────────────────────────────────────────────────
function FeatureCard({ icon: Icon, label, ex }: { icon: React.ElementType; label: string; ex: string }) {
  const r = useReveal()
  return (
    <div ref={r} className="reveal feature-card rounded-xl p-6 group">
      {/* Amber icon on dark navy background — matches the brand */}
      <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-5"
        style={{ background: 'rgba(244,195,67,0.1)', border: '1px solid rgba(244,195,67,0.2)' }}>
        <Icon size={18} weight="duotone" color="rgb(244,195,67)" />
      </div>
      <p className="text-cream text-sm font-medium mb-2">{label}</p>
      <p className="text-cream-dim font-mono text-xs">{ex}</p>
    </div>
  )
}

function WhatItCaptures() {
  const ref = useReveal()
  const items = [
    { icon: Terminal,   label: 'Package manager',    ex: 'bun, pnpm, uv' },
    { icon: Stack,      label: 'Logging library',     ex: 'structlog, winston, pino' },
    { icon: ShieldCheck,label: 'Auth patterns',       ex: 'JwtAuthGuard, Depends(require_auth)' },
    { icon: FileText,   label: 'Naming conventions',  ex: 'kebab-case, snake_case' },
    { icon: Code,       label: 'Exception classes',   ex: '218 custom types, top 10 shown' },
    { icon: Lightning,  label: 'Tribal knowledge',    ex: 'Off-limits files, domain terms' },
  ]
  return (
    <section className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <div ref={ref} className="reveal text-center mb-10">
          <div className="section-divider" />
          <p className="text-cream-muted font-mono text-xs tracking-widest uppercase mb-3">What saar extracts</p>
          <h2 className="display-headline text-cream" style={{ fontSize: 'clamp(36px, 5vw, 60px)' }}>
            Everything your AI<br />was missing.
          </h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {items.map((item) => <FeatureCard key={item.label} {...item} />)}
        </div>
      </div>
    </section>
  )
}

// ── Stats ────────────────────────────────────────────────────────────────────
function StatCard({ n, label, sub }: { n: string; label: string; sub: string }) {
  const r = useReveal()
  return (
    <div ref={r} className="reveal text-center">
      <div className="stat-number mb-2">{n}</div>
      <p className="text-cream text-sm mb-1">{label}</p>
      <p className="text-cream-dim font-mono text-xs">{sub}</p>
    </div>
  )
}

function Stats() {
  const ref = useReveal()
  const stats = [
    { n: '60k+', label: 'open source repos use AGENTS.md', sub: 'Linux Foundation standard' },
    { n: '10s', label: 'to generate your AGENTS.md', sub: 'from cold start' },
    { n: '92/100', label: 'saar scores on its own AGENTS.md', sub: 'we dogfood everything' },
    { n: '548', label: 'tests passing today', sub: 'CI clean' },
  ]
  return (
    <section className="py-24 px-6 overflow-hidden" style={{ background: 'rgba(4,7,15,0.5)' }}>
      <div className="max-w-5xl mx-auto">
        <div ref={ref} className="reveal text-center mb-12">
          <div className="section-divider" />
          <p className="text-cream-muted font-mono text-xs tracking-widest uppercase mb-3">By the numbers</p>
          <h2 className="display-headline text-cream" style={{ fontSize: 'clamp(36px, 5vw, 60px)' }}>
            Built for real teams.<br />Used on real codebases.
          </h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          {stats.map((s) => <StatCard key={s.n} {...s} />)}
        </div>
      </div>
    </section>
  )
}

// ── Saar lint teaser ─────────────────────────────────────────────────────────
function LintTeaser() {
  const ref = useReveal()
  return (
    <section className="py-24 px-6">
      <div className="max-w-4xl mx-auto">
        <div ref={ref} className="reveal">
          <div className="feature-card rounded-2xl p-8 md:p-12">
            <div className="flex flex-col md:flex-row md:items-center gap-8">
              <div className="flex-1">
                <span className="text-amber-saar font-mono text-xs tracking-widest uppercase">New in v0.5.8</span>
                <h3 className="display-headline text-cream mt-3 mb-4" style={{ fontSize: 'clamp(28px, 4vw, 48px)' }}>
                  saar lint
                </h3>
                <p className="text-cream-muted leading-relaxed mb-6">
                  Like ruff, but for your AGENTS.md. Catches duplicate rules, orphaned headers, vague instructions, generic filler, and emojis — with line numbers and fix hints.
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  {['SA001','SA003','SA004'].map(code => (
                    <span key={code} className="font-mono text-xs px-2 py-1 rounded text-amber-saar"
                      style={{ border: '1px solid rgba(244,195,67,0.2)' }}>{code}</span>
                  ))}
                  <span className="text-cream-dim font-mono text-xs">+2 more</span>
                </div>
              </div>
              <div className="terminal w-full md:w-80 shrink-0">
                <div className="terminal-bar">
                  <div className="terminal-dot bg-[#FF5F57]" />
                  <div className="terminal-dot bg-[#FEBC2E]" />
                  <div className="terminal-dot bg-[#28C840]" />
                </div>
                <div className="p-4 font-mono text-xs space-y-2">
                  <p><span className="text-amber-saar">$</span> <span className="text-cream">saar lint .</span></p>
                  <p><span className="text-cream-dim">AGENTS.md:5:1:</span> <span className="text-yellow-400">SA004</span> <span className="text-cream-muted">Generic filler detected</span></p>
                  <p><span className="text-cream-dim">AGENTS.md:12:1:</span> <span className="text-yellow-400">SA001</span> <span className="text-cream-muted">Duplicate rule (line 3)</span></p>
                  <p className="text-[#FF4E4E] pt-1">Found 2 violations.</p>
                  <p className="text-cream-dim pt-1">Run <span className="text-cream">saar stats .</span> for full score.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Final CTA ────────────────────────────────────────────────────────────────
function CTA() {
  const ref = useReveal()
  return (
    <section className="py-32 px-6 text-center relative overflow-hidden">
      <div className="absolute inset-0 grid-bg opacity-50" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[300px] rounded-full blur-3xl pointer-events-none" style={{ background: 'rgba(244,195,67,0.06)' }} />
      <div ref={ref} className="reveal relative z-10 max-w-2xl mx-auto">
        <h2 className="display-headline text-cream mb-6" style={{ fontSize: 'clamp(40px, 7vw, 80px)' }}>
          Your codebase.<br />
          <span className="text-amber-saar">Your rules.</span><br />
          Your AI.
        </h2>
        <p className="text-cream-muted text-lg mb-10">One command. Ten seconds. Your AI finally knows your project.</p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <div className="terminal flex items-center gap-3 px-5 py-3">
            <span className="text-cream-muted font-mono text-sm">pip install saar</span>
            <CopyButton text="pip install saar" />
          </div>
          <a href="https://github.com/OpenCodeIntel/saar" target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-2 text-cream-muted hover:text-cream transition-colors text-sm amber-underline">
            <GithubLogo size={15} weight="fill" /> View on GitHub
          </a>
        </div>
      </div>
    </section>
  )
}

// ── Footer ───────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="border-t border-white/5 py-8 px-6">
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <span className="font-serif italic text-amber-saar">saar</span>
        <div className="flex items-center gap-6 text-cream-dim text-xs font-mono">
          <a href="https://github.com/OpenCodeIntel/saar" target="_blank" rel="noopener noreferrer" className="hover:text-cream transition-colors">GitHub</a>
          <a href="https://pypi.org/project/saar/" target="_blank" rel="noopener noreferrer" className="hover:text-cream transition-colors">PyPI</a>
          <a href="https://github.com/OpenCodeIntel/saar/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="hover:text-cream transition-colors">MIT License</a>
        </div>
        <p className="text-cream-dim text-xs font-mono">open source · getsaar.com</p>
      </div>
    </footer>
  )
}

// ── Root App ─────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <div className="noise">
      <Nav />
      <main>
        <Hero />
        <TheProof />
        <HowItWorks />
        <WhatItCaptures />
        <Stats />
        <LintTeaser />
        <CTA />
      </main>
      <Footer />
    </div>
  )
}
