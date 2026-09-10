'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Globe2,
  Inbox,
  Landmark,
  Newspaper,
  PlayCircle,
  Radar,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type NewsItem = { title: string; url: string; publisher: string; published_at?: string | null };
type FilingItem = { form: string; filed_at: string; description: string; url: string };
type Holding = {
  ticker: string; price: number | null; change_pct: number | null; return_20d_pct: number | null;
  rsi14: number | null; atr_pct: number | null; signal_score: number; stance: string; risk_level: string;
  news: NewsItem[]; filings: FilingItem[]; errors: string[];
};
type Candidate = Holding & { setup_score: number; thesis: string[]; horizon: string; risk_flags?: string[] };
type IntelligenceItem = {
  id: string; title: string; summary: string; url: string; publisher: string; published_at: string | null;
  source_type: string; region: string; topic: string; tickers: string[]; priority_score: number;
  priority: 'must-review' | 'scan' | 'background'; why_flagged: string; age_hours: number | null;
};
type FeedHealth = {
  name: string; url: string; source_type: string; region: string; status: string;
  item_count: number; latest_published_at: string | null; error: string | null;
};
type GlobalMarket = {
  symbol: string; label: string; region: string; category: string; price: number | null;
  change_pct: number | null; return_5d_pct: number | null; as_of: string | null;
  source: string; url: string; status: string; error?: string;
};
type Source = { name: string; url: string; cost: string; covers: string };
export type Report = {
  schema_version: number; run_id: string; generated_at: string; is_demo: boolean;
  market: { session: string; as_of_et: string; next_scheduled_refresh: string };
  summary: { headline: string; detail: string; disclaimer: string };
  quality: {
    score: number; source_count: number; price_coverage_pct: number; news_coverage_pct: number;
    feed_coverage_pct?: number; global_market_coverage_pct?: number; publisher_count?: number;
    provider_warning_count: number; provider_warnings: string[]; stale: boolean; warnings: string[];
  };
  intelligence: {
    headline: string; digest: string[]; review_queue: IntelligenceItem[]; must_review_count: number;
    scan_count: number; estimated_review_minutes: number;
    themes: { id: string; label: string; count: number; tickers: string[] }[];
    coverage: { total_items: number; international_items: number; video_items: number; filing_items: number; publisher_count: number; publishers: string[]; regions: string[]; healthy_feeds: number; total_feeds: number };
    feed_health: FeedHealth[];
  };
  global_markets: GlobalMarket[];
  alerts: { ticker: string; severity: string; type: string; title: string; detail: string; url?: string }[];
  portfolio: Holding[]; candidates: Candidate[];
  agents: { id: string; label: string; status: string; duration_ms: number; summary: string }[];
  sources: Source[];
};

type ModelContext = { registerTool: (tool: Record<string, unknown>, options?: { signal?: AbortSignal }) => void | Promise<void> };
declare global { interface Document { modelContext?: ModelContext } }

const REMOTE_REPORT = 'https://raw.githubusercontent.com/Eddie-gi/stock-analyst/main/public/data/latest.json';
const REVIEWED_KEY = 'signal-desk-reviewed-v2';
const FILTERS = [
  ['all', 'All sources'], ['must-review', 'Must review'], ['international', 'International'],
  ['video', 'Video'], ['filing', 'Filings'], ['company-news', 'Company news'],
] as const;

