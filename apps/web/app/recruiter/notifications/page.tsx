"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Notification {
  id: number;
  notification_type: string;
  message: string | null;
  is_read: boolean;
  sender_user_id: number | null;
  created_at: string | null;
}

const TYPE_LABELS: Record<string, string> = {
  new_application: "New Application",
  mention: "@Mention",
};

const TYPE_ICONS: Record<string, string> = {
  new_application: "\uD83D\uDCE5",
  mention: "\uD83D\uDCAC",
};

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function RecruiterNotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  useEffect(() => {
    setLoading(true);
    const url = new URL(`${API_BASE}/api/recruiter/notifications`);
    if (filter === "unread") url.searchParams.set("unread_only", "true");
    url.searchParams.set("limit", "100");

    fetch(url.toString(), { credentials: "include" })
      .then((r) => (r.ok ? r.json() : { notifications: [] }))
      .then((data) => setNotifications(data.notifications ?? []))
      .finally(() => setLoading(false));
  }, [filter]);

  const markRead = async (id: number) => {
    await fetch(`${API_BASE}/api/recruiter/notifications/${id}/read`, {
      method: "POST",
      credentials: "include",
    });
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
    );
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Notifications</h1>
        <p className="mt-1 text-sm text-slate-500">
          Application alerts, @mentions, and team activity
        </p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setFilter("all")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            filter === "all"
              ? "bg-indigo-600 text-white"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          All
        </button>
        <button
          onClick={() => setFilter("unread")}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
            filter === "unread"
              ? "bg-indigo-600 text-white"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          Unread{unreadCount > 0 && ` (${unreadCount})`}
        </button>
      </div>

      {/* Notification list */}
      {loading ? (
        <div className="py-12 text-center text-slate-400">Loading...</div>
      ) : notifications.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center">
          <p className="text-lg font-medium text-slate-600">No notifications</p>
          <p className="mt-1 text-sm text-slate-400">
            {filter === "unread"
              ? "You're all caught up!"
              : "Notifications will appear here when candidates apply or teammates mention you."}
          </p>
        </div>
      ) : (
        <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`flex items-start gap-4 px-5 py-4 transition ${
                n.is_read ? "bg-white" : "bg-indigo-50/50"
              }`}
            >
              {/* Icon */}
              <span className="mt-0.5 text-xl">
                {TYPE_ICONS[n.notification_type] ?? "\uD83D\uDD14"}
              </span>

              {/* Content */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                    {TYPE_LABELS[n.notification_type] ?? n.notification_type}
                  </span>
                  <span className="text-xs text-slate-400">
                    {timeAgo(n.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-700">{n.message}</p>
              </div>

              {/* Mark read */}
              {!n.is_read && (
                <button
                  onClick={() => markRead(n.id)}
                  className="shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
                >
                  Mark read
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
