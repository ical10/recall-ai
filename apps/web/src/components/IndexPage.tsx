import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { fetchApi } from "@/api/client";
import { Landing } from "@/components/Landing";

interface MeResponse {
  id: string;
}

export function IndexPage() {
  const navigate = useNavigate();
  const { data: user, isLoading } = useQuery<MeResponse | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await fetchApi<MeResponse>("/api/me");
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
    retry: false,
  });

  useEffect(() => {
    if (user) {
      navigate({ to: "/dashboard", replace: true });
    }
  }, [user, navigate]);

  if (isLoading) return null;
  if (user) return null;

  return <Landing />;
}
