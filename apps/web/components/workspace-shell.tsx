import { Button } from "@auditor/ui";
import { FileText, PanelRight, ShieldCheck } from "lucide-react";

import { ServiceReadiness } from "./service-readiness";

export function WorkspaceShell() {
  return (
    <div className="min-h-screen px-3 py-3 sm:px-5 sm:py-5 lg:px-8">
      <a
        href="#workspace"
        className="sr-only z-50 rounded bg-ink px-3 py-2 text-paper focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to audit workspace
      </a>
      <div className="mx-auto max-w-[92rem] overflow-hidden border border-line bg-paper shadow-[0_18px_60px_rgb(23_35_43_/_0.08)]">
        <header className="flex min-h-16 items-center justify-between border-b border-line px-5 sm:px-8">
          <div className="flex items-baseline gap-3">
            <span className="font-prose text-2xl font-semibold tracking-[-0.025em] text-ink">
              Auditor
            </span>
            <span className="hidden text-[0.68rem] font-semibold uppercase tracking-[0.19em] text-evidence-needed sm:inline">
              Evidence-grounded writing review
            </span>
          </div>
          <nav aria-label="Primary navigation" className="flex items-center gap-1 sm:gap-3">
            <a
              href="#workspace"
              aria-current="page"
              className="rounded px-2 py-2 text-sm font-semibold text-ink outline-none hover:bg-canvas focus-visible:ring-2 focus-visible:ring-mineral"
            >
              Audit workspace
            </a>
            <span className="hidden border-l border-line pl-3 font-mono text-[0.68rem] uppercase tracking-[0.12em] text-evidence-needed md:inline">
              EN
            </span>
          </nav>
        </header>

        <ServiceReadiness />

        <main id="workspace" className="relative" tabIndex={-1}>
          <div className="grid min-h-[42rem] lg:grid-cols-[minmax(0,1fr)_23rem]">
            <section aria-labelledby="draft-title" className="min-w-0 px-5 py-7 sm:px-8 sm:py-10 lg:px-12">
              <div className="mx-auto max-w-4xl">
                <div className="mb-8 flex flex-col gap-4 border-b border-faint-line pb-6 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="font-mono text-[0.66rem] font-medium uppercase tracking-[0.18em] text-mineral">
                      Local text audit
                    </p>
                    <h1 id="draft-title" className="mt-2 max-w-2xl font-prose text-3xl font-semibold leading-tight tracking-[-0.025em] text-ink sm:text-4xl">
                      Review the claim, then trace the reason.
                    </h1>
                    <p className="mt-3 max-w-2xl text-base leading-6 text-evidence-needed">
                      Paste English or Slovak writing here. The auditor identifies writing and verification risks—it does not determine scientific truth.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.12em] text-evidence-needed">
                    <ShieldCheck aria-hidden="true" className="size-4 text-supported" />
                    Local workspace
                  </div>
                </div>

                <div className="relative min-h-[24rem] border border-line bg-white px-6 py-8 shadow-[inset_0_1px_0_rgb(255_255_255),0_10px_30px_rgb(23_35_43_/_0.04)] sm:px-10 sm:py-10">
                  <div className="absolute left-0 top-8 h-14 w-[3px] bg-mineral" aria-hidden="true" />
                  <div className="flex min-h-[18rem] flex-col items-center justify-center text-center">
                    <FileText aria-hidden="true" className="mb-4 size-7 stroke-[1.5] text-mineral" />
                    <h2 className="font-prose text-xl font-semibold text-ink">Your draft starts here</h2>
                    <p className="mt-2 max-w-sm text-sm leading-6 text-evidence-needed">
                      The editable document surface arrives in the text-editor milestone. This foundation keeps the review workspace ready without storing text remotely.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <aside aria-labelledby="review-title" className="relative border-t border-line bg-canvas/55 px-5 py-7 sm:px-8 lg:border-l lg:border-t-0 lg:px-7 lg:py-10">
              <div className="absolute -left-px top-0 hidden h-full w-px bg-mineral/45 lg:block" aria-hidden="true" />
              <div className="absolute -left-[5px] top-16 hidden size-[9px] rounded-full border-2 border-paper bg-mineral lg:block" aria-hidden="true" />
              <div className="flex items-center justify-between border-b border-line pb-4">
                <div>
                  <p className="font-mono text-[0.64rem] uppercase tracking-[0.16em] text-mineral">Provenance thread</p>
                  <h2 id="review-title" className="mt-1 font-prose text-xl font-semibold text-ink">Claim review</h2>
                </div>
                <PanelRight aria-hidden="true" className="size-5 text-evidence-needed" />
              </div>
              <div className="flex min-h-56 flex-col justify-center py-9 lg:min-h-[27rem]">
                <p className="text-sm font-semibold text-ink">No claim selected</p>
                <p className="mt-2 text-sm leading-6 text-evidence-needed">
                  Add text and run an audit. Selecting a highlighted claim will connect its exact span to the explanation here.
                </p>
                <div className="mt-6 border-l-2 border-dashed border-evidence-needed/45 pl-4">
                  <p className="font-mono text-[0.64rem] uppercase tracking-[0.13em] text-evidence-needed">Thread inactive</p>
                  <p className="mt-1 text-xs leading-5 text-evidence-needed">Editor span → finding → revision</p>
                </div>
              </div>
            </aside>
          </div>

          <footer className="flex flex-col gap-3 border-t border-line bg-paper px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
            <p className="font-mono text-xs text-evidence-needed">0 / 2,000 characters · No audit started</p>
            <Button disabled aria-describedby="audit-unavailable">Audit text</Button>
            <span id="audit-unavailable" className="sr-only">The text editor is not available in this foundation milestone.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
