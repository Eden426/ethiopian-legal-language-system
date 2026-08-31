export type Language = "amh_Ethi" | "eng_Latn";

export type Citation = {
  passageId: string;
  label: string;
  excerpt: string;
};

const wait = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

export async function mockTranslate(text: string): Promise<string> {
  await wait(500);
  if (!text.trim()) throw new Error("Enter Amharic text before translating.");
  return "[Mock translation] This legal passage will be translated when the NLLB service is connected.";
}

export async function mockSearch(query: string, language: Language): Promise<Citation[]> {
  await wait(450);
  if (!query.trim()) throw new Error("Enter a search query.");
  const excerpt =
    language === "amh_Ethi"
      ? "ይህ የተፈበረከ የሙከራ ማስረጃ ነው፤ ከእውነተኛ ሕጋዊ ሰነድ አልተወሰደም።"
      : "This is fabricated test evidence and was not taken from a real legal document.";
  return [
    { passageId: "SYNTHETIC-001", label: "Synthetic fixture · Passage 1", excerpt },
    {
      passageId: "SYNTHETIC-002",
      label: "Synthetic fixture · Passage 2",
      excerpt: "Article 2 contains a synthetic number-preservation example.",
    },
  ];
}

export async function mockAnswer(question: string): Promise<{
  answer: string;
  citations: Citation[];
}> {
  await wait(550);
  if (!question.trim()) throw new Error("Enter a question.");
  return {
    answer:
      "This mock answer demonstrates the citation layout. A real answer will be returned only when indexed evidence is sufficient.",
    citations: [
      {
        passageId: "SYNTHETIC-001",
        label: "Synthetic fixture · Passage 1",
        excerpt: "Fabricated evidence used only for interface testing.",
      },
    ],
  };
}