export function Dashboard({ initialData }: { initialData: Report }) {
  const [report, setReport] = useState<Report>(initialData);
  const [refreshing, setRefreshing] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [reviewed, setReviewed] = useState<Set<string>>(() => {
    if (typeof window === 'undefined') return new Set();
    try { return new Set(JSON.parse(localStorage.getItem(REVIEWED_KEY) ?? '[]') as string[]); } catch { return new Set(); }
  });
  const [filter, setFilter] = useState<string>('all');
  const [query, setQuery] = useState('');

  const reload = useCallback(async () => {
    setRefreshing(true);
    try {
      const endpoints = [`${REMOTE_REPORT}?ts=${Date.now()}`, `./data/latest.json?ts=${Date.now()}`];
      for (const endpoint of endpoints) {
        try {
          const response = await fetch(endpoint, { cache: 'no-store' });
          if (!response.ok) continue;
          const next = (await response.json()) as Report;
          if (next.schema_version >= 3 && next.intelligence?.review_queue) {
            setReport(next);
            break;
          }
        } catch {
          // Continue to the bundled last-known-good report.
        }
      }
    } finally {
      setLastChecked(new Date());
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void reload(), 0);
    const timer = window.setInterval(() => void reload(), 5 * 60 * 1000);
    const onFocus = () => void reload();
    window.addEventListener('focus', onFocus);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); window.removeEventListener('focus', onFocus); };
  }, [reload]);

  useEffect(() => {
    const context = document.modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    const register = async () => {
      await context.registerTool({
        name: 'get_morning_source_brief', title: 'Get morning source brief',
        description: 'Read the current prioritized source queue, overnight market handoff, themes, and coverage health.',
        inputSchema: { type: 'object', properties: {}, additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: true },
        execute: () => ({ intelligence: report.intelligence, global_markets: report.global_markets, quality: report.quality }),
      }, { signal: lifecycle.signal });
      await context.registerTool({
        name: 'find_source_items', title: 'Find source items',
        description: 'Find source-linked briefing items by ticker, publisher, topic, or words in the headline.',
        inputSchema: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'], additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: true },
        execute: (input: unknown) => {
          const raw = (input as { query?: unknown })?.query;
          const value = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
          return report.intelligence.review_queue.filter((item) => searchable(item).includes(value)).slice(0, 15);
        },
      }, { signal: lifecycle.signal });
    };
    void register().catch(() => undefined);
    return () => lifecycle.abort();
  }, [report]);

  const markReviewed = (id: string) => {
    setReviewed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      localStorage.setItem(REVIEWED_KEY, JSON.stringify([...next]));
      return next;
    });
  };

  const visibleItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return report.intelligence.review_queue.filter((item) => {
      const matchesFilter = filter === 'all' || item.priority === filter || item.source_type === filter;
      return matchesFilter && (!needle || searchable(item).includes(needle));
    });
  }, [filter, query, report.intelligence.review_queue]);

  const mustReview = report.intelligence.review_queue.filter((item) => item.priority === 'must-review');
  const reviewedCount = report.intelligence.review_queue.filter((item) => reviewed.has(item.id)).length;
  const isToday = easternDay(report.generated_at) === easternDay(new Date().toISOString());

  return (
    <main className="official-shell min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1580px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3"><div className="brand-mark"><Radar className="h-[18px] w-[18px]" /></div><div><p className="text-base font-semibold tracking-tight">Signal Desk</p><p className="hidden text-xs text-slate-500 sm:block">Daily market intelligence</p></div></div>
          <div className="flex items-center gap-2"><span className={`status hidden sm:inline-flex ${isToday ? 'status-good' : 'status-warn'}`}>{isToday ? 'Updated today' : 'Needs refresh'}</span><span className="hidden text-xs text-slate-500 lg:block">Checked {lastChecked ? formatClock(lastChecked.toISOString()) : 'on open'}</span><Button variant="outline" size="icon-lg" onClick={() => void reload()} disabled={refreshing} aria-label="Check for the newest briefing"><RefreshCw className={refreshing ? 'animate-spin' : ''} /></Button></div>
        </div>
      </header>

      <div className="mx-auto max-w-[1580px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <section className="briefing-head"><div className="max-w-4xl"><p className="eyebrow flex items-center gap-2"><Clock3 className="h-3.5 w-3.5 text-cyan-300" /> Official morning brief · Generated {formatDateTime(report.generated_at)}</p><h1 className="briefing-title mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">{report.intelligence.headline}</h1><div className="mt-4 grid gap-1.5 text-base leading-7 text-slate-400">{report.intelligence.digest.slice(0, 3).map((line) => <p key={line}>{line}</p>)}</div></div><div className="review-budget"><p className="eyebrow">Estimated reading time</p><p className="mt-2 font-mono text-4xl font-semibold text-cyan-200">{report.intelligence.estimated_review_minutes}<span className="ml-1 text-lg text-slate-500">min</span></p><p className="mt-2 text-sm text-slate-400">{reviewedCount}/{report.intelligence.coverage.total_items} items reviewed on this device</p></div></section>

        <div className="mb-6 grid grid-cols-2 gap-2 md:grid-cols-5"><Stat label="Must review" value={report.intelligence.must_review_count} tone="urgent" /><Stat label="Sources indexed" value={report.intelligence.coverage.total_items} /><Stat label="International" value={report.intelligence.coverage.international_items} /><Stat label="Videos" value={report.intelligence.coverage.video_items} /><Stat label="Publishers" value={report.intelligence.coverage.publisher_count} /></div>

        <Tabs defaultValue="brief" className="gap-5">
          <TabsList variant="line" className="h-auto max-w-full justify-start overflow-x-auto border-b border-white/8 pb-2"><TabsTrigger value="brief">Morning brief</TabsTrigger><TabsTrigger value="inbox">Source inbox <span className="ml-1.5 rounded-full bg-white/8 px-1.5 text-[11px]">{report.intelligence.coverage.total_items}</span></TabsTrigger><TabsTrigger value="overnight">Overnight handoff</TabsTrigger><TabsTrigger value="market">Market context</TabsTrigger><TabsTrigger value="coverage">Coverage</TabsTrigger></TabsList>
          <TabsContent value="brief"><MorningBrief report={report} items={mustReview} reviewed={reviewed} onReview={markReviewed} /></TabsContent>
          <TabsContent value="inbox"><SourceInbox items={visibleItems} reviewed={reviewed} filter={filter} query={query} onFilter={setFilter} onQuery={setQuery} onReview={markReviewed} /></TabsContent>
          <TabsContent value="overnight"><Overnight markets={report.global_markets} themes={report.intelligence.themes} /></TabsContent>
          <TabsContent value="market"><MarketContext report={report} /></TabsContent>
          <TabsContent value="coverage"><Coverage report={report} /></TabsContent>
        </Tabs>

        <footer className="mt-7 border-t border-white/8 pt-5 text-xs leading-5 text-slate-500"><p>{report.summary.disclaimer} Headlines and video titles are routing metadata, not verified conclusions. Open the linked source before relying on an item.</p><p className="mt-1">Automatic checks run every five minutes while this page is open. Background collection targets one report between 5:30 and 9:20 AM Eastern on weekdays.</p></footer>
      </div>
    </main>
  );
}

