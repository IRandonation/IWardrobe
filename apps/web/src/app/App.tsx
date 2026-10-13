import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, setCsrf, type Session } from "../lib/api";
import { Brand, Busy } from "../components/ui";
import { Login } from "../features/identity/Login";
import { Wardrobe } from "../pages/Wardrobe";

export function App() {
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => api<Session>("/auth/me"),
  });
  useEffect(() => {
    const expired = () => {
      setCsrf("");
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], null);
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, [client]);
  useEffect(() => {
    setCsrf(session.data?.csrf_token ?? "");
  }, [session.data]);
  if (session.isPending)
    return (
      <div className="loading-screen">
        <Brand />
        <Busy />
      </div>
    );
  if (
    !session.data ||
    (session.error instanceof ApiError && session.error.status === 401)
  )
    return (
      <Login
        onLogin={(value) => {
          setCsrf(value.csrf_token);
          client.removeQueries({
            predicate: (query) => query.queryKey[0] !== "session",
          });
          client.setQueryData(["session"], value);
        }}
      />
    );
  return <Wardrobe key={session.data.user.id} session={session.data} />;
}
