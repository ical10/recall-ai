import type { Card } from "./review";

export interface QueuedRating {
  rating_id: string;
  card_id: string;
  grade: number;
  rated_at: string;
}

const BATCH_KEY = "recallai_batch";
const QUEUE_KEY = "recallai_rating_queue";

export function cacheBatch(cards: Card[]): Promise<void> {
  return chrome.storage.local.set({ [BATCH_KEY]: cards });
}

export function getCachedBatch(): Promise<Card[]> {
  return chrome.storage.local
    .get(BATCH_KEY)
    .then((r) => (r[BATCH_KEY] as Card[]) || []);
}

export function enqueue(rating: QueuedRating): Promise<void> {
  return chrome.storage.local.get(QUEUE_KEY).then((r) => {
    const queue: QueuedRating[] = (r[QUEUE_KEY] as QueuedRating[]) || [];
    queue.push(rating);
    return chrome.storage.local.set({ [QUEUE_KEY]: queue });
  });
}

export function getQueue(): Promise<QueuedRating[]> {
  return chrome.storage.local
    .get(QUEUE_KEY)
    .then((r) => (r[QUEUE_KEY] as QueuedRating[]) || []);
}

export function clearQueue(): Promise<void> {
  return chrome.storage.local.remove(QUEUE_KEY);
}

export async function flushQueue(
  postFn: (ratings: QueuedRating[]) => Promise<void>,
): Promise<number> {
  const queue = await getQueue();
  if (queue.length === 0) return 0;

  try {
    await postFn(queue);
    await clearQueue();
    return queue.length;
  } catch {
    return 0;
  }
}
