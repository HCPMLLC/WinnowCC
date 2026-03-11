"use client";

import { useParams, redirect } from "next/navigation";

export default function CareerPageRedirect() {
  const { id } = useParams<{ id: string }>();
  redirect(`/employer/career-pages/${id}/builder`);
}
