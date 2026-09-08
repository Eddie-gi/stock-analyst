'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  BellRing,
  Bot,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  FileText,
  Newspaper,
  Radar,
  RefreshCw,
  SearchCheck,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type NewsItem = { title: string; url: string; publisher: string; published_at?: string | null };
type FilingItem = { form: string; filed_at: string; description: string; url: string };
type Holding = {
  ticker: string;
  name: string;
  currency: string;
  price: number | null;
  change_pct: number | null;
  return_20d_pct: number | null;
  ema20: number | null;
  ema50: number | null;
  rsi14: number | null;
  atr_pct: number | null;
  volume_ratio: number | null;
  market_cap: number | null;
  next_earnings: string | null;
  earnings_days: number | null;
  chart: { date: string; close: number }[];
  news: NewsItem[];
  filings: FilingItem[];
  errors: string[];
  signal_score: number;
  stance: string;
  risk_level: string;
  rationale: string[];
  catalysts: { type: string; date: string; label: string }[];
};
type Candidate = Holding & {
  setup_score: number;
  thesis: string[];
  entry_zone: [number, number];
  model_target: number;
  model_stop: number;
  modeled_upside_pct: number;
  reward_risk_ratio: number | null;
  horizon: string;
  target_note: string;
  research_allocation_cap_pct?: number;
  risk_flags?: string[];
};
export type Report = {
  schema_version: number;
  run_id: string;
  generated_at: string;
  is_demo: boolean;
  market: { session: string; as_of_et: string; next_scheduled_refresh: string };
  summary: { headline: string; detail: string; risk_level: string; constructive_count: number; holdings_count: number; candidate_count: number; disclaimer: string };
  quality: { score: number; source_count: number; price_coverage_pct: number; news_coverage_pct: number; provider_warning_count: number; provider_warnings: string[]; age_minutes: number; stale: boolean; warnings: string[] };
  risk: { level: string; high_risk_tickers: string[]; earnings_cluster: string[]; notes: string[] };
  alerts: { ticker: string; severity: string; type: string; title: string; detail: string; date?: string; url?: string }[];
  portfolio: Holding[];
  candidates: Candidate[];
  agents: { id: string; label: string; status: string; duration_ms: number; summary: string }[];
  sources: { name: string; url: string; cost: string; covers: string }[];
};

type ModelContext = {
  registerTool: (tool: Record<string, unknown>, options?: { signal?: AbortSignal }) => void | Promise<void>;
};

declare global {
  interface Document { modelContext?: ModelContext }
}

