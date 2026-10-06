// Preview-only compatibility with the actual RC Journal read API.
import { afterEach, expect, it, vi } from "vitest";
import { listDecisions, readDecisionAudit, readDecisionDetail } from "./decision-api";

afterEach(() => {vi.unstubAllEnvs();vi.unstubAllGlobals();});
it("maps real Preview Journal items and its actual audit endpoint", async () => {
  vi.stubEnv("NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE","true");
  vi.stubGlobal("window",{location:{origin:"http://localhost:3802"}});
  const fetchMock = vi.fn()
    .mockResolvedValueOnce({ok:true,json:async()=>({items:[{id:"demo",title:"PREVIEW",status:"confirmed"}]})})
    .mockResolvedValueOnce({ok:true,json:async()=>({items:[{id:"event",action:"decision.confirmed",metadata:{policy_version_number:1}}],next_before_sequence_number:null})});
  vi.stubGlobal("fetch",fetchMock);
  expect((await listDecisions()).decisions[0].title).toBe("PREVIEW");
  expect((await readDecisionAudit("demo")).events[0].action).toBe("decision.confirmed");
  expect(fetchMock.mock.calls[1][0]).toContain("/audit-events");
});
it("maps actual immutable snapshots without inventing a snapshot identifier", async () => {
  vi.stubEnv("NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE","true");
  vi.stubGlobal("window",{location:{origin:"http://localhost:3802"}});
  vi.stubGlobal("fetch",vi.fn()
    .mockResolvedValueOnce({ok:true,json:async()=>({id:"demo",status:"confirmed",original_snapshot:{title:"PREVIEW"},effective_snapshot:{title:"PREVIEW"}})})
    .mockResolvedValueOnce({ok:true,json:async()=>({items:[{action:"decision.confirmed",metadata:{policy_version_number:1}}],next_before_sequence_number:null})}));
  const d=await readDecisionDetail("demo");
  expect(d.confirmed?.title).toBe("PREVIEW");
  expect(d.confirmed?.policy_version_number).toBe(1);
  expect(d.confirmed?.snapshot_id).toBeNull();
});
