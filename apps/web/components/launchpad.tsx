"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Brain, ChevronRight, CircleHelp, Command, FolderKanban, LayoutDashboard, Plus, Radio, Rocket, ShieldCheck, Sparkles, User } from "lucide-react";
import { api, type Brand, type Campaign } from "@/lib/api";
import { Badge, Empty, ErrorNotice, Loading, PageHeading, Status } from "./ui";
import { NewCampaign, BrandBrain } from "./setup";
import { Workspace } from "./workspace";
import { UserProfile } from "./account";

export function Launchpad() {
  const path = usePathname();
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<{ mode: string }>("/health") });
  const brands = useQuery({ queryKey: ["brands"], queryFn: () => api<Brand[]>("/brands") });
  const campaigns = useQuery({ queryKey: ["campaigns"], queryFn: () => api<Campaign[]>("/campaigns") });
  const campaignId = path.match(/^\/campaigns\/([^/]+)/)?.[1];
  const isCampaign = campaignId && campaignId !== "new";
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to main content</a>
    <aside className="sidebar">
      <Link href="/" className="brand-logo"><span className="logo-mark"><img src="/logo.png" alt="Delph.ai Logo" width={22} height={22} style={{ objectFit: 'contain' }} /></span><span>Delph.ai</span></Link>
      <div className="workspace-picker"><span className="workspace-avatar">CL</span><div><strong>Campaign workspace</strong><small>Your campaign workspace</small></div></div>
      <p className="nav-label">WORKSPACE</p>
      <nav aria-label="Main navigation"><Link href="/" className={path === "/" ? "nav-link active" : "nav-link"}><LayoutDashboard size={18} /> Overview</Link><Link href="/campaigns" className={path.startsWith("/campaigns") ? "nav-link active" : "nav-link"}><FolderKanban size={18} /> Campaigns<span className="nav-count">{campaigns.data?.length ?? "—"}</span></Link><Link href="/brands" className={path.startsWith("/brands") ? "nav-link active" : "nav-link"}><Brain size={18} /> Brand Brain</Link><Link href="/profile" className={path === "/profile" ? "nav-link active" : "nav-link"}><User size={18} /> Profile</Link></nav>
      <div className="sidebar-campaigns"><p className="nav-label">RECENT CAMPAIGNS</p>{campaigns.data?.slice(0, 4).map((campaign) => <Link key={campaign.id} href={`/campaigns/${campaign.id}`} className="recent-link"><span className="tiny-dot" />{campaign.name}</Link>)}{!campaigns.data?.length && <p className="small muted">Your next big idea goes here.</p>}</div>
      <div className="sidebar-bottom"><div className="demo-card"><Sparkles size={18} /><strong>A connected campaign brain</strong><p>Context, content, and decisions.<br />One place to move them forward.</p><Link href="/campaigns/new">Start a campaign <ArrowUpRight size={15} /></Link></div><div className="local-status"><span className="tiny-dot" /> {health.data?.mode === "deterministic" ? "Local demo · no authentication" : "Private account workspace"}</div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><span className="breadcrumb">Workspace <ChevronRight size={14} /> <strong>{isCampaign ? "Campaign workspace" : path === "/brands" ? "Brand Brain" : path === "/profile" ? "Profile" : path === "/campaigns/new" ? "New campaign" : path === "/campaigns" ? "Campaigns" : "Overview"}</strong></span><div className="topbar-right"><Badge tone="green"><span className="tiny-dot" /> {health.data?.mode === "deterministic" ? "Deterministic demo" : "Gemini AI agents"}</Badge></div></header>
      <main id="main" className="main-content">
        {path === "/campaigns/new" ? <NewCampaign brands={brands.data || []} loading={brands.isPending} error={brands.error} /> : path === "/brands" ? <BrandBrain brands={brands.data || []} loading={brands.isPending} error={brands.error} /> : path === "/profile" ? <UserProfile /> : isCampaign ? <Workspace id={campaignId} brands={brands.data || []} /> : path === "/" || path === "/campaigns" ? <Dashboard campaigns={campaigns.data || []} loading={campaigns.isPending} error={campaigns.error} retry={() => void campaigns.refetch()} /> : <Empty title="Page not found" action={<Link className="button primary" href="/">Back to overview</Link>}>This workspace page does not exist.</Empty>}
      </main><footer className="app-footer"><Command size={13} /> Delph.ai <span>Built for thoughtful launches.</span><span className="footer-disclaimer">Human approval required · no automatic social publishing</span></footer>
    </div>
  </div>;
}