export function Dashboard({ initialData }: { initialData: Report }) {
  const [report, setReport] = useState<Report>(initialData);
  const [selectedTicker, setSelectedTicker] = useState(initialData.portfolio[0]?.ticker ?? '');
  const [refreshing, setRefreshing] = useState(false);
  const selected = useMemo(
    () => report.portfolio.find((item) => item.ticker === selectedTicker) ?? report.portfolio[0],
    [report.portfolio, selectedTicker],
  );

  const reload = async () => {
    setRefreshing(true);
    try {
      const endpoints = [
        `https://raw.githubusercontent.com/Eddie-gi/stock-analyst/main/public/data/latest.json?ts=${Date.now()}`,
        `./data/latest.json?ts=${Date.now()}`,
      ];
      let next: Report | undefined;
      for (const endpoint of endpoints) {
        try {
          const response = await fetch(endpoint, { cache: 'no-store' });
          if (response.ok) {
            next = (await response.json()) as Report;
            break;
          }
        } catch {
          // Try the bundled snapshot when the remote source is not reachable.
        }
      }
      if (!next) throw new Error('No report endpoint was reachable.');
      setReport(next);
      if (!next.portfolio.some((item) => item.ticker === selectedTicker)) setSelectedTicker(next.portfolio[0]?.ticker ?? '');
    } catch {
      // Keep the last known-good bundled report visible.
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const context = document.modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    const register = async () => {
      await context.registerTool({
        name: 'get_portfolio_briefing',
        title: 'Get portfolio briefing',
        description: 'Read the current Signal Desk summary, alert list, and data-quality status.',
        inputSchema: { type: 'object', properties: {}, additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: true },
        execute: () => ({ summary: report.summary, alerts: report.alerts, quality: report.quality }),
      }, { signal: lifecycle.signal });
      await context.registerTool({
        name: 'get_ticker_research',
        title: 'Get ticker research',
        description: 'Read the latest signals, catalysts, news, and filings for one ticker in the monitored portfolio.',
        inputSchema: { type: 'object', properties: { ticker: { type: 'string', description: 'US ticker symbol, such as NVDA.' } }, required: ['ticker'], additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: true },
        execute: (input: unknown) => {
          const rawTicker = (input as { ticker?: unknown })?.ticker;
          if (typeof rawTicker !== 'string') throw new Error('ticker must be a string.');
          const ticker = rawTicker.trim().toUpperCase();
          const item = report.portfolio.find((holding) => holding.ticker === ticker);
          if (!item) throw new Error(`Ticker ${ticker || '(blank)'} is not in this report.`);
          return item;
        },
      }, { signal: lifecycle.signal });
    };
    void register().catch(() => undefined);
    return () => lifecycle.abort();
  }, [report]);

  const generatedLabel = formatDateTime(report.generated_at);
  const freshness = report.is_demo ? 'Example data' : report.quality.stale ? 'Stale report' : 'Current report';

  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-white/8 bg-[#07111f]/92 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1520px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-300"><Radar className="h-[18px] w-[18px]" /></div>
            <div className="min-w-0"><p className="truncate text-base font-semibold tracking-tight">Signal Desk</p><p className="hidden text-xs text-slate-400 sm:block">Automated premarket intelligence</p></div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className={`hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs sm:flex ${report.quality.stale || report.is_demo ? 'border-amber-300/20 bg-amber-300/8 text-amber-200' : 'border-emerald-300/15 bg-emerald-300/8 text-emerald-300'}`}><span className={`h-1.5 w-1.5 rounded-full ${report.quality.stale || report.is_demo ? 'bg-amber-300' : 'animate-pulse bg-emerald-300'}`} />{freshness}</div>
            <Button variant="outline" size="icon-lg" onClick={() => void reload()} disabled={refreshing} aria-label="Reload latest report"><RefreshCw className={refreshing ? 'animate-spin' : ''} /></Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1520px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <section className="mb-6 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
          <div className="max-w-4xl">
            <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-cyan-300"><span className="flex items-center gap-2"><Clock3 className="h-4 w-4" /> Premarket briefing · {generatedLabel}</span><span className="text-slate-600">•</span><span className="capitalize text-slate-400">US market {report.market.session}</span></div>
            <h1 className="text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">{report.summary.headline}</h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-slate-400">{report.summary.detail}</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-400"><ShieldCheck className="h-4 w-4 text-emerald-300" />{report.quality.source_count} evidence points · quality {report.quality.score}%</div>
        </section>

        {report.is_demo && <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-300/20 bg-amber-300/8 px-4 py-3 text-sm text-amber-100"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><p>This is the bundled example report. The automated refresh replaces it with current source-linked data.</p></div>}

        <Tabs defaultValue="overview" className="gap-5">
          <TabsList variant="line" className="h-auto max-w-full justify-start overflow-x-auto border-b border-white/8 pb-2">
            <TabsTrigger value="overview" className="px-3 py-2">Overview</TabsTrigger><TabsTrigger value="portfolio" className="px-3 py-2">Portfolio</TabsTrigger><TabsTrigger value="research" className="px-3 py-2">Research queue</TabsTrigger><TabsTrigger value="sources" className="px-3 py-2">Sources & agents</TabsTrigger>
          </TabsList>
          <TabsContent value="overview"><Overview report={report} selected={selected} onSelect={setSelectedTicker} /></TabsContent>
          <TabsContent value="portfolio"><PortfolioView report={report} selected={selected} onSelect={setSelectedTicker} /></TabsContent>
          <TabsContent value="research"><ResearchQueue candidates={report.candidates} /></TabsContent>
          <TabsContent value="sources"><SourcesAndAgents report={report} /></TabsContent>
        </Tabs>

        <p className="mt-6 border-t border-white/8 pt-5 text-xs leading-5 text-slate-500">{report.summary.disclaimer} Market data can be delayed or incomplete. Verify linked primary sources before trading.</p>
      </div>
    </main>
  );
}

function Overview({ report, selected, onSelect }: { report: Report; selected?: Holding; onSelect: (ticker: string) => void }) {
  const alerts = report.alerts.slice(0, 4);
  return <div className="grid gap-4 xl:grid-cols-[1.35fr_.78fr]">
    <div className="grid gap-4"><section className="panel overflow-hidden"><PanelHeader eyebrow="Portfolio monitor" title="Long-term holdings" icon={<Activity />} aside={`${report.portfolio.length} monitored`} /><PortfolioTable holdings={report.portfolio} selectedTicker={selected?.ticker} onSelect={onSelect} /></section>{selected && <TickerSnapshot holding={selected} />}</div>
    <aside className="grid content-start gap-4"><section className="panel p-5"><div className="mb-4 flex items-center justify-between"><div><p className="eyebrow">Priority queue</p><h2 className="mt-1 text-lg font-semibold">Alerts</h2></div><BellRing className="h-5 w-5 text-amber-200" /></div>{alerts.length ? <div className="grid gap-3">{alerts.map((alert, index) => <AlertCard key={`${alert.ticker}-${alert.type}-${index}`} alert={alert} />)}</div> : <EmptyState icon={<CheckCircle2 />} title="No rule-based alerts" detail="The latest run found no earnings, volume, price, or filing trigger above the configured thresholds." />}</section>
      <section className="panel p-5"><div className="flex items-center gap-2 text-violet-300"><Sparkles className="h-4 w-4" /><p className="eyebrow !text-violet-300">Swing screener</p></div>{report.candidates[0] ? <><div className="mt-4 flex items-end justify-between gap-4"><div><p className="text-sm text-slate-400">Top research candidate</p><h2 className="mt-1 text-3xl font-semibold">{report.candidates[0].ticker}</h2></div><Score value={report.candidates[0].setup_score} /></div><p className="mt-4 text-sm leading-6 text-slate-300">{report.candidates[0].thesis[0] ?? 'Review the complete data card before forming a view.'}</p><div className="mt-5 grid grid-cols-3 gap-2"><Metric label="RSI" value={formatNumber(report.candidates[0].rsi14, 0)} /><Metric label="ATR" value={formatPercent(report.candidates[0].atr_pct)} /><Metric label="Earnings" value={formatDays(report.candidates[0].earnings_days)} /></div></> : <EmptyState icon={<SearchCheck />} title="No qualifying setup" detail="No ticker passed the current market-cap and data-completeness filters." />}</section>
    </aside>
  </div>;
}

function PortfolioView({ report, selected, onSelect }: { report: Report; selected?: Holding; onSelect: (ticker: string) => void }) {
  return <div className="grid gap-4 xl:grid-cols-[1.15fr_.85fr]"><section className="panel overflow-hidden"><PanelHeader eyebrow="Signal matrix" title="All monitored holdings" icon={<BarChart3 />} aside="Select a ticker for evidence" /><PortfolioTable holdings={report.portfolio} selectedTicker={selected?.ticker} onSelect={onSelect} detailed /></section>{selected ? <EvidencePanel holding={selected} /> : <div className="panel p-6"><EmptyState icon={<Database />} title="No ticker selected" detail="Choose a monitored holding to see its sources." /></div>}</div>;
}

function ResearchQueue({ candidates }: { candidates: Candidate[] }) {
  return candidates.length ? <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">{candidates.map((candidate, index) => <article key={candidate.ticker} className="panel p-5"><div className="flex items-start justify-between gap-4"><div className="flex items-center gap-3"><span className="rank">{index + 1}</span><div><p className="text-2xl font-semibold">{candidate.ticker}</p><p className="text-sm text-slate-500">{formatMarketCap(candidate.market_cap)}</p></div></div><Score value={candidate.setup_score} /></div><div className="my-5 grid grid-cols-3 gap-2"><Metric label="Entry model" value={`${formatCurrency(candidate.entry_zone[0])}–${formatCurrency(candidate.entry_zone[1])}`} compact /><Metric label="Target" value={formatCurrency(candidate.model_target)} compact /><Metric label="Risk line" value={formatCurrency(candidate.model_stop)} compact /></div><div className="grid gap-2.5">{candidate.thesis.slice(0, 3).map((line) => <p key={line} className="flex gap-2 text-sm leading-5 text-slate-300"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />{line}</p>)}</div><div className="mt-5 border-t border-white/8 pt-4 text-xs leading-5 text-slate-500">{candidate.target_note} Allocation cap: {candidate.research_allocation_cap_pct ?? '—'}% research heuristic.</div></article>)}</div> : <div className="panel p-8"><EmptyState icon={<SearchCheck />} title="No qualifying mega-cap setup" detail="The screener requires price history and a market cap above the configured $1T threshold." /></div>;
}

function SourcesAndAgents({ report }: { report: Report }) {
  return <div className="grid gap-4 xl:grid-cols-[.85fr_1.15fr]"><div className="grid content-start gap-4"><section className="panel p-5"><div className="flex items-start justify-between gap-4"><div><p className="eyebrow">Trust layer</p><h2 className="mt-1 text-lg font-semibold">Data quality</h2></div><Score value={report.quality.score} /></div><div className="mt-5 grid grid-cols-2 gap-2"><Metric label="Price coverage" value={`${report.quality.price_coverage_pct}%`} /><Metric label="News coverage" value={`${report.quality.news_coverage_pct}%`} /></div><div className="mt-4 grid gap-2">{(report.quality.warnings.length ? report.quality.warnings : ['No coverage warning in the latest run.']).map((warning) => <p key={warning} className="text-sm leading-6 text-slate-400">{warning}</p>)}</div></section><section className="panel p-5"><p className="eyebrow">Free data sources</p><div className="mt-4 grid gap-3">{report.sources.map((source) => <a key={source.name} href={source.url} target="_blank" rel="noreferrer" className="group rounded-xl border border-white/8 bg-white/[0.025] p-4 transition hover:border-cyan-300/25 hover:bg-cyan-300/[0.04]"><div className="flex items-center justify-between"><p className="font-medium">{source.name}</p><ExternalLink className="h-4 w-4 text-slate-500 group-hover:text-cyan-300" /></div><p className="mt-1 text-sm text-slate-400">{source.covers}</p><p className="mt-2 text-xs text-slate-500">{source.cost}</p></a>)}</div></section></div>
    <section className="panel p-5"><div className="flex items-center justify-between"><div><p className="eyebrow">Execution graph</p><h2 className="mt-1 text-lg font-semibold">Agent run</h2></div><Bot className="h-5 w-5 text-cyan-300" /></div><div className="mt-5 grid gap-1">{report.agents.length ? report.agents.map((agent, index) => <div key={agent.id} className="grid grid-cols-[auto_1fr_auto] gap-3"><div className="flex flex-col items-center"><span className="mt-0.5 grid h-7 w-7 place-items-center rounded-full border border-emerald-300/20 bg-emerald-300/10 text-emerald-300"><CheckCircle2 className="h-3.5 w-3.5" /></span>{index < report.agents.length - 1 && <span className="h-full w-px bg-white/8" />}</div><div className="pb-5"><p className="font-medium">{agent.label}</p><p className="mt-1 text-sm leading-5 text-slate-400">{agent.summary}</p></div><p className="pt-1 font-mono text-xs text-slate-500">{agent.duration_ms}ms</p></div>) : <EmptyState icon={<Bot />} title="Agent log pending" detail="Execution timings appear after the first live refresh." />}</div></section>
  </div>;
}

function PortfolioTable({ holdings, selectedTicker, onSelect, detailed = false }: { holdings: Holding[]; selectedTicker?: string; onSelect: (ticker: string) => void; detailed?: boolean }) {
  return <Table><TableHeader><TableRow className="border-white/8 hover:bg-transparent"><TableHead className="pl-5 text-xs text-slate-500">Ticker</TableHead><TableHead className="text-xs text-slate-500">Price</TableHead><TableHead className="text-xs text-slate-500">20D</TableHead>{detailed && <TableHead className="text-xs text-slate-500">RSI / ATR</TableHead>}<TableHead className="text-xs text-slate-500">Signal</TableHead><TableHead className="pr-5 text-right text-xs text-slate-500">View</TableHead></TableRow></TableHeader><TableBody>{holdings.map((holding) => <TableRow key={holding.ticker} data-state={holding.ticker === selectedTicker ? 'selected' : undefined} className="border-white/8 hover:bg-white/[0.035] data-[state=selected]:bg-cyan-300/[0.045]"><TableCell className="pl-5"><div className="flex items-center gap-3"><span className="ticker-mark">{holding.ticker.slice(0, 2)}</span><div><p className="font-semibold">{holding.ticker}</p><p className="text-xs text-slate-500">{holding.stance}</p></div></div></TableCell><TableCell><p className="font-mono text-sm">{formatCurrency(holding.price)}</p><Move value={holding.change_pct} /></TableCell><TableCell><Move value={holding.return_20d_pct} /></TableCell>{detailed && <TableCell><p className="font-mono text-sm">{formatNumber(holding.rsi14, 0)} <span className="text-slate-600">/</span> {formatPercent(holding.atr_pct)}</p></TableCell>}<TableCell><div className="flex min-w-28 items-center gap-2"><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8"><div className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-300" style={{ width: `${holding.signal_score}%` }} /></div><span className="w-7 font-mono text-xs text-slate-400">{holding.signal_score}</span></div></TableCell><TableCell className="pr-5 text-right"><Button variant="ghost" size="icon-sm" onClick={() => onSelect(holding.ticker)} aria-label={`View ${holding.ticker} research`}><ChevronRight /></Button></TableCell></TableRow>)}</TableBody></Table>;
}

function TickerSnapshot({ holding }: { holding: Holding }) {
  return <section className="panel p-5"><div className="grid gap-5 lg:grid-cols-[.9fr_1.1fr]"><div><div className="flex items-center justify-between"><div><p className="eyebrow">Selected research</p><h2 className="mt-1 text-2xl font-semibold">{holding.ticker}</h2></div><Score value={holding.signal_score} /></div><div className="mt-5 grid grid-cols-3 gap-2"><Metric label="RSI" value={formatNumber(holding.rsi14, 0)} /><Metric label="ATR" value={formatPercent(holding.atr_pct)} /><Metric label="Earnings" value={formatDays(holding.earnings_days)} /></div><div className="mt-4 grid gap-2">{holding.rationale.slice(0, 3).map((line) => <p key={line} className="text-sm leading-5 text-slate-400">{line}</p>)}</div></div><div className="min-h-52 rounded-xl border border-white/8 bg-[#071421] p-4"><div className="mb-3 flex items-center justify-between"><p className="text-sm font-medium">Six-month adjusted close</p><p className="font-mono text-xs text-slate-500">{holding.currency}</p></div>{holding.chart.length ? <Sparkline data={holding.chart} /> : <div className="grid h-[170px] place-items-center text-sm text-slate-500">Chart available after a live refresh</div>}</div></div></section>;
}

function Sparkline({ data }: { data: { date: string; close: number }[] }) {
  const values = data.map((item) => item.close);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = Math.max(high - low, 0.0001);
  const points = data.map((item, index) => `${(index / Math.max(data.length - 1, 1)) * 100},${96 - ((item.close - low) / span) * 88}`).join(' ');
  const positive = values.at(-1)! >= values[0];
  return <div><svg viewBox="0 0 100 104" preserveAspectRatio="none" className="h-[150px] w-full" aria-label={`Adjusted close ranged from ${formatCurrency(low)} to ${formatCurrency(high)}`}><title>Six-month adjusted close for the selected ticker</title><defs><linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={positive ? '#67e8f9' : '#fda4af'} stopOpacity="0.22" /><stop offset="100%" stopColor={positive ? '#67e8f9' : '#fda4af'} stopOpacity="0" /></linearGradient></defs><polygon points={`0,104 ${points} 100,104`} fill="url(#spark-fill)" /><polyline points={points} fill="none" stroke={positive ? '#67e8f9' : '#fda4af'} strokeWidth="1.5" vectorEffect="non-scaling-stroke" /></svg><div className="flex justify-between font-mono text-[11px] text-slate-600"><span>{formatCurrency(low)}</span><span>{formatCurrency(high)}</span></div></div>;
}

function EvidencePanel({ holding }: { holding: Holding }) {
  const news = holding.news.slice(0, 5); const filings = holding.filings.slice(0, 4);
  return <section className="panel p-5"><div className="flex items-center justify-between"><div><p className="eyebrow">Evidence room</p><h2 className="mt-1 text-lg font-semibold">{holding.ticker} sources</h2></div><Database className="h-5 w-5 text-cyan-300" /></div><div className="mt-5"><div className="mb-3 flex items-center gap-2"><Newspaper className="h-4 w-4 text-slate-400" /><h3 className="text-sm font-semibold">Recent coverage</h3></div>{news.length ? <div className="grid gap-2">{news.map((item) => <SourceLink key={`${item.url}-${item.title}`} title={item.title} meta={`${item.publisher}${item.published_at ? ` · ${formatDate(item.published_at)}` : ''}`} url={item.url} />)}</div> : <p className="text-sm text-slate-500">No usable news item was returned in this run.</p>}</div><div className="mt-6 border-t border-white/8 pt-5"><div className="mb-3 flex items-center gap-2"><FileText className="h-4 w-4 text-slate-400" /><h3 className="text-sm font-semibold">Recent SEC filings</h3></div>{filings.length ? <div className="grid gap-2">{filings.map((item) => <SourceLink key={item.url} title={`${item.form} · ${item.description}`} meta={item.filed_at} url={item.url} />)}</div> : <p className="text-sm text-slate-500">No matching recent filing was found in the lookback window.</p>}</div></section>;
}

function SourceLink({ title, meta, url }: { title: string; meta: string; url: string }) { return <a href={url} target="_blank" rel="noreferrer" className="group flex items-start justify-between gap-3 rounded-xl border border-white/8 bg-white/[0.02] p-3.5 transition hover:border-cyan-300/20 hover:bg-cyan-300/[0.035]"><div><p className="line-clamp-2 text-sm leading-5 text-slate-200">{title}</p><p className="mt-1 text-xs text-slate-500">{meta}</p></div><ExternalLink className="mt-0.5 h-4 w-4 shrink-0 text-slate-600 group-hover:text-cyan-300" /></a>; }
function PanelHeader({ eyebrow, title, icon, aside }: { eyebrow: string; title: string; icon: React.ReactNode; aside: string }) { return <div className="flex flex-col gap-3 border-b border-white/8 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="eyebrow">{eyebrow}</p><h2 className="mt-1 text-lg font-semibold">{title}</h2></div><div className="flex items-center gap-2 text-xs text-slate-400"><span className="text-cyan-300 [&>svg]:h-4 [&>svg]:w-4">{icon}</span>{aside}</div></div>; }
function AlertCard({ alert }: { alert: Report['alerts'][number] }) { const tone = alert.severity === 'high' || alert.severity === 'critical' ? 'border-rose-300/15 bg-rose-300/[0.055]' : 'border-amber-300/15 bg-amber-300/[0.045]'; const content = <><div className="flex items-center justify-between gap-3"><span className="font-mono text-xs font-semibold text-slate-300">{alert.ticker}</span><span className={`status ${alert.severity === 'high' || alert.severity === 'critical' ? 'status-risk' : 'status-warn'}`}>{alert.severity}</span></div><p className="mt-2 text-sm font-medium">{alert.title}</p><p className="mt-1 text-xs leading-5 text-slate-400">{alert.detail}</p></>; return alert.url ? <a href={alert.url} target="_blank" rel="noreferrer" className={`block rounded-xl border p-3.5 transition hover:border-white/20 ${tone}`}>{content}</a> : <article className={`rounded-xl border p-3.5 ${tone}`}>{content}</article>; }
function EmptyState({ icon, title, detail }: { icon: React.ReactNode; title: string; detail: string }) { return <div className="py-6 text-center"><div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-white/[0.04] text-slate-400 [&>svg]:h-5 [&>svg]:w-5">{icon}</div><p className="font-medium">{title}</p><p className="mx-auto mt-1 max-w-md text-sm leading-6 text-slate-500">{detail}</p></div>; }
function Metric({ label, value, compact = false }: { label: string; value: string; compact?: boolean }) { return <div className="min-w-0 rounded-xl border border-white/8 bg-white/[0.025] px-3 py-3"><p className="text-[12px] text-slate-500">{label}</p><p className={`mt-1 truncate font-mono font-semibold text-slate-200 ${compact ? 'text-xs' : 'text-sm'}`} title={value}>{value}</p></div>; }
function Score({ value }: { value: number }) { return <div className="text-right"><p className={`font-mono text-3xl font-semibold ${value >= 75 ? 'text-emerald-300' : value >= 55 ? 'text-amber-200' : 'text-slate-400'}`}>{value}</p><p className="text-[11px] uppercase tracking-[0.09em] text-slate-600">score</p></div>; }
function Move({ value }: { value: number | null }) { if (value === null || value === undefined) return <span className="text-xs text-slate-600">—</span>; const positive = value >= 0; return <span className={`flex items-center gap-0.5 text-xs ${positive ? 'text-emerald-300' : 'text-rose-300'}`}>{positive ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}{value >= 0 ? '+' : ''}{value.toFixed(2)}%</span>; }

function formatCurrency(value: number | null | undefined) { return value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value); }
function formatNumber(value: number | null | undefined, digits = 1) { return value == null ? '—' : value.toFixed(digits); }
function formatPercent(value: number | null | undefined) { return value == null ? '—' : `${value.toFixed(1)}%`; }
function formatDays(value: number | null | undefined) { return value == null ? 'Unknown' : value < 0 ? 'Reported' : value === 0 ? 'Today' : `${value}d`; }
function formatMarketCap(value: number | null | undefined) { return value == null ? 'Market cap unavailable' : `$${(value / 1_000_000_000_000).toFixed(2)}T market cap`; }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'time unavailable' : new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }).format(date); }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date); }
