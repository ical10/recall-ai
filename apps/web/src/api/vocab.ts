export interface VocabItem {
  id: string;
  token: string;
  language: string;
  part_of_speech: string | null;
  definition: string;
  example_sentence: string | null;
  word_audio_url: string | null;
}

export interface VocabListResponse {
  items: VocabItem[];
  page: number;
  page_size: number;
  total: number;
}
