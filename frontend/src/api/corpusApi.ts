export type LawType = "proclamation" | "book";

export type CorpusFile = {
  role: "source" | "target";
  language: "amh_Ethi" | "eng_Latn";
  original_name: string;
  sha256: string;
  size_bytes: number;
  page_count: number;
};

export type CorpusPage = {
  role: "source" | "target";
  language: "amh_Ethi" | "eng_Latn";
  page_number: number;
  sha256: string;
  size_bytes: number;
  width: number;
  height: number;
};

export type CorpusJob = {
  job_id: string;
  state: "created" | "uploaded" | "queued" | "processing" | "review" | "completed" | "failed" | "expired";
  stage: string;
  progress: number;
  error_code: string | null;
  law_type: LawType;
  title: string | null;
  document_id: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  upload_constraints: {
    max_pdf_bytes: number;
    max_pdf_pages: number;
    accepted_content_types: ["application/pdf"];
    source_language: "amh_Ethi";
    target_language: "eng_Latn";
  };
  files: CorpusFile[];
  pages: CorpusPage[];
};

const API_ROOT = "/api";

async function responseError(response: Response): Promise<Error> {
  try {
    const payload = (await response.json()) as { detail?: { message?: string } };
    if (payload.detail?.message) return new Error(payload.detail.message);
  } catch {
    // The fallback below deliberately avoids exposing server internals.
  }
  return new Error("The corpus request could not be completed.");
}

export async function createCorpusJob(lawType: LawType, title: string): Promise<CorpusJob> {
  const response = await fetch(`${API_ROOT}/v1/corpus/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ law_type: lawType, title: title.trim() || null }),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as CorpusJob;
}

export async function uploadCorpusFiles(
  jobId: string,
  sourceFile: File,
  targetFile: File,
): Promise<CorpusJob> {
  const form = new FormData();
  form.append("source_file", sourceFile);
  form.append("target_file", targetFile);
  form.append("confirm_same_document", "true");
  const response = await fetch(`${API_ROOT}/v1/corpus/jobs/${jobId}/files`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as CorpusJob;
}

export async function getCorpusJob(jobId: string): Promise<CorpusJob> {
  const response = await fetch(`${API_ROOT}/v1/corpus/jobs/${jobId}`);
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as CorpusJob;
}
