import { Request, Response, NextFunction } from "express";
import { verifySession } from "./session";

// Bearer-token auth: sets req.user from the Authorization header or answers 401.
export async function requireUser(req: Request, res: Response, next: NextFunction) {
  const token = (req.headers.authorization || "").replace(/^Bearer /, "");
  const user = token ? await verifySession(token) : null;
  if (!user) {
    return res.status(401).json({ error: "unauthorized" });
  }
  (req as any).user = user;
  next();
}
