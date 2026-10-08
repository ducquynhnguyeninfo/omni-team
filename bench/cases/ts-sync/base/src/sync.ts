export interface Item {
  id: string;
  updatedAt: number;
}

export interface Store {
  save(item: Item): Promise<void>;
}
