export interface Note {
  id: string;
  ownerId: string;
  title: string;
  body: string;
}

export declare const db: {
  notes: {
    findMany(args: { where: Partial<Note> }): Promise<Note[]>;
    findFirst(args: { where: Partial<Note> }): Promise<Note | null>;
    deleteMany(args: { where: Partial<Note> }): Promise<{ count: number }>;
  };
};
