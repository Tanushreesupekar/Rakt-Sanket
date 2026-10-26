import { RiskPill, dateLabel } from '../components/shared'
import type { Forecast } from '../../lib/types'

export function ForecastView({ forecasts }: { forecasts: Forecast[] }) {
  const ordered = forecasts.slice().sort((a, b) => b.cbsri - a.cbsri)
  return <section className="panel forecast-board"><div className="panel-heading"><div><div className="eyebrow">7–14 DAY DEMAND OUTLOOK</div><h2>Forecast by blood group</h2></div><span className="record-count">{forecasts.length} blood groups</span></div><div className="forecast-board-grid">{ordered.map((forecast) => {
    const finalPoint = forecast.points.at(-1)
    const maxUnits = Math.max(forecast.current_units, 1)
    return <article className="forecast-group-card" key={forecast.blood_group}><div className="forecast-group-heading"><span className="blood-type">{forecast.blood_group}</span><RiskPill level={finalPoint?.risk_level ?? 'stable'} /><span className="forecast-cbsri">{forecast.cbsri.toFixed(0)}<small> CBSRI</small></span></div><div className="forecast-bar-chart">{forecast.points.filter((_, index) => index % 2 === 0 || index === forecast.points.length - 1).map((point) => <span className="forecast-bar" key={point.date} title={`${dateLabel(point.date)}: ${point.projected_units} units`}><i className={point.projected_units < forecast.safety_stock_units ? 'bar-under-safety' : ''} style={{ height: `${Math.max(4, point.projected_units / maxUnits * 100)}%` }} /></span>)}</div><div className="forecast-range"><span>{forecast.current_units} units now</span><strong>{finalPoint?.projected_units ?? 0} projected</strong></div><p>{forecast.explanation}</p></article>
  })}</div><p className="request-disclaimer">Pilot forecast uses a weekday-adjusted demand baseline. Validate against local historical stock data before operational use.</p></section>
}
