import { ChapterHeading } from "@/components/landing/shared/ChapterHeading";

const capabilities = [
  {
    name: "Source checks",
    output: "Extracted claims, verdicts and source links when available.",
    limitation: "Up to 15 claims from the first 15,000 characters. Similar fact-check matches need human confirmation.",
  },
  {
    name: "AI style estimates",
    output: "Paragraph-level signals with a heuristic fallback.",
    limitation: "Samples up to 20 paragraphs. Estimates are not proof of authorship or misconduct.",
  },
  {
    name: "Citation checks",
    output: "Link accessibility and retraction signals for links extracted from web articles.",
    limitation: "PDF and pasted-text bibliographies are not yet parsed into a reference inventory. Missing retraction data does not establish a clean record.",
  },
  {
    name: "Researcher analysis",
    output: "A separate lookup for publication metrics and citation patterns.",
    limitation: "Frequent incoming citations do not establish reciprocal citation rings or manipulation. Results require review.",
  },
  {
    name: "Reports",
    output: "Downloadable reports and revocable share links.",
    limitation: "Reports summarize the analysis performed. They do not certify a source or researcher.",
  },
  {
    name: "Plagiarism and LMS integrations",
    output: "Not available in the current product.",
    limitation: "Corpus-based plagiarism checking and native Moodle/Canvas plugins are not implemented.",
  },
];

export function ComparisonSection() {
  return (
    <section id="compare" className="py-28 sm:py-32">
      <div className="mx-auto max-w-5xl px-6">
        <ChapterHeading
          numeral="IV"
          eyebrow="Scope and limitations"
          title={<>Know what was checked. <span className="italic text-brand-fg">Know what needs review.</span></>}
          subtitle="Source checks and researcher lookups are separate workflows. Use the findings to guide a review, with the coverage and limitations alongside the result."
        />
        <div className="mt-12 overflow-x-auto">
          <hr className="rule-double" />
          <table className="w-full min-w-[32rem] text-left text-sm">
            <caption className="sr-only">Current ArtiProof capabilities and limitations</caption>
            <thead>
              <tr className="border-b border-border-strong">
                <th scope="col" className="px-3 py-5 text-fg-primary">Capability</th>
                <th scope="col" className="px-3 py-5 text-fg-primary">Current output</th>
                <th scope="col" className="px-3 py-5 text-fg-primary">Limitations</th>
              </tr>
            </thead>
            <tbody>
              {capabilities.map((capability) => (
                <tr key={capability.name} className="border-b border-border-subtle last:border-b-0">
                  <th scope="row" className="px-3 py-4 align-top font-medium text-fg-primary">{capability.name}</th>
                  <td className="px-3 py-4 align-top text-fg-secondary">{capability.output}</td>
                  <td className="px-3 py-4 align-top text-fg-secondary">{capability.limitation}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <hr className="rule-double" />
        </div>
      </div>
    </section>
  );
}