function MorningBrief({ report, items, reviewed, onReview }: { report: Report; items: IntelligenceItem[]; reviewed: Set<string>; onReview: (id: string) => void }) {
  const queue = items.length ? items : report.intelligence.review_queue.slice(0, 5);
  return <div className="grid gap-4 xl:grid-cols-[1.35fr_.65fr]"><section className="panel overflow-hidden"><PanelHeader eyebrow="Highest information value" title="Read these first" icon={<Inbox />} aside={`${queue.length} source-linked items`} /><div className="divide-y divide-white/8">{queue.map((item) => <SourceRow key={item.id} item={item} reviewed={reviewed.has(item.id)} onReview={onReview} />)}</div></section><aside className="grid content-start gap-4"><section className="panel p-5"><div className="flex items-center justify-between"><div><p className="eyebrow">Overnight transmission</p><h2 className="mt-1 text-lg font-semibold">Markets before New York</h2></div><Globe2 className="h-5 w-5 text-cyan-300" /></div><div className="mt-5 grid gap-2">{report.global_markets.slice(0, 6).map((market) => <MarketLine key={market.symbol} market={market} />)}</div></section><section className="panel p-5"><div className="flex items-center gap-2 text-violet-300"><Sparkles className="h-4 w-4" /><p className="eyebrow !text-violet-300">Theme compression</p></div><div className="mt-4 grid gap-3">{report.intelligence.themes.slice(0, 5).map((theme) => <div key={theme.id}><div className="flex justify-between gap-3 text-sm"><span className="capitalize text-slate-300">{theme.label}</span><span className="font-mono text-slate-500">{theme.count}</span></div><div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/7"><div className="h-full rounded-full bg-violet-300/70" style={{ width: `${Math.min(100, theme.count * 7)}%` }} /></div>{theme.tickers.length > 0 && <p className="mt-1 text-xs text-slate-600">{theme.tickers.join(' · ')}</p>}</div>)}</div></section></aside></div>;
}

function SourceInbox({ items, reviewed, filter, query, onFilter, onQuery, onReview }: { items: IntelligenceItem[]; reviewed: Set<string>; filter: string; query: string; onFilter: (value: string) => void; onQuery: (value: string) => void; onReview: (id: string) => void }) {
  return <section className="panel overflow-hidden"><div className="border-b border-white/8 p-4 sm:p-5"><div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between"><div><p className="eyebrow">Deduplicated evidence</p><h2 className="mt-1 text-lg font-semibold">Source inbox</h2></div><div className="relative w-full xl:max-w-sm"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" /><input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search ticker, source, region, or theme" aria-label="Search source inbox" className="source-search" /></div></div><div className="mt-4 flex gap-2 overflow-x-auto pb-1">{FILTERS.map(([value, label]) => <button key={value} type="button" onClick={() => onFilter(value)} className={`filter-chip ${filter === value ? 'filter-chip-active' : ''}`}>{label}</button>)}</div></div>{items.length ? <div className="divide-y divide-white/8">{items.map((item) => <SourceRow key={item.id} item={item} reviewed={reviewed.has(item.id)} onReview={onReview} />)}</div> : <div className="p-10 text-center"><Search className="mx-auto h-5 w-5 text-slate-600" /><p className="mt-3 font-medium">No source item matches this view</p><p className="mt-1 text-sm text-slate-500">Change the filter or search terms.</p></div>}</section>;
}

function SourceRow({ item, reviewed, onReview }: { item: IntelligenceItem; reviewed: boolean; onReview: (id: string) => void }) {
  const icon = item.source_type === 'video' ? <PlayCircle /> : item.source_type === 'filing' ? <Landmark /> : item.source_type === 'international' ? <Globe2 /> : <Newspaper />;
  return <article className={`source-row ${reviewed ? 'source-row-reviewed' : ''}`}><button type="button" onClick={() => onReview(item.id)} className={`review-check ${reviewed ? 'review-check-active' : ''}`} aria-label={reviewed ? `Mark ${item.title} unreviewed` : `Mark ${item.title} reviewed`}>{reviewed && <Check className="h-3.5 w-3.5" />}</button><div className="min-w-0"><div className="mb-2 flex flex-wrap items-center gap-2"><span className={`source-kind source-kind-${item.source_type}`}><span className="[&>svg]:h-3.5 [&>svg]:w-3.5">{icon}</span>{labelSourceType(item.source_type)}</span>{item.priority === 'must-review' && <span className="status status-risk">Must review</span>}<span className="text-xs text-slate-600">{item.region} · {item.topic.replace('-', ' ')}</span></div><a href={item.url} target="_blank" rel="noreferrer" onClick={() => { if (!reviewed) onReview(item.id); }} className="group inline-flex max-w-full items-start gap-2 text-base font-semibold leading-6 text-slate-100 hover:text-cyan-200"><span>{item.title}</span><ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-slate-600 group-hover:text-cyan-300" /></a><p className="source-summary">{item.summary}</p><p className="source-reason"><span>Why it’s here:</span> {item.why_flagged}</p><div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-600"><span className="font-medium text-slate-500">{item.publisher}</span><span>{formatRelative(item)}</span>{item.tickers.map((ticker) => <span key={ticker} className="ticker-chip">{ticker}</span>)}</div></div><div className="hidden text-right sm:block"><p className={`font-mono text-xl font-semibold ${item.priority === 'must-review' ? 'text-rose-200' : item.priority === 'scan' ? 'text-amber-200' : 'text-slate-500'}`}>{item.priority_score}</p><p className="text-[11px] uppercase tracking-wider text-slate-600">priority</p></div></article>;
}

function Overnight({ markets, themes }: { markets: GlobalMarket[]; themes: Report['intelligence']['themes'] }) {
  const asia = markets.filter((item) => ['Japan', 'Hong Kong', 'China', 'South Korea', 'Taiwan', 'Australia'].includes(item.region));
  const crossAsset = markets.filter((item) => !asia.includes(item));
  return <div className="grid gap-4 xl:grid-cols-[1.2fr_.8fr]"><section className="panel overflow-hidden"><PanelHeader eyebrow="Closed or trading before the US" title="Asia market handoff" icon={<Globe2 />} aside="Direct market links" /><MarketTable markets={asia} /></section><section className="panel overflow-hidden"><PanelHeader eyebrow="Risk transmission" title="Europe & cross-assets" icon={<ArrowUpRight />} aside="Daily / five-session move" /><MarketTable markets={crossAsset} /></section><section className="panel p-5 xl:col-span-2"><p className="eyebrow">How to use this</p><p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">Treat overnight moves as context, not explanations. Use the source inbox to find policy, supply-chain, or company evidence that may account for a move, then open the original source before forming a view. Active themes: {themes.slice(0, 4).map((theme) => theme.label).join(', ')}.</p></section></div>;
}

function MarketContext({ report }: { report: Report }) {
  return <div className="grid gap-4 xl:grid-cols-[1.2fr_.8fr]"><section className="panel overflow-hidden"><PanelHeader eyebrow="Secondary context" title="Watchlist signal matrix" icon={<Radar />} aside="Not the primary briefing" /><Table><TableHeader><TableRow className="border-white/8 hover:bg-transparent"><TableHead className="pl-5">Ticker</TableHead><TableHead>Price</TableHead><TableHead>Today</TableHead><TableHead>20D</TableHead><TableHead>Risk</TableHead><TableHead className="pr-5 text-right">Signal</TableHead></TableRow></TableHeader><TableBody>{report.portfolio.map((item) => <TableRow key={item.ticker} className="border-white/8"><TableCell className="pl-5 font-semibold">{item.ticker}</TableCell><TableCell className="font-mono">{formatCurrency(item.price)}</TableCell><TableCell><Move value={item.change_pct} /></TableCell><TableCell><Move value={item.return_20d_pct} /></TableCell><TableCell className="capitalize text-slate-400">{item.risk_level}</TableCell><TableCell className="pr-5 text-right font-mono">{item.signal_score}</TableCell></TableRow>)}</TableBody></Table></section><aside className="grid content-start gap-4"><section className="panel p-5"><p className="eyebrow">Research candidates</p><div className="mt-4 grid gap-3">{report.candidates.map((item, index) => <div key={item.ticker} className="rounded-xl border border-white/8 bg-white/[0.02] p-4"><div className="flex items-center justify-between"><div className="flex items-center gap-3"><span className="rank">{index + 1}</span><span className="text-lg font-semibold">{item.ticker}</span></div><span className="font-mono text-cyan-200">{item.setup_score}</span></div><p className="mt-3 text-sm leading-5 text-slate-400">{item.thesis[0] ?? 'Open the linked evidence before forming a view.'}</p></div>)}</div></section><section className="panel p-5"><p className="eyebrow">Rule-based alerts</p><div className="mt-4 grid gap-3">{report.alerts.slice(0, 5).map((item, index) => <div key={`${item.ticker}-${index}`}><div className="flex items-center gap-2"><span className="ticker-chip">{item.ticker}</span><span className="text-sm font-medium">{item.title}</span></div><p className="mt-1 text-xs leading-5 text-slate-500">{item.detail}</p></div>)}</div></section></aside></div>;
}

function Coverage({ report }: { report: Report }) {
  return <div className="grid gap-4 xl:grid-cols-[.9fr_1.1fr]"><div className="grid content-start gap-4"><section className="panel p-5"><div className="flex items-start justify-between"><div><p className="eyebrow">Trust layer</p><h2 className="mt-1 text-lg font-semibold">Coverage health</h2></div><QualityScore value={report.quality.score} /></div><div className="mt-5 grid grid-cols-2 gap-2"><MiniMetric label="Headline feeds" value={`${report.quality.feed_coverage_pct ?? 0}%`} /><MiniMetric label="Global markets" value={`${report.quality.global_market_coverage_pct ?? 0}%`} /><MiniMetric label="Watchlist prices" value={`${report.quality.price_coverage_pct}%`} /><MiniMetric label="Publishers" value={String(report.intelligence.coverage.publisher_count)} /></div>{report.quality.warnings.length > 0 && <div className="mt-4 text-sm leading-6 text-amber-200">{report.quality.warnings.join(' ')}</div>}</section><section className="panel p-5"><p className="eyebrow">Configured sources</p><div className="mt-4 grid gap-2">{report.sources.map((source) => <a key={`${source.name}-${source.url}`} href={source.url} target="_blank" rel="noreferrer" className="source-directory"><div><p className="text-sm font-medium">{source.name}</p><p className="mt-1 text-xs leading-5 text-slate-500">{source.covers}</p></div><ExternalLink className="h-4 w-4 shrink-0 text-slate-600" /></a>)}</div></section></div><div className="grid content-start gap-4"><section className="panel p-5"><div className="flex items-center justify-between"><div><p className="eyebrow">Live source checks</p><h2 className="mt-1 text-lg font-semibold">Feed health</h2></div><ShieldCheck className="h-5 w-5 text-emerald-300" /></div><div className="mt-5 grid gap-2">{report.intelligence.feed_health.map((feed) => <a key={feed.name} href={feed.url} target="_blank" rel="noreferrer" className="feed-health"><span className={`h-2 w-2 rounded-full ${feed.status === 'healthy' ? 'bg-emerald-300' : feed.status === 'empty' ? 'bg-amber-300' : 'bg-rose-300'}`} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{feed.name}</p><p className="text-xs text-slate-600">{feed.region} · {feed.item_count} indexed · {feed.status}</p></div><ExternalLink className="h-3.5 w-3.5 text-slate-600" /></a>)}</div></section><section className="panel p-5"><div className="flex items-center justify-between"><div><p className="eyebrow">Automation trace</p><h2 className="mt-1 text-lg font-semibold">Agent network</h2></div><Bot className="h-5 w-5 text-cyan-300" /></div><div className="mt-5 grid gap-3">{report.agents.map((agent) => <div key={agent.id} className="grid grid-cols-[auto_1fr_auto] gap-3"><span className="mt-0.5 grid h-6 w-6 place-items-center rounded-full bg-emerald-300/10 text-emerald-300"><CheckCircle2 className="h-3.5 w-3.5" /></span><div><p className="text-sm font-medium">{agent.label}</p><p className="mt-1 text-xs leading-5 text-slate-500">{agent.summary}</p></div><span className="font-mono text-[11px] text-slate-600">{agent.duration_ms}ms</span></div>)}</div></section></div></div>;
}

function MarketTable({ markets }: { markets: GlobalMarket[] }) { return <Table><TableHeader><TableRow className="border-white/8 hover:bg-transparent"><TableHead className="pl-5">Market</TableHead><TableHead>Region</TableHead><TableHead>1D</TableHead><TableHead className="pr-5 text-right">5D</TableHead></TableRow></TableHeader><TableBody>{markets.map((market) => <TableRow key={market.symbol} className="border-white/8"><TableCell className="pl-5"><a href={market.url} target="_blank" rel="noreferrer" className="font-medium hover:text-cyan-200">{market.label}</a></TableCell><TableCell className="text-slate-500">{market.region}</TableCell><TableCell><Move value={market.change_pct} /></TableCell><TableCell className="pr-5 text-right"><Move value={market.return_5d_pct} right /></TableCell></TableRow>)}</TableBody></Table>; }
function MarketLine({ market }: { market: GlobalMarket }) { return <a href={market.url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-4 rounded-lg px-2 py-1.5 hover:bg-white/[0.035]"><div><p className="text-sm font-medium">{market.label}</p><p className="text-xs text-slate-600">{market.region}</p></div><Move value={market.change_pct} right /></a>; }
function PanelHeader({ eyebrow, title, icon, aside }: { eyebrow: string; title: string; icon: React.ReactNode; aside: string }) { return <div className="flex flex-col gap-3 border-b border-white/8 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="eyebrow">{eyebrow}</p><h2 className="mt-1 text-lg font-semibold">{title}</h2></div><div className="flex items-center gap-2 text-xs text-slate-500"><span className="text-cyan-300 [&>svg]:h-4 [&>svg]:w-4">{icon}</span>{aside}</div></div>; }
function Stat({ label, value, tone }: { label: string; value: number; tone?: 'urgent' }) { return <div className="stat-card"><p className="text-xs text-slate-500">{label}</p><p className={`mt-1 font-mono text-2xl font-semibold ${tone === 'urgent' && value > 0 ? 'text-rose-200' : 'text-slate-100'}`}>{value}</p></div>; }
function MiniMetric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/8 bg-white/[0.025] p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-mono text-lg text-slate-200">{value}</p></div>; }
function QualityScore({ value }: { value: number }) { return <div className="text-right"><p className={`font-mono text-3xl font-semibold ${value >= 85 ? 'text-emerald-300' : value >= 65 ? 'text-amber-200' : 'text-rose-200'}`}>{value}</p><p className="text-[11px] uppercase tracking-wider text-slate-600">quality</p></div>; }
function Move({ value, right = false }: { value: number | null; right?: boolean }) { if (value == null) return <span className={`text-xs text-slate-600 ${right ? 'block text-right' : ''}`}>—</span>; const positive = value >= 0; return <span className={`inline-flex items-center gap-0.5 text-sm ${right ? 'justify-end' : ''} ${positive ? 'text-emerald-300' : 'text-rose-300'}`}>{positive ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}{positive ? '+' : ''}{value.toFixed(2)}%</span>; }

function searchable(item: IntelligenceItem) { return [item.title, item.summary, item.publisher, item.region, item.topic, ...item.tickers].join(' ').toLowerCase(); }
function labelSourceType(value: string) { return value === 'company-news' ? 'Company news' : value.charAt(0).toUpperCase() + value.slice(1); }
function formatCurrency(value: number | null) { return value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value); }
function formatDateTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'time unavailable' : new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'long', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }).format(date); }
function formatClock(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? 'now' : new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }).format(date); }
function easternDay(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date); }
function formatRelative(item: IntelligenceItem) { if (item.age_hours == null) return item.published_at ? formatDateTime(item.published_at) : 'Time unavailable'; if (item.age_hours < 1) return 'Within the last hour'; if (item.age_hours < 24) return `${Math.max(1, Math.round(item.age_hours))}h ago`; return `${Math.round(item.age_hours / 24)}d ago`; }
