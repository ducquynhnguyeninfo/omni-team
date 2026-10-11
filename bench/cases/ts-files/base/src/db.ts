export interface User {
  id: string;
  name: string;
  email: string;
  role: "member" | "admin";   // admin unlocks /admin/*
  emailVerified: boolean;
}

export declare const db: {
  users: {
    findUnique(args: { where: { id: string } }): Promise<User>;
    update(args: { where: { id: string }; data: Partial<User> }): Promise<User>;
  };
};
