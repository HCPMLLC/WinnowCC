"use client";

import { useParams, redirect } from "next/navigation";

export default function CareerPageRedirect() {
  const { id } = useParams<{ id: string }>();
  redirect(`/recruiter/career-pages/${id}/builder`);
}
