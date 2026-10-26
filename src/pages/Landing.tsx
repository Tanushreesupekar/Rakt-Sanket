import { Activity, Bell, Droplet, Gauge, HeartPulse, MapPin, Send, ShieldCheck } from 'lucide-react'

export default function Landing({ onAdmin, onDonor }: { onAdmin: () => void; onDonor: () => void }) {
  return (
    <div className="landing">
      <header className="landing-topbar">
        <span className="brand">
          <span className="brand-mark"><Droplet size={21} fill="currentColor" /></span>
          <span className="brand-copy"><strong>RaktSanket</strong><small>Blood operations · Pilot</small></span>
        </span>
        <nav className="landing-links" aria-label="Landing sections">
          <a href="#how">How it works</a>
          <a href="#features">Why RaktSanket</a>
          <a href="#scope">Pilot scope</a>
        </nav>
        <div className="landing-cta">
          <button className="button button-outline" onClick={onDonor}>Donor sign in</button>
          <button className="button button-primary" onClick={onAdmin}>Admin sign in</button>
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <div className="eyebrow"><span className="eyebrow-mark" />PROACTIVE · EXPLAINABLE · FATIGUE-AWARE</div>
            <h1>Predict blood shortages 7–14 days early, then contact the right donors.</h1>
            <p>
              RaktSanket replaces reactive mass SMS blasts with the Composite Blood Shortage-Response Index (CBSRI):
              shortage forecasting, donor response probability, and fatigue-adjusted priority in one transparent score.
            </p>
            <div className="landing-hero-actions">
              <button className="button button-primary" onClick={onAdmin}><Gauge size={15} />Open admin console</button>
              <button className="button button-outline" onClick={onDonor}><HeartPulse size={15} />Go to donor space</button>
            </div>
            <div className="landing-hero-meta">
              <span><ShieldCheck size={14} />Human review required before donor contact</span>
              <span><MapPin size={14} />Pilot districts · low-bandwidth friendly</span>
            </div>
          </div>
          <div className="landing-hero-card" aria-label="CBSRI preview">
            <div className="landing-card-topline"><span><Activity size={13} />CBSRI · LIVE PREVIEW</span><b>14-day window</b></div>
            <div className="landing-cbsri-score"><strong>72</strong><span>critical · O− · Amravati example</span></div>
            <ul>
              <li><i />Shortage forecast <b>high</b></li>
              <li><i />Top-5 donor response <b>64%</b></li>
              <li><i />Fatigue-adjusted priority <b>58.4</b></li>
            </ul>
            <p>Every alert and donor rank ships with a human-readable reason. No black-box outreach.</p>
            <button className="button button-outline full-button" onClick={onAdmin}><Send size={15} />Review outreach tiers</button>
          </div>
        </section>

        <section id="how" className="landing-section">
          <div className="eyebrow">HOW IT WORKS</div>
          <h2>From forecast to staged contact in three steps</h2>
          <div className="landing-grid-3">
            <article><strong>01 · Forecast</strong><span>Weekday, seasonal and festival-aware projection per district and blood group, 7–14 days ahead.</span></article>
            <article><strong>02 · Rank</strong><span>XGBoost response probability on recency, frequency and past response, discounted for recent contact load.</span></article>
            <article><strong>03 · Activate in tiers</strong><span>Priority → Expanded → Wider batches. Repeated non-responders are deprioritised to cut fatigue.</span></article>
          </div>
        </section>

        <section id="features" className="landing-section">
          <div className="eyebrow">WHY RAKTSANKET</div>
          <h2>Built for Indian blood-bank reality</h2>
          <div className="landing-grid-3">
            <article><span className="landing-icon"><Activity size={17} /></span><strong>Explainable AI</strong><span>Model factors shown for each donor and forecast point — season, coverage, trend, unmet-demand history.</span></article>
            <article><span className="landing-icon"><Bell size={17} /></span><strong>Fatigue-aware</strong><span>Contact load and recency lower priority automatically. No donor is spammed every round.</span></article>
            <article><span className="landing-icon"><HeartPulse size={17} /></span><strong>Operator + donor views</strong><span>Admins manage stock and outreach; donors manage availability, requests and history.</span></article>
          </div>
        </section>

        <section id="scope" className="landing-section landing-scope">
          <div className="eyebrow">PILOT SCOPE</div>
          <h2>Small pilot, measurable outcome</h2>
          <p>Limited districts and blood banks. Public/example-schema data for forecasting and ranking. Lightweight web dashboard for low-bandwidth networks. Aadhaar/eKYC, wearables, drone delivery, organ matching and native mobile apps are out of scope.</p>
        </section>
      </main>

      <footer className="landing-footer">
        <span>RaktSanket · Pilot operations console · Demo data only — validate before operational use</span>
        <span><ShieldCheck size={14} />Simulated outreach — no SMS is sent from this demo</span>
      </footer>
    </div>
  )
}
