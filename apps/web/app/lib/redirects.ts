const DISALLOWED_REDIRECT_PREFIXES = ["/login", "/signup", "/onboarding"];

export const normalizeRedirect = (
  redirect: string | null | undefined,
  fallback: string
) => {
  if (!redirect || !redirect.startsWith("/")) {
    return fallback;
  }
  if (DISALLOWED_REDIRECT_PREFIXES.some((prefix) => redirect.startsWith(prefix))) {
    return fallback;
  }
  return redirect;
};

export const buildRedirectValue = (
  pathname: string,
  searchParams?: URLSearchParams | null
) => {
  const query = searchParams?.toString();
  return query ? `${pathname}?${query}` : pathname;
};

export const withRedirectParam = (path: string, redirect: string) =>
  `${path}?redirect=${encodeURIComponent(redirect)}`;
