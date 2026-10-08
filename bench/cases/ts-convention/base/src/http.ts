import type { Response } from "express";

export function sendError(res: Response, status: number, code: string, message: string) {
  res.status(status).json({ code, message });
}
