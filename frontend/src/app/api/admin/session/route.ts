import { NextResponse } from "next/server";
import { isAdminRequest } from "@/lib/adminAuth";

export async function GET(request: Request) {
  return NextResponse.json({ authed: isAdminRequest(request) });
}