function Dashboard({ campaigns, loading, error, retry }: { campaigns: Campaign[]; loading: boolean; error: unknown; retry: () => void }) {
  const assets = campaigns.flatMap((campaign) => campaign.assets);
  const metrics = [{ label: "Campaigns", value: campaigns.length, detail: "Ideas in motion", icon: FolderKanban }, { label: "Content assets", value: assets.length, detail: "Connected to your strategy", icon: Sparkles }, { label: "Awaiting review", value: assets.filter((asset) => asset.status === "needs_review").length, detail: "Your judgment makes the difference", icon: ShieldCheck }, { label: "Experiments", value: campaigns.reduce((total, campaign) => total + campaign.experiments.length, 0), detail: "Simulated tests, real learning flow", icon: Radio }];
  return <><PageHeading eyebrow="YOUR CAMPAIGN COMMAND CENTER" title="Good ideas deserve a great launch." description="Turn your next brief into a campaign that works together." action={<Link href="/campaigns/new" className="button primary"><Plus size={17} /> New campaign</Link>} />
    <section className="hero"><div><Badge>FROM IDEA TO IMPACT</Badge><h2>Less scattered work.<br />More forward momentum.</h2><p>Give your campaign one home — from the first spark<br className="desktop-break" /> to the lessons that make your next launch better.</p><Link href="/campaigns/new" className="button dark">Build your next campaign <ArrowUpRight size={17} /></Link></div><div className="orbit" aria-hidden="true"><span className="orbit-ring ring-one" /><span className="orbit-ring ring-two" /><span className="orbit-core"><Rocket size={42} /></span><span className="orbit-pill pill-one"><Brain size={16} /> Brand context</span><span className="orbit-pill pill-two"><Sparkles size={16} /> Creative strategy</span><span className="orbit-pill pill-three"><ShieldCheck size={16} /> Human approval</span><span className="orbit-star">✦</span></div></section>
    <div className="metric-grid">{metrics.map(({ label, value, detail, icon: Icon }) => <div className="metric-card" key={label}><div><span>{label}</span><Icon size={17} /></div><strong>{loading ? "—" : value}</strong><p>{detail}</p></div>)}</div>
    <div className="section-heading"><div><h2>Your campaigns <span className="count">{campaigns.length}</span></h2><p className="muted">Every brief. Every decision. All connected.</p></div><Link href="/brands" className="text-link">Manage brand context <ArrowUpRight size={16} /></Link></div>
    <ErrorNotice error={error} />{error ? <button className="button secondary" onClick={retry}>Retry connection</button> : loading ? <Loading /> : campaigns.length ? <div className="campaign-grid">{campaigns.map((campaign, index) => <Link className="campaign-card" key={campaign.id} href={`/campaigns/${campaign.id}`}><div className={`campaign-art art-${index % 3}`}><span className="campaign-monogram">{campaign.name.split(" ").map((word) => word[0]).slice(0, 2).join("")}</span><span className="campaign-art-label">{campaign.duration_days}-DAY CAMPAIGN</span><ArrowUpRight size={20} /></div><div className="campaign-card-body"><div className="row"><Status value={campaign.status} /><span className="small muted">{new Date(campaign.created_at).toLocaleDateString("en", { month: "short", day: "numeric" })}</span></div><h3>{campaign.name}</h3><p>{campaign.goal}</p><div className="platform-tags">{campaign.platforms.map((platform) => <Badge key={platform}>{platform === "x" ? "X" : platform}</Badge>)}</div><div className="campaign-card-footer"><span>{campaign.assets.length} assets · {campaign.assets.filter((asset) => asset.status === "approved").length} approved</span><ChevronRight size={16} /></div></div></Link>)}</div> : <div className="panel"><Empty title="Your first campaign starts with a brief" action={<Link href="/campaigns/new" className="button primary"><Plus size={17} /> Create a campaign</Link>}>Tell us what you are launching. Connect your brand context, shape the strategy, and take it all the way to review.</Empty></div>}
    <div className="bottom-note"><CircleHelp size={17} /><p>Generation mode is shown above. Demo metrics are explicitly labeled; AI experiments await imported results.</p></div>
  </>;
}
