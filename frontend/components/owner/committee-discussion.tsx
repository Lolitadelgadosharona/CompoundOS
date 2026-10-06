"use client";
import { useState } from "react";
import {
  CommitteeDiscussion,
  committeeText,
  Overview,
  ownerFinding,
} from "../../lib/owner-data";
import { Badge } from "./shared";
export default function CommitteeDiscussionPanel({
  report,
  data,
}: {
  report: CommitteeDiscussion;
  data?: Overview;
}) {
  const [answer, setAnswer] = useState("");
  return (
    <section className="panel" id="discussion">
      <h2>Committee perspectives & challenge</h2>
      <p className="owner-simulated">
        SIMULATED COMMITTEE · NOT REAL AI ANALYSIS
      </p>
      <p>{report.review_kind}</p>
      <p>
        Overall: <Badge status={report.overall} /> · Confidence: NOT AVAILABLE
      </p>
      <p>
        Discussion cannot complete governance, authorize approval or replace the
        candidate.
      </p>
      <div className="owner-two-column">
        {report.perspectives.map((p) => (
          <article key={p.name} className="panel">
            <h3>{p.name}</h3>
            <p>
              VIEW: <Badge status={p.view} />
            </p>
            <p>KEY REASON: {committeeText(p.key_reason)}</p>
            <p>DATA LIMITATIONS: {p.data_limitations}</p>
            <details>
              <summary>EVIDENCE REFERENCES</summary>
              {p.evidence_references.length ? (
                p.evidence_references.map((e, i) => (
                  <p key={i}>
                    {e.claim}
                    <small> · {e.citation_ref}</small>
                  </p>
                ))
              ) : (
                <p>No supplied evidence for this perspective. NOT EVALUATED.</p>
              )}
            </details>
          </article>
        ))}
      </div>
      {[
        ["SUPPORTING CASE", report.supporting_case],
        ["OPPOSING CASE", report.opposing_case],
        ["KEY RISKS", report.key_risks],
        ["DATA LIMITATIONS", report.data_limitations],
        ["WHAT WOULD CHANGE OUR MIND?", report.what_changes_mind],
        ["ALTERNATIVES CONSIDERED", report.alternatives],
      ].map(([title, items]) => (
        <div key={title as string}>
          <h3>{title}</h3>
          <ul>
            {(items as string[]).map((text, i) => (
              <li key={i}>
                {committeeText(data ? ownerFinding(text, data) : text)}
              </li>
            ))}
          </ul>
        </div>
      ))}
      <h3>ASK COMMITTEE</h3>
      <p>Local evidence only. No market forecasts.</p>
      <div className="actions">
        {report.questions.map((q) => (
          <button key={q.question} onClick={() => setAnswer(q.answer)}>
            {q.question}
          </button>
        ))}
      </div>
      {answer && <p role="status">{answer}</p>}
      <h3>CHALLENGE / MODIFY PLAN</h3>
      <p>{report.modification}</p>
      <button disabled>Contribution override — deferred</button>
    </section>
  );
}
