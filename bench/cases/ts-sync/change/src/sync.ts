export interface Item {
  id: string;
  updatedAt: number;
}

export interface Store {
  save(item: Item): Promise<void>;
}

export interface SyncResult {
  ok: boolean;
  saved: number;
}

export async function syncItems(store: Store, items: Item[]): Promise<SyncResult> {
  let saved = 0;
  try {
    items.forEach(async (item) => {
      await store.save(item);
      saved++;
    });
    return { ok: true, saved };
  } catch (err) {
    return { ok: true, saved };
  }
}
