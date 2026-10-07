import { Connections } from "../../lib/owner-data";
export default function IBKRInventory({ broker }: { broker: Connections["brokers"][number] }) {
  return <section className="panel" aria-label="Broker inventory provenance">
    <h2>IBKR inventory · {broker.connection_type}</h2>
    <p><strong>MIXED DATA MODE · READ ONLY · VALUATION NOT LIVE</strong></p>
    <p>Broker inventory: {broker.connection_type}. Market data / FX remain separate DEMO inputs in Preview. New investment recommendations are unavailable.</p>
    <p>Data quality: {broker.data_quality}. Unresolved instruments: {broker.unresolved ?? 0}. Last successful sync: {broker.last_sync ?? "Never"}.</p>
    {broker.error_code && <p role="alert">{broker.error_code} — authenticate directly in the official gateway if required. Previous data is retained.</p>}
    <ul>{broker.accounts?.map((a) => <li key={a.reference}>{a.reference} · {a.currency} · {a.source}</li>)}</ul>
    <h3>Native cash balances</h3>
    <ul>{broker.cash_balances?.map((c) => <li key={`${c.account}:${c.currency}`}>{c.account}: {c.currency} {c.amount} · {c.quality} · {c.as_of}</li>)}</ul>
    <h3>Positions</h3>
    <div className="owner-table-scroll"><table><thead><tr><th>Account</th><th>Instrument</th><th>Quantity</th><th>Reported average cost</th><th>Identity / source</th><th>Strategic target</th></tr></thead>
      <tbody>{broker.holdings?.map((p) => <tr key={`${p.account}:${p.conid}`}>
        <td>{p.account}</td><td>{p.symbol} · conid {p.conid}</td><td>{p.quantity}</td><td>{p.average_cost == null ? "Unknown" : `${p.currency} ${p.average_cost}`}</td><td>{p.identity_status} · {p.source} · {p.quality}</td><td>{p.target}%{p.non_target ? " · Non-target holding" : ""}</td>
      </tr>)}</tbody></table></div>
    <p>Average cost is broker-reported position cost, not a market quote or verified tax-lot basis. Missing provider timestamps remain UNKNOWN.</p>
  </section>;
}
